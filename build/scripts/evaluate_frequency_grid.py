"""Off-grid synthetic frequency checks, without fitting estimator parameters."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'python')]
from evaluate_algorithms import sequence
from video_core import reference,statistics
from frequency_tracker import estimate

def main():
 rows=[]
 for f in [.37,.53,.73,1.13,1.77,2.31]:
  frames,_,_=sequence('clean',20261119,300,f);centres=[]
  for frame in frames:
   edge,_=reference(frame,80);n,s=statistics(edge,(1,1,127,127));centres.append(s/n if n else None)
  est=estimate(centres,30)[0]
  rows.append(dict(truth_hz=f,estimate=est,error_percent=abs(est['frequency_hz']-f)/f*100 if est['valid'] else None))
 result=dict(status='COMPLETE',scope='clean synthetic displaced geometric target, 300 frames at 30Hz; off FFT-bin centres; no physical accuracy claim',
             parameter_fitting=False,tests=rows)
 out=ROOT/'validation/offgrid_frequency_accuracy.json';out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
