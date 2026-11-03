"""Paired on-board PS/PL microbenchmark, same inputs/ROI/outputs, no decode/UI."""
from pathlib import Path
import argparse,csv,json,platform,sys,time,hashlib
import numpy as np
import cv2
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from board_hardware import Hardware
from video_core import reference,statistics

def optimized_ps(gray,threshold,roi):
 gx=cv2.Sobel(gray,cv2.CV_16S,1,0,ksize=3);gy=cv2.Sobel(gray,cv2.CV_16S,0,1,ksize=3)
 mag=cv2.add(cv2.convertScaleAbs(gx),cv2.convertScaleAbs(gy));mag[[0,-1],:]=0;mag[:,[0,-1]]=0
 edge=cv2.compare(mag,threshold,cv2.CMP_GE);edge[[0,-1],:]=0;edge[:,[0,-1]]=0
 x0,y0,x1,y1=roi;m=cv2.moments(edge[y0:y1,x0:x1],binaryImage=True)
 return edge,mag,int(m['m00']),int(m['m01']+y0*m['m00'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--repeats',type=int,default=3);a=p.parse_args()
 if platform.machine().lower() not in ['armv7l','armv8l','aarch64']:raise RuntimeError('Run this benchmark on PYNQ')
 folder=Path(a.output);folder.mkdir(parents=True,exist_ok=False)
 with np.load(ROOT/'data/prepared_frames.npz') as d:frames=d['frames'];roi=tuple(map(int,d['roi']))
 hw=Hardware(ROOT/'out/award_video.bit');rows=[]
 try:
  for gray in frames[:3]:hw.sobel(gray,80,roi);reference(gray,80);optimized_ps(gray,80,roi)
  for repeat in range(a.repeats):
   for backend in (['ps_numpy','ps_opencv','pl'] if repeat%2==0 else ['pl','ps_opencv','ps_numpy']):
    for i,gray in enumerate(frames):
     begin=time.perf_counter()
     if backend=='pl':edge,mag,count,ysum,_=hw.sobel(gray,80,roi)
     elif backend=='ps_opencv':edge,mag,count,ysum=optimized_ps(gray,80,roi)
     else:edge,mag=reference(gray,80);count,ysum=statistics(edge,roi)
     elapsed=time.perf_counter()-begin
     expected,expected_mag=reference(gray,80);n,s=statistics(expected,roi)
     if not np.array_equal(edge,expected) or not np.array_equal(mag,expected_mag) or (n,s)!=(count,ysum):raise AssertionError('Benchmark correctness failure')
     rows.append({'backend':backend,'repeat':repeat,'frame':i,'wall_s':elapsed})
    print('benchmark',repeat,backend,'PASS',flush=True)
 finally:hw.close()
 with (folder/'transactions.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 result={'status':'PASS','scope':'same-board Sobel magnitude/binary + ROI; host and DMA included; input prepared in RAM; decode, policy, display, validation excluded','repeats':a.repeats,'backends':{}}
 result['warmup_frames_per_backend']=3
 result['benchmark_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 result['driver_sha256']=hashlib.sha256((ROOT/'python/board_hardware.py').read_bytes()).hexdigest()
 result['hardware_sha256']=json.loads((ROOT/'out/manifest.json').read_text())['hardware_sha256']
 for name in ['ps_numpy','ps_opencv','pl']:
  v=np.asarray([r['wall_s'] for r in rows if r['backend']==name]);result['backends'][name]={'frames':len(v),'mean_ms':float(v.mean()*1000),'p95_ms':float(np.percentile(v,95)*1000),'fps':float(1/v.mean())}
 result['numpy_to_pl_mean_time_ratio']=result['backends']['ps_numpy']['mean_ms']/result['backends']['pl']['mean_ms']
 result['opencv_to_pl_mean_time_ratio']=result['backends']['ps_opencv']['mean_ms']/result['backends']['pl']['mean_ms']
 (folder/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
