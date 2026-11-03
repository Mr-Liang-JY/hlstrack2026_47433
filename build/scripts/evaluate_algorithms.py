"""Development/holdout ablations with independent geometric truth, no report prose."""
from pathlib import Path
import argparse,csv,hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from video_core import reference,statistics
from adaptive_policy import AdaptivePolicy,DEFAULTS,MODES
from frequency_tracker import estimate

CASES={'clean':(0,1,0),'noise_20':(20,1,0),'noise_35':(35,1,0),
       'dim_065':(0,.65,0),'bright_130':(0,1.3,0),'flicker_9hz':(8,1,.3),'low_contrast_noise':(8,.22,0),'weak_contrast':(0,.10,0)}
def blur(a):
    a=np.pad(np.asarray(a,float),1,mode='reflect')
    b=(a[:-2,:-2]+2*a[:-2,1:-1]+a[:-2,2:]+2*a[1:-1,:-2]+4*a[1:-1,1:-1]+2*a[1:-1,2:]+a[2:,:-2]+2*a[2:,1:-1]+a[2:,2:])/16
    return np.clip(np.rint(b),0,255).astype(np.uint8)
def sequence(case,seed,n=300,frequency=.8):
    noise,gain,flicker=CASES[case];rng=np.random.default_rng(seed)
    images=[];truths=[];positions=[]
    for k in range(n):
        t=k/30;x=int(round(47+12*np.sin(2*np.pi*frequency*t)));y=int(round(48+10*np.sin(2*np.pi*frequency*t)))
        mask=np.zeros((128,128),bool);mask[y:y+26,x:x+20]=1
        interior=mask.copy();interior[1:-1,1:-1]&=mask[:-2,1:-1]&mask[2:,1:-1]&mask[1:-1,:-2]&mask[1:-1,2:]
        ideal=np.where(mask,180.,40.)
        observed=ideal*(gain+flicker*np.sin(2*np.pi*9*t))+rng.normal(0,noise,ideal.shape)
        images.append(blur(np.clip(observed,0,255)));truths.append(mask&~interior);positions.append(y+12.5)
    return np.asarray(images),np.asarray(truths),np.asarray(positions)
def dilate(a):
    p=np.pad(a,1);return np.logical_or.reduce([p[y:y+a.shape[0],x:x+a.shape[1]] for y in range(3) for x in range(3)])
def edge_scores(edge,truth):
    a=edge!=0;n=int(a.sum());nt=int(truth.sum())
    p=float((a&dilate(truth)).sum()/n) if n else float(nt==0)
    r=float((truth&dilate(a)).sum()/nt) if nt else 1.
    return p,r,2*p*r/(p+r) if p+r else 0.
def run(out,split):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    n=180 if split=='development' else 300;seed=20261103 if split=='development' else 20261117
    protocol={'split':split,'seed':seed,'frames':n,'fs':30,'cases':CASES,'policies':MODES,'params':DEFAULTS,
        'ground_truth':'one-pixel geometric inner rectangle contour; exact mask centre-y',
        'edge_matching':'independent precision/recall matches within one Chebyshev pixel; no one-to-one assignment',
        'metrics_scope':'post-warmup frames index>=65; all results retained',
        'physical_board_test':'NOT_RUN; controlled software evaluation only'}
    protocol['policy_sha256']=hashlib.sha256((ROOT/'python/adaptive_policy.py').read_bytes()).hexdigest()
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    summary=[]
    with (out/'frame_metrics.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['case','mode','frame','threshold','precision','recall','f1','centroid_y','truth_y'])
        for ci,case in enumerate(CASES):
            frames,truths,positions=sequence(case,seed+ci,n)
            for mode in MODES:
                policy=AdaptivePolicy(mode,30);previous=None;rows=[];centres=[]
                for k,(image,truth,ty) in enumerate(zip(frames,truths,positions)):
                    th=policy.next();edge,mag=reference(image,th);count,ysum=statistics(edge,(0,0,128,128))
                    cy=ysum/count if count else None;centres.append(cy);p,r,f1=edge_scores(edge,truth)
                    rows.append((th,p,r,f1,cy,ty));writer.writerow([case,mode,k,th,p,r,f1,cy,ty])
                    policy.observe(image,previous,(0,0,128,128),mag);previous=image
                post=rows[65:];est=estimate(centres,30)[0]
                valid=[(cy,ty) for _,_,_,_,cy,ty in post if cy is not None]
                s={'case':case,'mode':mode,'mean_f1':float(np.mean([row[3] for row in post])),
                   'mean_precision':float(np.mean([row[1] for row in post])),'mean_recall':float(np.mean([row[2] for row in post])),
                   'threshold_min':min(row[0] for row in post),'threshold_max':max(row[0] for row in post),
                   'position_rmse_px':float(np.sqrt(np.mean([(a-b)**2 for a,b in valid]))) if valid else None,
                   'frequency_hz':est['frequency_hz'],'frequency_error_percent':abs(est['frequency_hz']-.8)/.8*100 if est['valid'] else None}
                summary.append(s);print(split,case,mode,'F1 %.4f'%s['mean_f1'],flush=True)
            if split=='holdout' and case in ['noise_20','low_contrast_noise']:
                np.savez_compressed(out/(case+'.npz'),frames=frames,truths=truths,truth_y=positions,
                    times_s=np.arange(n)/30,fps=30.,roi=np.array([1,1,127,127]),truth_frequency_hz=.8)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    # Known input frequency suite is an accuracy test of the estimator, not a real-video ground truth claim.
    frequencies=[]
    for freq in [.5,.8,1.25,2.0]:
        frames,_,truth=sequence('clean',seed+100,300,freq);cy=[]
        for image in frames:
            edge,_=reference(image,80);nedge,ysum=statistics(edge,(0,0,128,128));cy.append(ysum/nedge if nedge else None)
        est=estimate(cy,30)[0];frequencies.append(dict(truth_hz=freq,estimate=est,error_percent=abs(est['frequency_hz']-freq)/freq*100 if est['valid'] else None))
    (out/'frequency_accuracy.json').write_text(json.dumps(frequencies,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--split',choices=['development','holdout'],required=True)
    a=p.parse_args();run(a.output,a.split)
