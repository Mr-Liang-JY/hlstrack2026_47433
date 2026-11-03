"""Read-only clock/HPD/frame counter probe; never downloads an Overlay."""
from pathlib import Path
import argparse,json,time
from pynq import MMIO,PL
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
assert Path(PL.bitfile_name).name=='award_video.bit'
m=json.loads((ROOT/'out/manifest.json').read_text());gpio=MMIO(m['display_control_address'],4096)
samples=[]
for _ in range(21):samples.append((time.monotonic(),gpio.read(8)));time.sleep(.1)
values=[v for _,v in samples]
assert all((v>>24)==0xa8 and (v&14)==14 and not(v&128) for v in values)
result=dict(status='PASS',clock_lock=True,pixel_reset_released=True,monitor_hpd=True,framebuffer_protocol_error=False,
    enabled=bool(values[-1]&1),first_presented=(values[0]>>8)&65535,last_presented=(values[-1]>>8)&65535,
    heartbeat_transitions=sum(bool((x^y)&16) for x,y in zip(values,values[1:])),
    hardware_sha256=m['hardware_sha256'],observation='registers and heartbeat only, no monitor image quality claim')
path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
