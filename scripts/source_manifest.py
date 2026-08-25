#!/usr/bin/env python3
import argparse, hashlib, sys
from pathlib import Path

ROOT_FILES={'.gitignore','README.md','README.vi.md','CHANGELOG.md','CHANGELOG.vi.md','VERSION','package-llama-runtime.sh','serve.sh','expose.sh','external.sh','doctor.sh','release-export.sh','readiness.sh','demo-smoke.sh'}
ROOT_DIRS={'config','scripts','tests'}
EXCLUDE_DIRS={'__pycache__','.git','.venv','vendor','models','runs','artifacts','comparisons'}
EXCLUDE_SUFFIXES={'.pyc','.pyo'}
EXCLUDE_NAMES={'SOURCE_MANIFEST.sha256'}

def source_files(root:Path):
    out=[]
    for name in sorted(ROOT_FILES):
        p=root/name
        if p.is_file(): out.append(p)
    for d in sorted(ROOT_DIRS):
        base=root/d
        if not base.is_dir(): continue
        for p in sorted(base.rglob('*')):
            if not p.is_file(): continue
            rel=p.relative_to(root)
            if any(part in EXCLUDE_DIRS for part in rel.parts): continue
            if p.name in EXCLUDE_NAMES or p.suffix in EXCLUDE_SUFFIXES: continue
            out.append(p)
    return sorted(set(out),key=lambda p:p.relative_to(root).as_posix())

def sha256(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def render(root:Path): return ''.join(f'{sha256(p)}  {p.relative_to(root).as_posix()}\n' for p in source_files(root))
def parse_manifest(path:Path):
    rows={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            digest,rel=line.split(None,1); rows[rel.strip()]=digest
    return rows
def check(root:Path,manifest:Path):
    expected=parse_manifest(manifest); actual={p.relative_to(root).as_posix():sha256(p) for p in source_files(root)}
    missing=sorted(set(expected)-set(actual)); extra=sorted(set(actual)-set(expected)); changed=sorted(k for k in set(expected)&set(actual) if expected[k]!=actual[k])
    for k in missing: print(f'MISSING  {k}')
    for k in extra: print(f'EXTRA    {k}')
    for k in changed: print(f'CHANGED  {k}')
    ok=not(missing or extra or changed); print(f"SOURCE_MANIFEST: {'OK' if ok else 'FAILED'} files={len(actual)} changed={len(changed)} missing={len(missing)} extra={len(extra)}"); return ok

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    for name in ('write','check'):
        p=sub.add_parser(name); p.add_argument('--root',default=str(Path(__file__).resolve().parents[1])); p.add_argument('--output',default=None)
    a=ap.parse_args(); root=Path(a.root).resolve(); output=Path(a.output).resolve() if a.output else root/'SOURCE_MANIFEST.sha256'
    if a.cmd=='write': output.parent.mkdir(parents=True,exist_ok=True); output.write_text(render(root),encoding='utf-8'); print(output); return
    if not output.exists(): print(f'SOURCE_MANIFEST missing: {output}',file=sys.stderr); raise SystemExit(2)
    raise SystemExit(0 if check(root,output) else 3)
if __name__=='__main__': main()
