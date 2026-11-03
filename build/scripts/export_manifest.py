"""Bind exported bit/HWH to exact source snapshots after every Vivado build."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'out'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    sources={}
    for folder,pattern in [('rtl','*.v'),('constraints','*.xdc')]:
        for p in sorted((ROOT/folder).glob(pattern)):
            saved=OUT/'build_sources'/folder/p.name
            if not saved.is_file() or digest(saved)!=digest(p):raise ValueError('Stale hardware source: '+p.name)
            sources[p.relative_to(ROOT).as_posix()]=digest(p)
    tree=ET.parse(OUT/'award_video.hwh')
    ip=tree.find(".//MODULE[@INSTANCE='display_control']")
    params={p.get('NAME'):p.get('VALUE') for p in ip.findall('./PARAMETERS/PARAMETER')}
    value=dict(design='award_video',part='xc7z020clg400-1',vivado='2024.2',display_packet_words=8448,
               display_control_address=int(params['C_BASEADDR'],0),
               hardware_sha256={name:digest(OUT/name) for name in ['award_video.bit','award_video.hwh']},
               sources_sha256=sources,
               interface=dict(sobel_input='128x128 uint32, grayscale[7:0]',sobel_output='binary[7:0], saturated magnitude[15:8]',
                              display='8448 little-endian uint32 words, TLAST per packet',hdmi='1280x720 60Hz'))
    (OUT/'manifest.json').write_text(json.dumps(value,indent=2));print('Hardware manifest exported and source snapshots verified')
if __name__=='__main__':main()
