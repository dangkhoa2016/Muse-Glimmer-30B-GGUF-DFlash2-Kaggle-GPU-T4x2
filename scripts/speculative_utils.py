#!/usr/bin/env python3
import argparse
import subprocess
import sys

REQUIRED_DFLASH_CAPABILITIES = [
    'draft-dflash',
    '--spec-draft-model',
    '--spec-draft-threads',
    '--spec-draft-threads-batch',
    '--spec-draft-n-max',
    '--spec-draft-n-min',
    '--spec-draft-p-min',
    '--spec-draft-ngl',
    '--spec-draft-device',
]


def missing_dflash_capabilities(help_text: str | None) -> list[str]:
    text = help_text or ''
    return [token for token in REQUIRED_DFLASH_CAPABILITIES if token not in text]


def build_dflash_args(
    model_path,
    draft_threads,
    draft_batch_threads,
    n_max,
    n_min,
    p_min,
    draft_gpu_layers,
    draft_device='',
):
    args = [
        '--spec-type', 'draft-dflash',
        '--spec-draft-model', str(model_path),
        '--spec-draft-threads', str(draft_threads),
        '--spec-draft-threads-batch', str(draft_batch_threads),
        '--spec-draft-n-max', str(n_max),
        '--spec-draft-n-min', str(n_min),
        '--spec-draft-p-min', str(p_min),
        '--spec-draft-ngl', str(draft_gpu_layers),
    ]
    if str(draft_device or '').strip():
        args += ['--spec-draft-device', str(draft_device).strip()]
    return args


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check-help')
    c.add_argument('--server', required=True)
    e = sub.add_parser('emit-args')
    e.add_argument('--model', required=True)
    e.add_argument('--draft-threads', required=True, type=int)
    e.add_argument('--draft-batch-threads', required=True, type=int)
    e.add_argument('--n-max', required=True, type=int)
    e.add_argument('--n-min', required=True, type=int)
    e.add_argument('--p-min', required=True, type=float)
    e.add_argument('--draft-gpu-layers', required=True)
    e.add_argument('--draft-device', default='')
    e.add_argument('--null', action='store_true')
    args = ap.parse_args()

    if args.cmd == 'check-help':
        proc = subprocess.run(
            [args.server, '--help'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        missing = missing_dflash_capabilities(proc.stdout)
        if missing:
            print(
                'ERROR: llama-server lacks required GPU DFlash capabilities: ' + ', '.join(missing),
                file=sys.stderr,
            )
            return 3
        print('GPU DFlash capabilities: OK')
        return 0

    values = build_dflash_args(
        args.model,
        args.draft_threads,
        args.draft_batch_threads,
        args.n_max,
        args.n_min,
        args.p_min,
        args.draft_gpu_layers,
        args.draft_device,
    )
    if args.null:
        for value in values:
            sys.stdout.buffer.write(str(value).encode('utf-8') + b'\0')
    else:
        print('\n'.join(values))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
