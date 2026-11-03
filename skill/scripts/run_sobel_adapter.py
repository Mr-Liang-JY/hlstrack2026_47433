from pathlib import Path
import importlib.util,subprocess,sys
r=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('reproduce',r/'build/reproduce.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
if __name__=='__main__':
 a=sys.argv[1:]
 if '--output' in a:
  i=a.index('--output')+1;a[i]=str(Path(a[i]).resolve())
 t=m.prepare_runtime();subprocess.run([sys.executable,str(t/'skill/scripts/run_sobel_adapter.py'),*a],cwd=t,check=True)
