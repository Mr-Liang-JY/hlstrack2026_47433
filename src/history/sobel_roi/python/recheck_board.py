"""PC: recheck downloaded ACTUAL PL frames, ROI statistics and saved PS FFT."""
from pathlib import Path
from datetime import datetime
import argparse
import csv
import json
import math
import numpy as np
from shm_common import sha256,sobel_reference,roi_stats,next_threshold,harmonic_fit

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,help='Downloaded complete board run directory')
    parser.add_argument('--prepared',help='Defaults to actual_ps_frames.npz saved by the board')
    parser.add_argument('--output',default='pc_recheck')
    args=parser.parse_args()
    folder=Path(args.input)
    prepared=Path(args.prepared) if args.prepared else folder/'actual_ps_frames.npz'
    summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    if summary.get('status')!='PASS' or summary.get('physical_board_test')!='PASS':
        raise ValueError('Board run was not completed/passed')
    identity=summary['run_identity']
    if sha256(prepared)!=identity['input_sha256']:
        raise ValueError('Wrong prepared video input')
    with np.load(str(prepared),allow_pickle=False) as data:
        frames,times,fs,roi=data['frames'],data['times_s'],float(data['fps']),data['roi'].tolist()
    with np.load(str(folder/'actual_pl_edges.npz'),allow_pickle=False) as received:
        edges,indices=received['edges'],received['frame_indices']
    with (folder/'frame_metrics.csv').open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    expected_indices=[0,len(frames)//2,len(frames)-1] if identity['smoke_test'] else list(range(len(frames)))
    if indices.tolist()!=expected_indices or len(rows)!=len(indices) or edges.shape!=(len(indices),128,128):
        raise ValueError('Incomplete/incorrect frame order')
    history=[];threshold=80.0;previous=None;positions=[]
    for order,(index,edge,row) in enumerate(zip(indices,edges,rows)):
        index=int(index)
        if identity['mode']=='adaptive' and not identity['smoke_test']:
            threshold,_=next_threshold(threshold,history,fs)
        integer_threshold=int(math.ceil(threshold))
        if int(row['frame_index'])!=index or int(row['frame_id'])!=((order+1)&15):
            raise ValueError('Wrong source index / hardware frame tag')
        if int(row['threshold'])!=integer_threshold or abs(float(row['time_s'])-times[index])>1e-9:
            raise ValueError('Threshold/time mismatch')
        expected=sobel_reference(frames[index],integer_threshold)
        if not np.array_equal(edge,expected):
            raise ValueError('Actual PL image mismatch at frame %d'%index)
        count,ysum=roi_stats(edge,roi)
        if count!=int(row['roi_edge_count']) or ysum!=int(row['roi_edge_y_sum']):
            raise ValueError('PL ROI statistics mismatch')
        if int(row['pixel_mismatches'])!=0 or int(row['roi_stat_mismatches'])!=0:
            raise ValueError('Saved mismatch count is nonzero')
        if not count:
            raise ValueError('Empty ROI')
        centroid=ysum/count
        if abs(float(row['centroid_y'])-centroid)>1e-9:
            raise ValueError('Centroid mismatch')
        positions.append(centroid)
        if previous is not None:
            x0,y0,x1,y1=roi
            mad=float(np.abs(frames[index,y0:y1,x0:x1].astype(np.int16)-previous[y0:y1,x0:x1].astype(np.int16)).mean())
            if abs(float(row['motion_mad'])-mad)>1e-9:
                raise ValueError('MAD mismatch')
            history.append(mad)
        elif row['motion_mad']!='':
            raise ValueError('First MAD must be undefined')
        previous=frames[index]
    if not identity['smoke_test']:
        fit,_=harmonic_fit(times,positions,fs)
        for name in ('fft_peak_hz','fitted_frequency_hz','r_squared','fitted_amplitude_processed_pixels'):
            if not np.isclose(fit[name],summary['harmonic_fit'][name],rtol=1e-6,atol=1e-8):
                raise ValueError('Saved FFT/fit differs: '+name)
    out=Path(args.output)/('recheck_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    out.mkdir(parents=True,exist_ok=False)
    result={'status':'PASS','checked_frames':len(rows),'checked_pixels':int(edges.size),
            'source_summary_sha256':sha256(folder/'summary.json'),
            'actual_pl_edges_sha256':sha256(folder/'actual_pl_edges.npz'),
            'scope':'Offline audit of saved board data; not a new physical board measurement'}
    (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('DAY9 PC RECHECK PASSED (%d frames; %d pixels)'%(len(rows),edges.size))
    print(out.resolve())
if __name__=='__main__':main()
