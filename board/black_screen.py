from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    runtime=ROOT/'build/work/runtime'
    if not (runtime/'black_screen.py').is_file():raise RuntimeError('No materialized runtime; use the monitor power button if another Overlay is active')
    subprocess.run([sys.executable,str(runtime/'black_screen.py')],cwd=runtime,check=True)
