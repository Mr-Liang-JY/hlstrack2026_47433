"""Entry point: demo/process/play/blank/preview. All media stays local."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import time
import numpy as np
from PIL import Image
from video_core import ROOT,reference,statistics
from adaptive_policy import AdaptivePolicy as Policy,MODES
from frequency_tracker import FrequencyTracker
from drift_monitor import DriftMonitor
from video_input import source_frames
from native_codec import NativeComposer as Composer,render_packet,PACKET_WORDS

def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while True:
            chunk=f.read(1024*1024)
            if not chunk:break
            h.update(chunk)
    return h.hexdigest()

def hardware(bit):
    from board_hardware import Hardware
    return Hardware(bit)

def process(args,hw=None):
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();media=Path(args.input)
    digest=file_hash(media)
    source=json.loads((ROOT/'data/source.json').read_text(encoding='utf-8'))
    crop=args.crop
    region=args.roi
    if digest==source['video_sha256']:
        crop=crop or source['crop_xywh'];region=region or source['roi_xyxy']
    fs,roi,frames,total,preprocessing=source_frames(media,region,crop,args.max_frames,args.decoder)
    if not (0<=roi[0]<roi[2]<=128 and 0<=roi[1]<roi[3]<=128):raise ValueError('Invalid ROI')
    estimate_bytes=total*(PACKET_WORDS*4+3*128*128)
    if shutil.disk_usage(out).free<estimate_bytes+128*1024**2:
        raise RuntimeError('Insufficient storage for result cache')
    policy=Policy(args.policy,fs,args.threshold);composer=Composer();tracker=FrequencyTracker(fs,args.fft_window);monitor=DriftMonitor(args.reference_hz,args.frequency_tolerance)
    owned=False
    if args.backend=='pl' and hw is None:hw=hardware(args.bit);owned=True
    rows=[];history=[];previous=None;error=None;completed=0
    streams={name:(out/(name+('.u32' if name=='display_packets' else '.u8'))).open('wb') for name in ('display_packets','gray_frames','edge_frames','magnitude_frames')}
    fields=['frame_index','time_s','threshold','roi_edge_count','roi_edge_y_sum','centroid_y',
            'motion_mad','frequency_hz','fft_samples','fft_bin_spacing_hz',
            'reference_hz','frequency_deviation','frequency_alarm','spectral_noise_ratio','noise_gradient_median','edge_contrast','decode_preprocess_s','policy_s','dma_pl_s','verification_s','analysis_s','render_s','compute_s']
    csvfile=(out/'frame_metrics.csv').open('w',newline='',encoding='utf-8')
    writer=csv.DictWriter(csvfile,fieldnames=fields);writer.writeheader()
    try:
        iterator=iter(frames)
        while True:
            t=time.perf_counter()
            try:gray=next(iterator)
            except StopIteration:break
            decode_s=time.perf_counter()-t
            t=time.perf_counter();th=policy.next();decision=dict(policy.last_decision);policy_s=time.perf_counter()-t
            begin=time.perf_counter()
            if hw:edge,mag,count,ysum,dma_s=hw.sobel(gray,th,roi)
            else:
                edge,mag=reference(gray,th);count,ysum=statistics(edge,roi);dma_s=0.0
            core_s=time.perf_counter()-begin
            t=time.perf_counter();ref_edge,ref_mag=reference(gray,th);rc,rs=statistics(ref_edge,roi)
            if not np.array_equal(edge,ref_edge) or not np.array_equal(mag,ref_mag) or (count,ysum)!=(rc,rs):
                np.savez_compressed(out/'failed_frame.npz',gray=gray,edge=edge,magnitude=mag,
                                    reference_edge=ref_edge,reference_magnitude=ref_mag)
                raise AssertionError('PL pixel/magnitude/ROI mismatch at frame %d'%completed)
            verify_s=time.perf_counter()-t
            t=time.perf_counter();mad=policy.observe(gray,previous,roi,mag);previous=gray
            cy=ysum/count if count else None;history.append(cy)
            est,freq,amp=tracker.observe(cy);deviation=monitor.update(est)
            analysis_s=time.perf_counter()-t
            m={'frame_index':completed,'time_s':completed/fs,'threshold':th,'roi_edge_count':count,
               'roi_edge_y_sum':ysum,'centroid_y':cy,'frequency':est,'policy':args.policy,'alarm':deviation['alarm'],'playback_fps':args.fps}
            t=time.perf_counter()
            canvas=composer.render(gray,mag,edge,roi,m,history,freq,amp,args.binary,args.backend!='pl')
            render_s=time.perf_counter()-t
            for name,value in [('display_packets',canvas),('gray_frames',gray),('edge_frames',edge),('magnitude_frames',mag)]:
                streams[name].write(value.tobytes())
            row={k:v for k,v in m.items() if k in fields}
            row.update(reference_hz=deviation['reference_hz'],frequency_deviation=deviation['deviation_fraction'],frequency_alarm=deviation['alarm'],spectral_noise_ratio=decision['high_frequency_ratio'],noise_gradient_median=decision['noise_gradient_median'],edge_contrast=decision['edge_tail'],motion_mad=mad,frequency_hz=est['frequency_hz'],fft_samples=est['samples'],
                fft_bin_spacing_hz=est['bin_spacing_hz'],decode_preprocess_s=decode_s,policy_s=policy_s,dma_pl_s=dma_s,
                verification_s=verify_s,analysis_s=analysis_s,render_s=render_s,
                compute_s=decode_s+policy_s+core_s+analysis_s)
            rows.append(row);writer.writerow(row);completed+=1
            if completed==1 or completed%30==0:
                
                if args.preview_png:Image.fromarray(render_packet(canvas)).save(out/'preview_latest.png')
                if hw and not args.no_preview:hw.show(canvas)
                print('processed %d frames; verification PASS'%completed,flush=True)
        if not completed:raise ValueError('Video contains no decodable frames')
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        for stream in streams.values():stream.close()
        csvfile.close()
        elapsed=time.perf_counter()-started
        compute=sum(row['compute_s'] for row in rows)
        summary={'status':'FAIL' if error else 'PASS','backend':args.backend,
            'physical_board_processing':'PASS' if hw and not error else 'NOT_VERIFIED',
            'source_name':media.name,'source_sha256':digest,'source_fps':fs,
            'processed_frames':completed,'processing_size':[128,128],'canvas_size':[1280,720],'display_packet_words':PACKET_WORDS,'display_compositor':'native PL images/text/plots',
            'hdmi_signal':'1280x720 60Hz','requested_playback_fps':args.fps,'roi_xyxy':list(roi),
            'policy':args.policy,'initial_threshold':args.threshold,'preprocessing':preprocessing,
            'pixel_verification':'PASS' if not error else 'INCOMPLETE','verified_frames':completed,
            'total_wall_s':elapsed,'wall_processing_fps':completed/max(elapsed,1e-9),
            'compute_s':compute,'compute_fps':completed/max(compute,1e-9),
            'compute_scope':'decode/preprocess + Sobel/ROI + motion/FFT; verification/render/cache/display excluded',
            'final_frequency':tracker.finish()[0],
            'frequency_note':'centroid-y proxy in pixels; uncalibrated source clock; df is FFT grid spacing, not accuracy',
            'error':error,'privacy':'no hostname, username, network address or credentials recorded'}
        if hw:
            summary['hardware_sha256']=json.loads(Path(args.bit).with_name('manifest.json').read_text())['hardware_sha256']
        summary['driver_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        snapshot=out/'software_snapshot';snapshot.mkdir(exist_ok=True)
        hashes={}
        for src in sorted((ROOT/'python').glob('*.py')):
            shutil.copy2(src,snapshot/src.name);hashes['python/'+src.name]=file_hash(src)
        write_json(out/'software_sha256.json',hashes)
        summary['policy_version']='legacy_stage3' if args.policy in ('fixed','time','spectral_v1') else 'gradient_noise_spectral_v2'
        summary['frame_cache_format']='native_packet_u32'
        if not error:
            summary['display_cache_sha256']=file_hash(out/'display_packets.u32')
        write_json(out/'summary.json',summary)
        if owned and hw:hw.close()
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return out

def playback(args,hw=None):
    out=Path(args.output);summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    if summary['status']!='PASS':raise ValueError('Refusing incomplete/failed result cache')
    if summary['backend']!='pl' and not args.allow_reference:
        raise ValueError('PC reference cache needs --allow-reference; it is not PL evidence')
    n=summary['processed_frames'];fs=summary['source_fps'];fps=args.fps
    raw=out/'display_packets.u32'
    if raw.stat().st_size!=n*PACKET_WORDS*4:raise ValueError('Truncated display cache')
    if file_hash(raw)!=summary['display_cache_sha256']:
        raise ValueError('Display cache hash mismatch')
    cache_mode='ram' if raw.stat().st_size<=args.cache_memory_mb*1024**2 else 'memory_mapped'
    frames=(np.fromfile(raw,dtype='<u4').reshape(n,PACKET_WORDS) if cache_mode=='ram' else
            np.memmap(raw,mode='r',dtype='<u4',shape=(n,PACKET_WORDS)))
    # Resample playback only; frequency analysis above always uses SOURCE FPS.
    indices=np.minimum(n-1,np.floor(np.arange(max(1,round(n/fs*fps)))*fs/fps).astype(int))
    owned=hw is None
    if owned:hw=hardware(args.bit)
    shown=0;late=0;intervals=[];previous=None;started=time.monotonic();stop='completed';upload_s=[];trace=[]
    try:
        loop=0;deadline=time.monotonic()
        while args.loops==0 or loop<args.loops:
            for idx in indices:
                if (ROOT/'STOP_PLAYBACK').exists():
                    stop='STOP_PLAYBACK file';return
                remain=deadline-time.monotonic()
                if remain>0:time.sleep(remain)
                begin=time.monotonic();hw.show(frames[int(idx)])
                now=time.monotonic();upload_s.append(now-begin)
                if previous is not None:intervals.append(now-previous)
                interval=now-previous if previous is not None else None
                trace.append(dict(sequence=shown,source_index=int(idx),upload_s=now-begin,
                                  interval_s=interval,deadline_lateness_s=max(0,now-deadline),deadline_reset=now>deadline+2/fps))
                previous=now;shown+=1;deadline+=1/fps
                if now>deadline+1/fps:
                    late+=1;deadline=now
            loop+=1
    except KeyboardInterrupt:stop='keyboard interrupt'
    except BaseException:stop='error';raise
    finally:
        hw.blank()
        if owned:hw.close()
        elapsed=time.monotonic()-started
        record={'status':'PASS' if stop!='error' else 'FAIL','stop_reason':stop,'presented_frames':shown,
            'target_fps':fps,'measured_presentation_fps':1/float(np.mean(intervals)) if intervals else None,
            'presentation_interval_p95_ms':1000*float(np.percentile(intervals,95)) if intervals else None,
            'upload_plus_vblank_mean_ms':1000*float(np.mean(upload_s)) if upload_s else None,
            'deadline_resets':late,'wall_s':elapsed,'dropped_frames':0,
            'cache_mode':cache_mode,'display_cache_bytes':raw.stat().st_size,
            'presentation_interval_max_ms':1000*max(intervals) if intervals else None,
            'player_sha256':file_hash(Path(__file__)),
            'observation':'hardware acknowledgments; visible monitor quality needs physical observation'}
        with (out/'playback_intervals.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['sequence','source_index','upload_s','interval_s','deadline_lateness_s','deadline_reset'])
            writer.writeheader();writer.writerows(trace)
        write_json(out/'playback_latest.json',record);print(json.dumps(record,indent=2),flush=True)
        del frames

def export_preview(args):
    import cv2
    out=Path(args.output);s=json.loads((out/'summary.json').read_text())
    n=s['processed_frames'];frames=np.memmap(out/'display_packets.u32',mode='r',dtype='<u4',shape=(n,PACKET_WORDS))
    indices=np.minimum(n-1,np.floor(np.arange(max(1,round(n/s['source_fps']*30)))*s['source_fps']/30).astype(int))
    path=out/'processed_30fps.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),30,(1280,720))
    if not writer.isOpened():raise RuntimeError('MP4 encoder unavailable; raw cache remains usable')
    try:
        for i in indices:
            frame=render_packet(frames[int(i)])
            writer.write(cv2.cvtColor(frame,cv2.COLOR_GRAY2BGR))
    finally:writer.release()
    cap=cv2.VideoCapture(str(path));actual=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));rate=cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if actual!=len(indices) or abs(rate-30)>0.01:raise AssertionError('Exported video validation failed')
    write_json(out/'mp4_validation.json',{'frames':actual,'fps':rate,'size':[1280,720],
        'codec':'MPEG-4 Part 2 / mp4v; display playback does not require encoding/decoding this export',
        'pl_executed':s['backend']=='pl'})
    print(str(path))

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['demo','process','play','blank','preview'])
    p.add_argument('--input',default=str(ROOT/'data/spring_mass.mp4'))
    p.add_argument('--output',default=str(ROOT/'results/demo_01'))
    p.add_argument('--bit',default=str(ROOT/'out/award_video.bit'))
    p.add_argument('--backend',choices=['pl','reference'],default='pl')
    p.add_argument('--policy',choices=MODES,default='spectral')
    p.add_argument('--threshold',type=int,default=80)
    p.add_argument('--roi',nargs=4,type=int);p.add_argument('--crop',nargs=4,type=int)
    p.add_argument('--max-frames',type=int,default=900)
    p.add_argument('--fps',type=float,default=30)
    p.add_argument('--loops',type=int,default=3,help='0 loops indefinitely, Ctrl+C stops and blanks')
    p.add_argument('--fft-window',type=int,choices=[128,256,512],default=512);p.add_argument('--reference-hz',type=float);p.add_argument('--frequency-tolerance',type=float,default=.15)
    p.add_argument('--binary',action='store_true',default=True);p.add_argument('--magnitude',action='store_false',dest='binary');p.add_argument('--no-preview',action='store_true');p.add_argument('--preview-png',action='store_true');p.add_argument('--decoder',choices=['auto','opencv','gstreamer'],default='opencv')
    p.add_argument('--allow-reference',action='store_true')
    p.add_argument('--cache-memory-mb',type=int,default=64,help='Preload compact caches within this RAM budget; zero uses mmap')
    return p

def main():
    p=parser();args=p.parse_args()
    if not 0<=args.threshold<=255 or not 0<args.fps<=60 or args.loops<0 or args.max_frames<1 or args.cache_memory_mb<0:
        p.error('Invalid threshold/fps/loops/max-frames')
    if args.command=='blank':
        from pynq import MMIO,PL
        # Read the exported GPIO physical address; never reload the overlay to blank.
        manifest=json.loads(Path(args.bit).with_name('manifest.json').read_text())
        if Path(PL.bitfile_name).name!='award_video.bit':
            raise RuntimeError('Current overlay is not award_video; use monitor power button to blank')
        display=MMIO(manifest['display_control_address'],4096)
        if display.read(8)>>24!=0xA8:raise RuntimeError('Unexpected display signature; no write performed')
        display.write(0,0)
        print('HDMI BLACK; clock stays active');return
    if args.command=='preview':export_preview(args);return
    if args.command=='play':playback(args);return
    if args.command=='demo':
        if args.backend!='pl':p.error('Use process for PC reference; demo requires real PL')
        hw=hardware(args.bit)
        try:process(args,hw);playback(args,hw)
        finally:hw.close()
    else:process(args)

if __name__=='__main__':main()
