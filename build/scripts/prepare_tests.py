from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from video_core import reference,statistics
old=ROOT/'sim/tb_sobel_frame_axis.sv'
if not old.exists():
    old=ROOT.parents[1]/'competition_2026/hardware/v2/sim/tb_sobel_frame_axis.sv'
text=old.read_text()
text=text.replace('DAY9 AXIS SOBEL SIMULATION PASSED','PASS PACKED AXIS SOBEL')
(ROOT/'sim/tb_sobel_frame_axis.sv').write_text(text)
rng=np.random.default_rng(20261102)
with np.load(ROOT/'data/prepared_frames.npz') as src:frames=src['frames'][[0,75,150]]
cases=[(frames[0],80,(1,22,127,126)),(frames[1],110,(1,1,127,127)),
       (frames[2],0,(0,0,128,128)),(rng.integers(0,256,(128,128),dtype=np.uint8),255,(7,11,100,110)),
       (np.zeros((128,128),np.uint8),80,(1,1,127,127)),
       (np.full((128,128),255,np.uint8),80,(1,1,127,127))]
with (ROOT/'sim/vectors.txt').open('w') as f:
    f.write(str(len(cases))+'\n')
    for gray,th,roi in cases:
        edge,mag=reference(gray,th);n,s=statistics(edge,roi)
        f.write(' '.join(map(str,(th,*roi,n,s)))+'\n')
        packed=edge.astype(np.uint32)|(mag.astype(np.uint32)<<8)
        for a,b in zip(gray.ravel(),packed.ravel()):f.write('%d %d\n'%(a,b))
print('Prepared six packed-output Sobel cases')
