from pathlib import Path
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    for name in ('video_stage3.bit','video_stage3.hwh','timing_summary.rpt','drc.rpt','utilization.rpt'):
        if not (OUT/name).is_file():raise FileNotFoundError('Build has not exported '+name)
    for path in list((ROOT/'rtl').glob('*.v'))+list((ROOT/'constraints').glob('*.xdc')):
        snapshot=OUT/'build_sources'/path.parent.name/path.name
        if not snapshot.exists() or digest(path)!=digest(snapshot):raise ValueError('Stale hardware: '+path.name)
    # Keep full local logs private; exported reports should not expose host or
    # Windows profile paths when someone later shares the delivery directory.
    private=ROOT/'build/private_reports';private.mkdir(exist_ok=True)
    for path in list(OUT.glob('*.rpt'))+list(OUT.glob('tb_*.log')):
        data=path.read_text(encoding='utf-8',errors='replace')
        if not (private/path.name).exists():shutil.copy2(path,private/path.name)
        data=re.sub(r'(?m)^\| Host\s*:.*$', '| Host         : [redacted]',data)
        data=data.replace(str(ROOT),'<PROJECT>').replace(ROOT.as_posix(),'<PROJECT>')
        data=data.replace(str(ROOT).replace('\\','/').lower(),'<PROJECT>')
        # Case-insensitive drive/profile spelling also occurs in IP reports.
        data=re.sub(re.escape(ROOT.as_posix()),'<PROJECT>',data,flags=re.I)
        path.write_text(data,encoding='utf-8')
    tests={}
    for test in ('tb_axis_framebuffer','tb_video_timing','tb_sobel_frame_axis','tb_tmds_encoder','tb_serializer','tb_video_display'):
        text=(OUT/(test+'.log')).read_text(errors='replace')
        if 'PASS ' not in text or re.search(r'Fatal:|FATAL|ERROR:',text):raise ValueError('Simulation did not pass: '+test)
        tests[test]='PASS'
    xml=ET.parse(OUT/'video_stage3.hwh')
    gpio=xml.find(".//MODULE[@INSTANCE='display_control']")
    if gpio is None:raise ValueError('Missing display_control in HWH')
    params={p.get('NAME'):p.get('VALUE') for p in gpio.findall('./PARAMETERS/PARAMETER')}
    address=int(params['C_BASEADDR'],0)
    source_hashes={p.relative_to(ROOT).as_posix():digest(p) for folder,pattern in [('rtl','*.v'),('constraints','*.xdc'),('scripts','*.tcl')]
                   for p in sorted((ROOT/folder).glob(pattern))}
    manifest={'design':'video_stage3','part':'xc7z020clg400-1','vivado':'2024.2',
        'hardware_sha256':{name:digest(OUT/name) for name in ['video_stage3.bit','video_stage3.hwh']},
        'display_control_address':address,'sources_sha256':source_hashes,
        'format':{'sobel_input':'128x128 uint32, low byte grayscale',
                  'sobel_output':'uint32: binary[7:0], saturated magnitude[15:8]',
                  'display_input':'640x360 uint8, four pixels/uint32, little endian, TLAST per frame',
                  'hdmi':'1280x720 60Hz; 74.25MHz pixel; 371.25MHz DDR serializer'}}
    save(OUT/'manifest.json',manifest)
    physical=OUT/'board_test_summary.json'
    software=(ROOT/'validation/software_tests.txt').read_text(encoding='utf-8-sig')
    if not re.search(r'\bOK\b',software) or 'FAILED' in software:raise ValueError('Software tests failed')
    status={'simulation':tests,'software_tests':'PASS - see out/software_tests.txt',
        'bitstream_export':'PASS','setup_hold_drc':'PASS - export script checks setup/hold and DRC errors',
        'board_processing':'NOT_RUN','board_presentation':'NOT_RUN','monitor_visual_observation':'NOT_OBSERVED_BY_AGENT'}
    if physical.exists():status.update(json.loads(physical.read_text()))
    save(OUT/'validation_status.json',status)
    shutil.copy2(ROOT/'validation/software_tests.txt',OUT/'software_tests.txt')
    staging=ROOT/'board/video_stage3'
    staging.mkdir(parents=True,exist_ok=True)
    for folder in ('python','data','docs'):
        for src in (ROOT/folder).glob('*'):
            if src.is_file() and src.suffix not in ('.pyc',):
                target=staging/folder/src.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
    for name in ('video_stage3.bit','video_stage3.hwh','manifest.json','validation_status.json','software_tests.txt'):
        target=staging/'out'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(OUT/name,target)
    extra=['timing_summary.rpt','utilization.rpt','drc.rpt','board_test_summary.json',
           'board_display_status.json','display_optimization.json']
    extra += [p.name for p in OUT.glob('tb_*.log')]
    for name in extra:
        if (OUT/name).exists():shutil.copy2(OUT/name,staging/'out'/name)
    for name in ('README.md','LICENSE','THIRD_PARTY.md','requirements_pc.txt','RUN_DEMO.py','BLACK_SCREEN.py'):
        shutil.copy2(ROOT/name,staging/name)
    shutil.copy2(ROOT/'docs/01_板端逐步操作.md',ROOT/'board/先读操作说明.md')
    # Exclude caches/results and all personal/host paths from distributable ZIPs.
    with ZipFile(ROOT/'board/video_stage3_board.zip','w',ZIP_DEFLATED,compresslevel=6) as z:
        for src in sorted(staging.rglob('*')):
            if src.is_file() and '__pycache__' not in src.parts:
                z.write(src,'video_stage3/'+src.relative_to(staging).as_posix())
        assert all(not p.startswith('/') and '..' not in Path(p).parts for p in z.namelist())
    with ZipFile(ROOT/'video_stage3_source.zip','w',ZIP_DEFLATED,compresslevel=6) as z:
        for folder in ('rtl','constraints','scripts','sim','python','docs','board_files','data'):
            for src in sorted((ROOT/folder).rglob('*')):
                if src.is_file() and '__pycache__' not in src.parts:z.write(src,src.relative_to(ROOT).as_posix())
        for name in ('README.md','LICENSE','THIRD_PARTY.md','requirements_pc.txt','RUN_DEMO.py','BLACK_SCREEN.py'):z.write(ROOT/name,name)
        z.write(ROOT/'validation/test_software.py','validation/test_software.py')
    save(OUT/'delivery_hashes.json',{'board_zip_sha256':digest(ROOT/'board/video_stage3_board.zip'),
                                  'source_zip_sha256':digest(ROOT/'video_stage3_source.zip')})
    print(json.dumps(status,indent=2))

if __name__=='__main__':main()
