from pathlib import Path
import importlib.util,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reproduce',ROOT/'build/reproduce.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
if __name__=='__main__':
    args=sys.argv[1:]
    for flag in ['--input','--output','--bit']:
        if flag in args:
            index=args.index(flag)+1;args[index]=str(Path(args[index]).resolve())
    runtime=module.prepare_runtime()
    subprocess.run([sys.executable,str(runtime/'run_demo.py'),*args],cwd=runtime,check=True)
