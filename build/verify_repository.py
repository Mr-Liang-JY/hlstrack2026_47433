"""Validate naming, privacy, immutable hardware/software and publishable file sizes."""
from pathlib import Path
import argparse,hashlib,json,os,re,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
TEXT={'.py','.v','.sv','.tcl','.xdc','.json','.jsonl','.csv','.txt','.rpt','.log','.xml','.md','.ipynb','.mem'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files():
 for p in ROOT.rglob('*'):
  rel=p.relative_to(ROOT)
  if any(part in ['.git','.venv','__pycache__','.ipynb_checkpoints'] for part in rel.parts):continue
  if rel.parts[:2]==('build','work'):continue
  if p.is_file():yield p

def inspect(data,label):
 text=data.decode('utf-8-sig')
 patterns=[r'(?i)[a-z]:[\\/]+Users[\\/]+[^\\/\s\"\']+',r'\b192\.168\.\d{1,3}\.\d{1,3}\b',
           r'wxid_[a-zA-Z0-9_]+',r'gh[pousr]_[a-zA-Z0-9]{20,}',r'sk-[a-zA-Z0-9]{24,}']
 for pattern in patterns:
  if re.search(pattern,text):raise ValueError('Private data pattern in '+label)
 for private in [Path.home().name,os.environ.get('COMPUTERNAME','')]:
  if len(private)>4 and private.lower() in text.lower():raise ValueError('Local identity in '+label)
 if re.search(r'(?mi)^\| Host\s*:\s*(?!\[redacted\])\S',text):raise ValueError('Unredacted tool host')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true');a=parser.parse_args()
 items=list(files());largest=[]
 for p in items:
  rel=p.relative_to(ROOT)
  for part in rel.parts:
   if part in ['.gitignore','.gitattributes']:continue
   if not re.fullmatch(r'[a-z0-9_-]+(?:\.[a-z0-9_-]+)*',part):raise ValueError('Invalid filename: '+rel.as_posix())
  if p.stat().st_size>=25*1024**2:raise ValueError('File is too large for selected publication policy: '+rel.as_posix())
  largest.append((p.stat().st_size,rel.as_posix()))
  if p.suffix in TEXT:inspect(p.read_bytes(),rel.as_posix())
  if p.suffix=='.md':
   text=p.read_text(encoding='utf-8-sig')
   for dest in re.findall(r'\[[^\]\n]+\]\(([^)]+)\)',text):
    if re.match(r'^[a-z]+:',dest) or dest.startswith('#'):continue
    local=dest.split('#',1)[0].strip('<>')
    if local and not (p.parent/local).exists():raise ValueError('Broken Markdown link: '+rel.as_posix()+' -> '+local)
 manifest=json.loads((ROOT/'board/overlay/manifest.json').read_text(encoding='utf-8'))
 for name,value in manifest['hardware_sha256'].items():assert sha(ROOT/'board/overlay'/name)==value
 for name,value in manifest['sources_sha256'].items():
  parts=Path(name).parts;path=ROOT/('src/rtl' if parts[0]=='rtl' else 'src/constraints')/parts[-1]
  assert sha(path)==value, 'Stale hardware source '+name
 software=json.loads((ROOT/'board/results/final_gc_release/software_sha256.json').read_text())
 for name,value in software.items():assert sha(ROOT/'src/ps'/Path(name).name)==value
 package=ROOT/'board/packages/award_video_runtime.zip'
 expected=json.loads((ROOT/'build/runtime_map.json').read_text())['verified_board_package_sha256'];assert sha(package)==expected
 with zipfile.ZipFile(package) as z:
  assert z.testzip() is None
  for name in z.namelist():
   assert not name.startswith('/') and '..' not in Path(name).parts
   if Path(name).suffix in TEXT:inspect(z.read(name),'runtime.zip/'+name)
 archives=json.loads((ROOT/'data/evidence/index.json').read_text())
 for rec in archives:assert sha(ROOT/rec['archive'])==rec['archive_sha256']
 if a.full:
  import importlib.util
  spec=importlib.util.spec_from_file_location('reproduce',ROOT/'build/reproduce.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.verify_evidence()
 result=dict(status='PASS',files=len(items),naming='lowercase ASCII',privacy='checked text and runtime ZIP',
   max_file_bytes=max(x[0] for x in largest),total_file_bytes=sum(x[0] for x in largest),
   hardware_and_source_hashes='PASS',software_source_hashes='PASS',verified_board_zip_hash='PASS',
   evidence_archives=len(archives),largest_files=[dict(file=n,bytes=s) for s,n in sorted(largest,reverse=True)[:8]])
 (ROOT/'report/repository_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
