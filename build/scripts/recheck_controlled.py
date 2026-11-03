"""Score actual hardware edges using independent geometric ground truth."""
from pathlib import Path
import argparse,csv,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from evaluate_algorithms import edge_scores
from recheck_results import check
def main():
    rows=[]
    for case in ['noise','weak']:
        with np.load(ROOT/('data/controlled_'+case+'.npz')) as src:truth=src['truths'];truth_y=src['truth_y'];truth_hz=float(src['truth_frequency_hz'])
        for mode in ['fixed','time','spatial','spectral']:
            folder=ROOT/('validation/board_'+case+'_'+mode);check(folder)
            s=json.loads((folder/'summary.json').read_text());n=s['processed_frames']
            edges=np.memmap(folder/'edge_frames.u8',mode='r',dtype=np.uint8,shape=(n,128,128))
            with (folder/'frame_metrics.csv').open() as f:metrics=list(csv.DictReader(f))
            scores=np.asarray([edge_scores(e,t) for e,t in zip(edges,truth)])
            err=[(float(r['centroid_y'])-ty)**2 for r,ty in zip(metrics[65:],truth_y[65:]) if r['centroid_y']]
            freq=s['final_frequency']['frequency_hz']
            rows.append(dict(case=case,policy=mode,physical_board_test='PASS',frames=n,evaluation_frames=n-65,
                 precision=float(scores[65:,0].mean()),recall=float(scores[65:,1].mean()),f1=float(scores[65:,2].mean()),
                 position_rmse_px=float(np.sqrt(np.mean(err))) if err else None,
                 truth_frequency_hz=truth_hz,estimate_hz=freq,frequency_error_percent=abs(freq-truth_hz)/truth_hz*100 if freq else None))
    (ROOT/'validation/board_algorithm_scores.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
