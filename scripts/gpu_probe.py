#!/usr/bin/env python3
import argparse
import csv
import json
import subprocess
from pathlib import Path

QUERY = 'index,name,memory.total,driver_version,pci.bus_id'


def parse_nvidia_smi_csv(text: str):
    rows = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        parts = next(csv.reader([raw], skipinitialspace=True))
        if len(parts) != 5:
            raise ValueError(f'line {lineno}: expected 5 CSV fields, got {len(parts)}')
        index, name, memory_total, driver, pci = (p.strip() for p in parts)
        try:
            idx = int(index)
            mem = int(float(memory_total))
        except ValueError as exc:
            raise ValueError(f'line {lineno}: invalid numeric field: {exc}') from exc
        rows.append({
            'index': idx,
            'name': name,
            'memory_total_mib': mem,
            'driver_version': driver,
            'pci_bus_id': pci,
        })
    return rows


def validate_gpus(gpus, min_count: int, min_vram_mib: int):
    errors = []
    if len(gpus) < min_count:
        errors.append(f'expected at least {min_count} visible GPUs, found {len(gpus)}')
    for gpu in gpus[:min_count]:
        if gpu['memory_total_mib'] < min_vram_mib:
            errors.append(
                f"GPU {gpu['index']} has {gpu['memory_total_mib']} MiB VRAM; "
                f'minimum is {min_vram_mib} MiB'
            )
    return errors


def query_gpus():
    cmd = [
        'nvidia-smi',
        f'--query-gpu={QUERY}',
        '--format=csv,noheader,nounits',
    ]
    proc = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return parse_nvidia_smi_csv(proc.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-count', type=int, default=2)
    ap.add_argument('--min-vram-mib', type=int, default=14000)
    ap.add_argument('--output')
    args = ap.parse_args()

    try:
        gpus = query_gpus()
        errors = validate_gpus(gpus, args.min_count, args.min_vram_mib)
        payload = {
            'ok': not errors,
            'required_count': args.min_count,
            'minimum_vram_mib': args.min_vram_mib,
            'gpu_count': len(gpus),
            'gpus': gpus,
            'errors': errors,
        }
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        payload = {
            'ok': False,
            'required_count': args.min_count,
            'minimum_vram_mib': args.min_vram_mib,
            'gpu_count': 0,
            'gpus': [],
            'errors': [str(exc)],
        }

    rendered = json.dumps(payload, indent=2) + '\n'
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    raise SystemExit(0 if payload['ok'] else 2)


if __name__ == '__main__':
    main()
