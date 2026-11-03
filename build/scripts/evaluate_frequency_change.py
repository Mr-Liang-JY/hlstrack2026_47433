from pathlib import Path
import csv,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from frequency_tracker import FrequencyTracker
from drift_monitor import DriftMonitor

def main():
    output=ROOT/'validation/frequency_change';output.mkdir(exist_ok=False)
    fs=30.;step=600;n=1500
    truth=np.where(np.arange(n)<step,1.,1.5)
    phase=np.cumsum(2*np.pi*truth/fs);position=60+10*np.sin(phase)
    tracker=FrequencyTracker(fs);monitor=DriftMonitor(1.,.15);rows=[]
    for k,v in enumerate(position):
        estimate=tracker.observe(float(v))[0];deviation=monitor.update(estimate)
        rows.append(dict(frame=k,time_s=k/fs,truth_hz=truth[k],estimate_hz=estimate['frequency_hz'],
                         valid=estimate['valid'],alarm=bool(deviation['alarm'])))
    alarm=[r for r in rows if r['frame']>=step and r['alarm']]
    false=[r for r in rows if r['frame']<step and r['alarm']]
    result=dict(status='PASS' if alarm and not false else 'FAIL',input='synthetic phase-continuous displacement, not physical fault diagnosis',
                fs=fs,window=512,change_s=step/fs,old_hz=1.,new_hz=1.5,tolerance_fraction=.15,
                first_alarm_s=alarm[0]['time_s'] if alarm else None,detection_delay_s=alarm[0]['time_s']-step/fs if alarm else None,
                prechange_false_alarm_frames=len(false),final_estimate_hz=rows[-1]['estimate_hz'])
    with (output/'frames.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (output/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
