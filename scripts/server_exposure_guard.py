#!/usr/bin/env python3
"""Fail closed when the benchmark server is configured to bind off-loopback."""
from __future__ import annotations

import argparse
import ipaddress
import sys


def is_loopback_host(host: str) -> bool:
    value = host.strip().lower()
    if value == 'localhost':
        return True
    if value.startswith('[') and value.endswith(']'):
        value = value[1:-1]
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check-bind')
    check.add_argument('--host', required=True)
    check.add_argument('--allow-nonloopback', required=True)
    args = parser.parse_args()

    if args.command != 'check-bind':
        parser.error('unsupported command')
    if args.allow_nonloopback not in {'0', '1'}:
        print('ERROR: --allow-nonloopback must be 0 or 1', file=sys.stderr)
        return 2
    if is_loopback_host(args.host):
        return 0
    if args.allow_nonloopback == '1':
        print(
            f"WARNING: non-loopback server bind explicitly allowed: {args.host}. "
            "Do not expose this benchmark server directly to the Internet; put authentication and CORS policy at a trusted reverse proxy/tunnel.",
            file=sys.stderr,
        )
        return 0
    print(
        f"ERROR: refusing non-loopback SERVER_HOST={args.host!r}. "
        "The benchmark server is unauthenticated by default. Keep SERVER_HOST on loopback, "
        "or set SERVER_ALLOW_NONLOOPBACK=1 only for an explicitly protected network/reverse-proxy path.",
        file=sys.stderr,
    )
    return 3


if __name__ == '__main__':
    raise SystemExit(main())
