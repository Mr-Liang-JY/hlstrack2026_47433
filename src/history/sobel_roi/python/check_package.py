"""Verify delivered file hashes; does not write or fabricate board results."""
from pathlib import Path
import argparse
import hashlib
import json

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    args=parser.parse_args()
    root=Path(args.root).resolve()
    manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    mismatches=[]
    for filename,expected in manifest['files_sha256'].items():
        path=root/filename
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            mismatches.append(filename)
    if mismatches:raise ValueError('Missing/modified files: '+repr(mismatches))
    print('PACKAGE HASH CHECK PASSED (%d files)'%len(manifest['files_sha256']))
    print('Scope: packaged source/data/build evidence integrity; physical PYNQ test is separate.')
if __name__=='__main__':main()
