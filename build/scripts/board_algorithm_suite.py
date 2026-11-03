"""Real PL holdout ablations; no parameter fitting or selection on this set."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from video_app import parser,process,hardware
def main():
    hw=hardware(ROOT/'out/award_video.bit')
    try:
        for case in ['noise','weak']:
            for mode in ['fixed','time','spatial','spectral']:
                args=parser().parse_args(['process','--input',str(ROOT/('data/controlled_'+case+'.npz')),
                    '--output',str(ROOT/('results/board_'+case+'_'+mode)),'--policy',mode,'--no-preview'])
                process(args,hw)
    finally:hw.close()
if __name__=='__main__':main()
