"""Run ONLY in PYNQ Jupyter: real DMA/PL Sobel + ROI, PS motion FFT."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import math
import platform
import shutil
import sys
import time
import traceback
import xml.etree.ElementTree as ET
import numpy as np
from shm_common import (sha256, sobel_reference, roi_stats, next_threshold,
                        save_analysis, write_csv)

def status_fields(word):
    return {'raw_hex': '0x%08X'%word, 'signature': (word>>28)&15,
            'frame_id': (word>>24)&15, 'error_code': (word>>20)&15,
            'busy': bool(word&2), 'done': bool(word&1)}

def check_hwh(path):
    root = ET.parse(str(path)).getroot()
    def parameters(instance):
        module = root.find(".//MODULE[@INSTANCE='%s']"%instance)
        if module is None:
            raise RuntimeError('Wrong HWH: missing '+instance)
        return {v.get('NAME'): v.get('VALUE') for v in module.findall('./PARAMETERS/PARAMETER')}
    reset = parameters('proc_sys_reset_0')
    if reset.get('C_EXT_RESET_HIGH') != '0' or reset.get('C_AUX_RESET_HIGH') != '1':
        raise RuntimeError('Wrong reset polarity in HWH; rebuild matching bit/hwh')
    dma = parameters('axi_dma_0')
    if dma.get('C_INCLUDE_SG') != '0' or int(dma.get('C_SG_LENGTH_WIDTH','0')) < 17:
        raise RuntimeError('DMA must use simple mode and support at least 65536-byte frames')
    for name in ('axi_gpio_ctrl','axi_gpio_stats','axi_gpio_roi'):
        parameters(name)

class FrameAccelerator:
    def __init__(self, bitfile, timeout=10.0):
        from pynq import Overlay, MMIO, allocate
        check_hwh(Path(bitfile).with_suffix('.hwh'))
        self.overlay = Overlay(str(bitfile))
        required = ('axi_dma_0','axi_gpio_ctrl','axi_gpio_stats','axi_gpio_roi')
        missing = [name for name in required if name not in self.overlay.ip_dict]
        if missing:
            raise RuntimeError('Wrong Overlay IP names: '+repr(missing))
        def mmio(name):
            item = self.overlay.ip_dict[name]
            return MMIO(int(item['phys_addr']),int(item['addr_range']))
        self.ctrl, self.stats, self.roi = [mmio(name) for name in required[1:]]
        self.dma = self.overlay.axi_dma_0
        self.timeout = timeout
        self.input = allocate(shape=(128*128,), dtype=np.uint32)
        self.output = allocate(shape=(128*128,), dtype=np.uint32)
        self.ctrl.write(0,0)
        time.sleep(0.001)
        self.ctrl.write(0,(80<<8)|1)
        self.status()

    def status(self):
        result = status_fields(self.ctrl.read(8))
        if result['signature'] != 0xD:
            raise RuntimeError('PL signature mismatch: '+repr(result))
        return result

    def capture(self, image, threshold, roi):
        if image.shape != (128,128) or not 0 <= threshold <= 255:
            raise ValueError('Expected 128x128 frame and uint8 threshold')
        x0,y0,x1,y1 = [int(v) for v in roi]
        if not (0 <= x0 < x1 <= 128 and 0 <= y0 < y1 <= 128):
            raise ValueError('Invalid ROI')
        before = self.status()
        if before['busy']:
            raise RuntimeError('Previous frame still busy')
        expected_id = (before['frame_id']+1)&15
        self.input[:] = image.ravel()
        self.output[:] = np.uint32(0xDEADBEEF)
        self.roi.write(0, x0|(y0<<8)|(x1<<16)|(y1<<24))
        self.ctrl.write(0,(threshold<<8)|1)
        self.ctrl.write(0,(threshold<<8)|3)
        self.ctrl.write(0,(threshold<<8)|1)
        started = time.monotonic()
        # Arm receive first. Buffers are physically contiguous and uint32 aligned.
        self.dma.recvchannel.transfer(self.output)
        self.dma.sendchannel.transfer(self.input)
        while True:
            tx_status = self.dma.mmio.read(0x04)
            rx_status = self.dma.mmio.read(0x34)
            state = self.status()
            if (tx_status|rx_status)&0x70:
                raise RuntimeError('DMA error TX=0x%08X RX=0x%08X PL=%r'%(tx_status,rx_status,state))
            if state['error_code']:
                raise RuntimeError('PL protocol error: '+repr(state))
            finished = state['frame_id']==expected_id and state['done'] and not state['busy']
            if finished and tx_status&2 and rx_status&2:
                break
            if time.monotonic()-started > self.timeout:
                raise TimeoutError('DMA/PL timeout: TX=0x%08X RX=0x%08X PL=%r'%(tx_status,rx_status,state))
            time.sleep(0.0002)
        # Already confirmed idle, so these waits do not hide unbounded polling.
        self.dma.sendchannel.wait()
        self.dma.recvchannel.wait()  # PYNQ performs receive cache invalidation.
        words = np.array(self.output, copy=True)
        if not np.all((words==0)|(words==255)):
            raise RuntimeError('Output contains unwritten/invalid uint32 pixels')
        return words.astype(np.uint8).reshape(128,128), {
            'frame_id': expected_id, 'roi_edge_count': int(self.stats.read(0)),
            'roi_edge_y_sum': int(self.stats.read(8)),
            'transfer_and_pl_wall_s': time.monotonic()-started,
            'dma_tx_status_hex': '0x%08X'%tx_status,
            'dma_rx_status_hex': '0x%08X'%rx_status}

    def close(self):
        # Only release buffers after channels are quiescent. Failed runs reset DMA.
        self.ctrl.write(0,0)
        tx,rx = self.dma.mmio.read(0x04),self.dma.mmio.read(0x34)
        safe = bool((tx&3) and (rx&3))
        if not safe:
            self.dma.mmio.write(0x00,4)
            limit = time.monotonic()+1
            while self.dma.mmio.read(0x00)&4 and time.monotonic()<limit:
                time.sleep(0.001)
            safe = not bool(self.dma.mmio.read(0x00)&4)
        if safe:
            self.input.freebuffer()
            self.output.freebuffer()
        else:
            print('DMA reset did not finish; buffers retained. Restart the board before rerunning.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bitfile', default='day9_shm.bit')
    parser.add_argument('--input', default='prepared_frames.npz')
    parser.add_argument('--video', help='Optional original MP4: perform preprocessing on PS, needs ARM OpenCV')
    parser.add_argument('--source', default='source.json')
    parser.add_argument('--mode', choices=('fixed','adaptive'), default='fixed')
    parser.add_argument('--smoke', action='store_true', help='3 real frames, pixel/ROI validation only; no frequency claim')
    parser.add_argument('--output', default='day9_results')
    parser.add_argument('--timeout', type=float, default=10)
    args = parser.parse_args()
    if platform.machine().lower() not in ('armv7l','aarch64','armv8l'):
        raise RuntimeError('Run this on PYNQ ARM, not Windows. PC reference is prepare_video.py.')
    bit = Path(args.bitfile).resolve()
    source = json.loads(Path(args.source).read_text(encoding='utf-8'))
    if args.video:
        if sha256(args.video)!=source['video_sha256']:
            raise ValueError('Original video hash differs from source.json')
        from video_preprocess import decode_frames
        frames,times,fs=decode_frames(args.video,source['crop_xywh'])
        roi=source['roi_xyxy']
        source['preprocessing_location']='PYNQ_PS (OpenCV)'
    else:
        if sha256(args.input) != source['prepared_sha256']:
            raise ValueError('Prepared input hash differs from source.json')
        with np.load(args.input, allow_pickle=False) as data:
            frames,times,fs,roi = data['frames'],data['times_s'],float(data['fps']),data['roi'].tolist()
        source['preprocessing_location']='PC prepared frames; PS loads exact pixel arrays'
    if frames.shape != (source['frame_count'],128,128) or frames.dtype != np.uint8:
        raise ValueError('Wrong prepared frame format')
    if not np.allclose(np.diff(times),1/fs,atol=1e-6):
        raise ValueError('Nonuniform video timestamps')
    folder = Path(args.output)/('run_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir(parents=True,exist_ok=False)
    if args.video:
        np.savez_compressed(str(folder/'actual_ps_frames.npz'),frames=frames,times_s=times,
                            fps=np.array(fs),roi=np.asarray(roi,dtype=np.uint32))
    else:
        shutil.copyfile(args.input,str(folder/'actual_ps_frames.npz'))
    trace = (folder/'run_log.txt').open('w',encoding='utf-8')
    def log(message):
        print(message);trace.write(message+'\n');trace.flush()
    import pynq
    identity = {'utc_time': datetime.now(timezone.utc).isoformat(), 'machine': platform.machine(),
                'python_version':sys.version,'numpy_version':np.__version__,
                'pynq_version':getattr(pynq,'__version__','unknown'), 'bit_sha256':sha256(bit),
                'hwh_sha256':sha256(bit.with_suffix('.hwh')), 'input_sha256':sha256(folder/'actual_ps_frames.npz'),
                'preprocessing_location':source['preprocessing_location'],
                'driver_sha256':sha256(__file__), 'mode':args.mode,'smoke_test':args.smoke,
                'physical_board_test':'FAILED_OR_INCOMPLETE','status':'FAIL'}
    (folder/'run_identity.json').write_text(json.dumps(identity,indent=2),encoding='utf-8')
    accelerator = None
    rows, outputs, previous_mad = [], [], []
    previous = None
    threshold = 80.0
    indices = [0,len(frames)//2,len(frames)-1] if args.smoke else list(range(len(frames)))
    try:
        accelerator = FrameAccelerator(bit,args.timeout)
        log('Hardware loaded. Source: '+source['page_url'])
        for order,index in enumerate(indices):
            image = frames[index]
            ratio = None
            if args.mode=='adaptive' and not args.smoke:
                threshold,ratio = next_threshold(threshold,previous_mad,fs)
            integer_threshold = int(math.ceil(threshold))
            actual, result = accelerator.capture(image,integer_threshold,roi)
            outputs.append(actual)
            expected = sobel_reference(image,integer_threshold)
            wrong = int(np.count_nonzero(actual!=expected))
            count,ysum = roi_stats(actual,roi)
            stat_errors = int(count!=result['roi_edge_count'] or ysum!=result['roi_edge_y_sum'])
            x0,y0,x1,y1 = roi
            mad = None if previous is None else float(np.abs(image[y0:y1,x0:x1].astype(np.int16)-previous[y0:y1,x0:x1].astype(np.int16)).mean())
            rows.append({'frame_index':index,'time_s':float(times[index]),
                         'threshold_float':threshold,'threshold':integer_threshold,
                         'previous_motion_high_energy_ratio':ratio,
                         'roi_edge_count':result['roi_edge_count'],'roi_edge_y_sum':result['roi_edge_y_sum'],
                         'centroid_y':result['roi_edge_y_sum']/result['roi_edge_count'] if result['roi_edge_count'] else None,
                         'motion_mad':mad,'pixel_mismatches':wrong,'roi_stat_mismatches':stat_errors,
                         'frame_id':result['frame_id'],'transfer_and_pl_wall_s':result['transfer_and_pl_wall_s'],
                         'dma_tx_status_hex':result['dma_tx_status_hex'],'dma_rx_status_hex':result['dma_rx_status_hex']})
            write_csv(folder/'frame_metrics.csv',rows)
            if order in (0,len(indices)//2,len(indices)-1) or wrong or stat_errors:
                import matplotlib.pyplot as plt
                plt.imsave(str(folder/('frame_%03d_pl.png'%index)),actual,cmap='gray',vmin=0,vmax=255)
                plt.imsave(str(folder/('frame_%03d_reference.png'%index)),expected,cmap='gray',vmin=0,vmax=255)
            log('FRAME %d/%d source=%d id=%d T=%d pixel_mismatches=%d ROI_mismatches=%d count=%d'%(
                order+1,len(indices),index,result['frame_id'],integer_threshold,wrong,stat_errors,count))
            if wrong or stat_errors:
                raise AssertionError('Actual PL output differs; raw received images preserved')
            if mad is not None:previous_mad.append(mad)
            previous=image
        if args.smoke:
            summary={'status':'PASS','physical_board_test':'PASS','processed_frames':len(rows),
                     'pixel_mismatches':0,'roi_stat_mismatches':0,
                     'scope':'3 selected real frames, pixel/ROI/DMA verification; no FFT on nonuniform selected times'}
        else:
            summary=save_analysis(folder,rows,fs,source,'PASS')
            log('PS FFT peak=%.6f Hz; sinusoid-fit frequency=%.6f Hz; R2=%.6f'%(
                summary['harmonic_fit']['fft_peak_hz'],summary['harmonic_fit']['fitted_frequency_hz'],
                summary['harmonic_fit']['r_squared']))
        summary['run_identity']=identity
        summary['run_identity']['physical_board_test']='PASS'
        summary['run_identity']['status']='PASS'
        (folder/'run_identity.json').write_text(json.dumps(summary['run_identity'],indent=2),encoding='utf-8')
        (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        log('DAY9 PYNQ BOARD TEST PASSED (%d frames; %d/%d pixels matched; ROI statistics matched)'%(
            len(rows),len(rows)*16384,len(rows)*16384))
        log('RESULT DIRECTORY: '+str(folder.resolve()))
    except Exception as exc:
        failure=dict(identity,error='%s: %s'%(type(exc).__name__,exc),completed_frames=len(rows))
        (folder/'run_identity.json').write_text(json.dumps(failure,indent=2),encoding='utf-8')
        (folder/'summary.json').write_text(json.dumps(failure,indent=2),encoding='utf-8')
        log(traceback.format_exc())
        raise
    finally:
        if outputs:
            np.savez_compressed(str(folder/'actual_pl_edges.npz'),edges=np.asarray(outputs,dtype=np.uint8),
                                frame_indices=np.asarray(indices[:len(outputs)],dtype=np.int32))
        if accelerator is not None:accelerator.close()
        trace.close()

if __name__=='__main__':main()
