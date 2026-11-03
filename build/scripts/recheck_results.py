from pathlib import Path
import argparse,csv,hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from video_core import reference,statistics
from video_app import file_hash
from native_codec import PACKET_WORDS

def check(folder):
    folder=Path(folder);s=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    n=s['processed_frames'];roi=s['roi_xyxy']
    with (folder/'frame_metrics.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
    if len(rows)!=n:raise ValueError('Frame count mismatch')
    arrays=[]
    for name in ('gray_frames','edge_frames','magnitude_frames'):
        path=folder/(name+'.u8')
        if path.stat().st_size!=n*128*128:raise ValueError('Truncated '+name)
        arrays.append(np.memmap(path,mode='r',dtype=np.uint8,shape=(n,128,128)))
    errors=0;stats_errors=0
    for i,(gray,edge,mag,row) in enumerate(zip(*arrays,rows)):
        ref_e,ref_m=reference(gray,int(row['threshold']))
        errors+=int(np.count_nonzero(edge!=ref_e))+int(np.count_nonzero(mag!=ref_m))
        count,ysum=statistics(ref_e,roi)
        stats_errors+=int(count!=int(row['roi_edge_count']) or ysum!=int(row['roi_edge_y_sum']))
        expected=ysum/count if count else None
        got=float(row['centroid_y']) if row['centroid_y'] else None
        if (expected is None)!=(got is None) or (expected is not None and abs(expected-got)>1e-8):stats_errors+=1
    cache=folder/'display_packets.u32'
    good=(cache.stat().st_size==n*PACKET_WORDS*4 and file_hash(cache)==s['display_cache_sha256'])
    snapshot_ok=None
    if (folder/'software_sha256.json').exists():
        hashes=json.loads((folder/'software_sha256.json').read_text())
        snapshot_ok=all(file_hash(folder/'software_snapshot'/Path(name).name)==value for name,value in hashes.items())
        good=good and snapshot_ok
    result={'status':'PASS' if errors==stats_errors==0 and good else 'FAIL','frames':n,
        'pixel_values_checked':n*128*128*2,'pixel_mismatches':errors,'roi_or_centroid_mismatches':stats_errors,
        'display_cache_verified':good,'software_snapshot_verified':snapshot_ok,'backend':s['backend'],'physical_board_processing':s['physical_board_processing']}
    (folder/'pc_recheck.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if result['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');check(p.parse_args().folder)
