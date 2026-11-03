"""Make repeatable RTL cases from three real frames plus arithmetic corner cases."""
from pathlib import Path
import numpy as np
from shm_common import sobel_reference, roi_stats
ROOT = Path(__file__).resolve().parents[1]
def main():
    with np.load(str(ROOT/'inputs/prepared_frames.npz'), allow_pickle=False) as data:
        frames = data['frames']
        roi = data['roi'].tolist()
    rng = np.random.RandomState(19)
    ramp = np.tile(np.arange(128, dtype=np.uint8)*2, (128, 1))
    cases = [(frames[0],80,roi),(frames[len(frames)//2],100,roi),
             (frames[-1],40,[1,1,127,127]),
             (rng.randint(0,256,(128,128)).astype(np.uint8),80,[16,24,112,120]),
             (np.zeros((128,128),dtype=np.uint8),0,[0,0,128,128]),
             (ramp,255,[20,30,90,110])]
    with (ROOT/'sim/vectors.txt').open('w', encoding='ascii') as out:
        out.write(str(len(cases))+'\n')
        for frame, threshold, rectangle in cases:
            edge = sobel_reference(frame, threshold)
            count, ysum = roi_stats(edge, rectangle)
            out.write(' '.join(str(v) for v in [threshold]+rectangle+[count,ysum])+'\n')
            for pixel, expected in zip(frame.ravel(),edge.ravel()):
                out.write('%d %d\n'%(pixel,expected))
    print('SIM VECTORS READY: 6 frames, 98304 pixels, source/random/zero/ramp, varied thresholds/ROIs')
if __name__ == '__main__':main()
