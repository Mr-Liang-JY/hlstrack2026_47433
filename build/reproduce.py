"""Prepare the verified runtime layout and execute reproducible project actions."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'build/work/runtime'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy_folder(source,dest):
    if not source.is_dir():raise FileNotFoundError(source)
    for p in sorted(source.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        q=dest/p.relative_to(source);q.parent.mkdir(parents=True,exist_ok=True)
        if not q.exists() or sha(p)!=sha(q):shutil.copy2(p,q)

def prepare_runtime(target=None):
    target=Path(target) if target else RUNTIME;target.mkdir(parents=True,exist_ok=True)
    for source,dest in [('src/rtl','rtl'),('src/ps','python'),('src/constraints','constraints'),
      ('src/launchers','.'),('build/scripts','scripts'),('sim/benches','sim'),('skill/runtime','skill')]:
        copy_folder(ROOT/source,target/dest)
    copy_folder(ROOT/'build/board_files/pynq-z2/a_0',target/'board_files/pynq-z2/A.0')
    (target/'data').mkdir(exist_ok=True)
    for p in (ROOT/'data/input').iterdir():
        if p.is_file():shutil.copy2(p,target/'data'/('DejaVuSans.ttf' if p.name=='dejavu_sans.ttf' else p.name))
    (target/'out').mkdir(exist_ok=True);(target/'validation').mkdir(exist_ok=True)
    if not (target/'out/manifest.json').exists():
        copy_folder(ROOT/'board/overlay',target/'out')
        copy_folder(ROOT/'build/source_snapshots',target/'out/build_sources')
    # Do not replace newly built hardware with the published prebuilt files.
    return target

def restore_evidence(run,folder=None):
    import numpy as np
    all_records=json.loads((ROOT/'data/evidence/index.json').read_text())
    records={x['run']:x for x in all_records}
    if run not in records:raise ValueError('Unknown evidence run: '+run)
    rec=records[run];archive=ROOT/rec['archive']
    if sha(archive)!=rec['archive_sha256']:raise ValueError('Evidence archive hash mismatch')
    dest=Path(folder) if folder else ROOT/'build/work/evidence'/run
    dest.mkdir(parents=True,exist_ok=True)
    metadata=ROOT/'board/results'/run
    if metadata.exists():copy_folder(metadata,dest)
    with np.load(archive,allow_pickle=False) as z:
        for member in rec['members']:
            raw=z[member['key']].tobytes()
            if len(raw)!=member['bytes'] or hashlib.sha256(raw).hexdigest()!=member['sha256']:raise ValueError('Raw evidence mismatch')
            (dest/member['file']).write_bytes(raw)
    return dest

def verify_evidence():
    import numpy as np
    checked=0;total=0
    for rec in json.loads((ROOT/'data/evidence/index.json').read_text()):
        if sha(ROOT/rec['archive'])!=rec['archive_sha256']:raise ValueError('Compressed evidence hash mismatch')
        with np.load(ROOT/rec['archive'],allow_pickle=False) as z:
            for member in rec['members']:
                raw=z[member['key']].tobytes();assert len(raw)==member['bytes']
                if hashlib.sha256(raw).hexdigest()!=member['sha256']:raise ValueError('Uncompressed evidence hash mismatch')
                checked+=1;total+=len(raw)
    print(json.dumps(dict(status='PASS',raw_files_checked=checked,raw_bytes_checked=total)))

def vivado_path(explicit):
    if explicit:return explicit
    candidates=[shutil.which('vivado'),shutil.which('vivado.bat')]
    if os.environ.get('XILINX_VIVADO'):candidates.insert(0,str(Path(os.environ['XILINX_VIVADO'])/'bin/vivado.bat'))
    for c in candidates:
        if c and Path(c).exists():return c
    raise RuntimeError('Pass --vivado with the full Vivado executable path')

def export_board(path):
    rt=prepare_runtime();path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    selected=[]
    for folder in ['python','data','out']:
        for p in sorted((rt/folder).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and 'build_sources' not in p.parts:selected.append(p)
    selected += [rt/name for name in ['run_demo.py','black_screen.py','01_hdmi_test.ipynb'] if (rt/name).exists()]
    selected += [rt/'01_run_demo.ipynb']
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in selected:z.write(p,'award_video/'+p.relative_to(rt).as_posix())
    print('Board package:',path)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','check','simulate','hardware','all','verify-evidence','restore','recheck','export-board'])
    p.add_argument('--vivado');p.add_argument('--run',default='final_gc_release');p.add_argument('--output')
    a=p.parse_args()
    if a.command=='verify-evidence':verify_evidence();return
    if a.command=='restore':print(restore_evidence(a.run,a.output));return
    if a.command=='export-board':export_board(a.output or ROOT/'build/work/award_video_board.zip');return
    rt=prepare_runtime()
    if a.command=='prepare':print('Runtime ready:',rt);return
    if a.command=='check':
        subprocess.run([sys.executable,'-m','unittest','discover','-s','sim','-p','test_*.py','-v'],cwd=rt,check=True)
        subprocess.run([sys.executable,'skill/scripts/check_examples.py'],cwd=rt,check=True)
        subprocess.run([sys.executable,'scripts/export_manifest.py'],cwd=rt,check=True)
    elif a.command=='recheck':
        folder=restore_evidence(a.run,a.output)
        subprocess.run([sys.executable,'scripts/recheck_results.py',str(folder)],cwd=rt,check=True)
    else:
        script={'simulate':'run_simulation.tcl','hardware':'build_hardware.tcl','all':'build_all.tcl'}[a.command]
        env=dict(os.environ);env['AWARD_PYTHON']=sys.executable
        subprocess.run([vivado_path(a.vivado),'-mode','batch','-source',str(rt/'scripts'/script)],cwd=rt,env=env,check=True)
if __name__=='__main__':main()
