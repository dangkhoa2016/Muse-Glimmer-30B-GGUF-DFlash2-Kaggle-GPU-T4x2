#!/usr/bin/env python3
"""Package a proven llama.cpp build into an attachable Kaggle runtime directory."""
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path
from runtime_manifest import REQUIRED_BINARIES, create_manifest


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--bin-dir', type=Path, required=True)
    ap.add_argument('--lib-dir', type=Path)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--repo', required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--cuda-architectures', required=True)
    ap.add_argument('--cuda-version', default='')
    args=ap.parse_args()
    out=args.output_dir
    if out.exists(): shutil.rmtree(out)
    dst_bin=out/'build/bin'; dst_bin.mkdir(parents=True)
    for name in REQUIRED_BINARIES:
        src=args.bin_dir/name
        if not src.is_file(): raise SystemExit(f'ERROR: required binary missing: {src}')
        shutil.copy2(src, dst_bin/name)
        (dst_bin/name).chmod((dst_bin/name).stat().st_mode | 0o111)
    if args.lib_dir and args.lib_dir.is_dir():
        shutil.copytree(args.lib_dir, out/'build/lib')
    manifest=create_manifest(dst_bin,args.repo,args.commit,args.cuda_architectures,args.cuda_version)
    (out/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    files=[p for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS']
    (out/'SHA256SUMS').write_text(''.join(f'{sha256(p)}  {p.relative_to(out).as_posix()}\n' for p in files),encoding='utf-8')
    print(out)

if __name__=='__main__': main()
