"""PYNQ entry: process a local file, play at 30 FPS, then blank HDMI."""
from pathlib import Path
import os,signal,subprocess,sys,time

ROOT=Path(__file__).resolve().parent
def main():
    (ROOT/'STOP_PLAYBACK').unlink(missing_ok=True)
    env=dict(os.environ)
    local=ROOT/'data/optional_decoder/usr/lib/arm-linux-gnueabihf'
    if local.exists():env['LD_LIBRARY_PATH']=str(local)+':'+env.get('LD_LIBRARY_PATH','')
    env.setdefault('XILINX_XRT','/usr')
    result=ROOT/'results'/('demo_'+time.strftime('%Y%m%d_%H%M%S'))
    command=[sys.executable,'-u',str(ROOT/'python/video_app.py'),'demo','--no-preview','--output',str(result),*sys.argv[1:]]
    child=subprocess.Popen(command,cwd=ROOT,env=env)
    try:code=child.wait()
    except KeyboardInterrupt:
        if child.poll() is None:child.send_signal(signal.SIGINT)
        code=child.wait(timeout=15)
    if code:raise SystemExit(code)

if __name__=='__main__':main()
