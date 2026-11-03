"""Record only non-personal runtime versions for later reproduction."""
from pathlib import Path
import json,platform
import cv2,numpy,pynq,PIL
ROOT=Path(__file__).resolve().parents[1]
result=dict(board='PYNQ-Z2',architecture=platform.machine(),python=platform.python_version(),pynq=pynq.__version__,numpy=numpy.__version__,opencv=cv2.__version__,pillow=PIL.__version__)
for key,name in [('cpu_governor','scaling_governor'),('cpu_frequency_khz_observed','scaling_cur_freq')]:
 path=Path('/sys/devices/system/cpu/cpu0/cpufreq')/name
 if path.exists():result[key]=path.read_text().strip()
output=ROOT/'results/environment';output.mkdir(exist_ok=True);(output/'versions.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
