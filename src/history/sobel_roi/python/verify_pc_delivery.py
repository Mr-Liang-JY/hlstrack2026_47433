"""Inspect real PC/Vivado delivery evidence. Never labels a physical board test PASS."""
from pathlib import Path
import ast
import csv
import json
import re
import numpy as np
from shm_common import sha256,spectrum,sobel_reference,roi_stats
from run_board import check_hwh

ROOT=Path(__file__).resolve().parents[1]
def main():
    checks=[]
    def require(condition,message):
        if not condition:raise AssertionError(message)
        checks.append(message)
    source=json.loads((ROOT/'inputs/source.json').read_text(encoding='utf-8'))
    require(sha256(ROOT/'inputs/spring_mass.mp4')==source['video_sha256'],'Original real-video hash matches attribution')
    require(sha256(ROOT/'inputs/prepared_frames.npz')==source['prepared_sha256'],'Prepared input hash matches source record')
    with np.load(str(ROOT/'inputs/prepared_frames.npz'),allow_pickle=False) as data:
        frames,times,fs,roi=data['frames'],data['times_s'],float(data['fps']),data['roi'].tolist()
    require(frames.shape==(151,128,128) and frames.dtype==np.uint8,'151 real frames with uint8 128x128 format')
    require(fs==30 and np.allclose(times,np.arange(151)/30,atol=1e-12),'Video timeline is uniform 30 Hz')
    with (ROOT/'reference/frame_metrics.csv').open(encoding='utf-8-sig',newline='') as stream:
        metrics=list(csv.DictReader(stream))
    require(len(metrics)==151 and metrics[0]['motion_mad']=='','Reference has 151 rows and no invented first MAD')
    for frame,row in zip(frames,metrics):
        count,ysum=roi_stats(sobel_reference(frame,80),roi)
        require(count==int(row['roi_edge_count']) and ysum==int(row['roi_edge_y_sum']),
                'Reference ROI statistics frame '+row['frame_index'])
    positions=np.array([float(r['centroid_y']) for r in metrics])
    f,a,_=spectrum(positions,fs)
    k=1+int(np.argmax(a[1:]));window=np.hanning(len(positions))
    direct=2*abs(np.dot((positions-positions.mean())*window,np.exp(-2j*np.pi*k*np.arange(len(positions))/len(positions))))/window.sum()
    require(np.isclose(direct,a[k],atol=1e-10),'Direct DFT cross-check of position spectral peak')
    reference=json.loads((ROOT/'reference/summary.json').read_text(encoding='utf-8'))
    require(abs(reference['harmonic_fit']['fitted_frequency_hz']-reference['independent_dark_body_fit']['fitted_frequency_hz'])<0.02,
            'Edge centroid/body-mask frequency estimates agree within 0.02 Hz (not external calibration)')
    test_log=(ROOT/'validation/python_tests.log').read_text(encoding='utf-8')
    require('Ran 7 tests' in test_log and '\nOK' in test_log,'Seven Python reference/protocol tests passed')
    sim_log=(ROOT/'validation/simulation_pipeline.log').read_text(encoding='utf-8',errors='replace')
    require('DAY9 AXIS SOBEL SIMULATION PASSED (6 frames; 98304 pixels; backpressure, TLAST and ROI verified)' in sim_log
            and 'Fatal:' not in sim_log,'Final pipelined RTL passed actual Vivado simulation')
    build_log=(ROOT/'validation/rebuild_pipeline.log').read_text(encoding='utf-8',errors='replace')
    require('DAY9 BUILD FINISHED' in build_log,'Final full Vivado build/export finished')
    timing=(ROOT/'out/timing_summary.rpt').read_text(encoding='utf-8',errors='replace')
    require('All user specified timing constraints are met.' in timing,'Routed design meets timing constraints')
    require('checking no_clock (0)' in timing and 'checking unconstrained_internal_endpoints (0)' in timing,
            'No unclocked registers or unconstrained internal endpoints')
    match=re.search(r'WNS\(ns\).*?\n\s*-+[^\n]*\n\s*([-\d.]+)\s+([-\d.]+)\s+(\d+)\s+(\d+)\s+([-\d.]+)',timing,re.S)
    if not match:raise ValueError('Cannot parse final setup/hold timing summary')
    wns,whs=float(match.group(1)),float(match.group(5))
    require(wns>=0 and whs>=0,'Nonnegative setup and hold slack')
    require((ROOT/'out/day9_shm.bit').stat().st_size>1000000,'Exported physical FPGA bitstream exists')
    check_hwh(ROOT/'out/day9_shm.hwh')
    require(True,'Matching HWH provides DMA simple mode, length and reset parameters')
    for name in ('run_board.py','shm_common.py','video_preprocess.py','check_board.py'):
        require((ROOT/'out'/name).read_bytes()==(ROOT/'python'/name).read_bytes(),'Out driver matches source: '+name)
    for path in (ROOT/'python').glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,10))
    require(True,'Python sources parse with Python 3.10 grammar; local runtime test used Python 3.12')
    result={'status':'PASS_PC_AND_VIVADO_ONLY','physical_board_test':'NOT_RUN',
            'checks':checks,'check_count':len(checks),'rtl_simulated_frames':6,'rtl_simulated_pixels':98304,
            'nominal_clock_mhz':100,'setup_wns_ns':wns,'hold_whs_ns':whs,
            'bit_sha256':sha256(ROOT/'out/day9_shm.bit'),'hwh_sha256':sha256(ROOT/'out/day9_shm.hwh'),
            'remaining_user_action':'Run uploaded package on physical PYNQ, save real DMA output and run computer recheck',
            'material_scope':'Full-frame BRAM offline processing; FFT on PS; no claimed real-time FPS or external physical calibration',
            'preserved_warnings':'TUL board preset contains DDR skew warnings; final reports/logs retained. Physical board operation not verified here.'}
    (ROOT/'validation/VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DELIVERY VERIFICATION PASSED (%d checks); physical PYNQ test NOT RUN'%len(checks))
    print('Setup WNS %.3f ns; hold WHS %.3f ns'%(wns,whs))
if __name__=='__main__':main()
