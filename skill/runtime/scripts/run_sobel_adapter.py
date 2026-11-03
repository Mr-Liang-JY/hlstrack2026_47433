"""Same generic DMA runner, with only start/ready and ROI application adapters."""
from pathlib import Path
import argparse,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'python'),str(ROOT/'skill/scripts')]
from pynq_tools import load_config,DmaRunner,compare_arrays
from board_hardware import Hardware
from video_core import reference,statistics
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    config=load_config(ROOT/'skill/examples/award_sobel.json');hw=Hardware(config['bitfile']);runner=None;rows=[]
    try:
        runner=DmaRunner(config,overlay=hw.overlay)
        with np.load(ROOT/'data/prepared_frames.npz') as src:frames=src['frames'][[0,75,150]];roi=tuple(map(int,src['roi']))
        for k,gray in enumerate(frames):
            before=hw.control.read(8);expected=(((before>>24)&15)+1)&15
            x0,y0,x1,y1=roi;hw.roi.write(0,x0|(y0<<8)|(x1<<16)|(y1<<24))
            def start():
                for bits in (1,3,1):hw.control.write(0,(80<<8)|bits)
            def ready():
                status=hw.control.read(8)
                if (status>>20)&15:raise RuntimeError('Sobel protocol status error')
                return (status&3)==1 and ((status>>24)&15)==expected
            raw,timing=runner.transfer(gray.astype(np.uint32),start=start,ready=ready)
            edge,mag=reference(gray,80);gold=edge.astype(np.uint32)|(mag.astype(np.uint32)<<8)
            result=compare_arrays(raw,gold);n,s=statistics(edge,roi)
            assert result['passed'] and (hw.stats.read(0),hw.stats.read(8))==(n,s)
            rows.append(dict(frame=k,comparison=result,measurement=timing,roi_pass=True))
    finally:
        if runner:runner.close()
        hw.close()
    result=dict(passed=True,physical_board_test='RUN',task='Sobel image processing',shared_runner='pynq_tools.DmaRunner',frames=rows)
    (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
