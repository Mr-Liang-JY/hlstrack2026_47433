"""Blank the current award_video Overlay without reloading hardware."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parent
env=dict(os.environ);env.setdefault('XILINX_XRT','/usr')
if __name__=='__main__':
    (ROOT/'STOP_PLAYBACK').touch()
    subprocess.run([sys.executable,str(ROOT/'python/video_app.py'),'blank'],cwd=ROOT,env=env,check=True)
