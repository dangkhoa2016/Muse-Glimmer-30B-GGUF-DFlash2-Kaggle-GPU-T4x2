#!/usr/bin/env python3
import argparse
import errno
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    stat = Path(f"/proc/{pid}/stat")
    try:
        parts = stat.read_text(encoding="utf-8").split()
    except OSError:
        return True
    return len(parts) >= 3 and parts[2] != "Z"


def port_free(host: str, port: int) -> int:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        result = sock.connect_ex((host, port))
    except OSError as exc:
        print(f"ERROR: unable to verify server port {host}:{port}: {exc}", file=sys.stderr)
        return 12
    finally:
        sock.close()
    if result == 0:
        print(f"ERROR: server port {host}:{port} already in use by an active listener", file=sys.stderr)
        return 12
    if result == errno.ECONNREFUSED:
        return 0
    print(
        f"ERROR: unable to verify server port {host}:{port}: {os.strerror(result)}",
        file=sys.stderr,
    )
    return 12


def wait_ready(pid: int, urls: list[str], timeout: float, interval: float) -> int:
    deadline = time.monotonic() + timeout
    last_error = "no readiness response"
    while time.monotonic() < deadline:
        if not pid_running(pid):
            print(f"ERROR: owned server PID {pid} exited before readiness", file=sys.stderr)
            return 10
        for url in urls:
            try:
                remaining = max(0.1, min(2.0, deadline - time.monotonic()))
                with urllib.request.urlopen(url, timeout=remaining) as response:
                    if 200 <= response.status < 400:
                        if not pid_running(pid):
                            print(f"ERROR: owned server PID {pid} exited while readiness endpoint was healthy", file=sys.stderr)
                            return 10
                        print(f"ready pid={pid} url={url}")
                        return 0
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(interval)
    print(f"ERROR: server readiness timeout for owned PID {pid}: {last_error}", file=sys.stderr)
    return 11


def main() -> int:
    parser = argparse.ArgumentParser(description="Server ownership and readiness guard")
    sub = parser.add_subparsers(dest="command", required=True)

    p_port = sub.add_parser("port-free")
    p_port.add_argument("--host", required=True)
    p_port.add_argument("--port", required=True, type=int)

    p_ready = sub.add_parser("wait-ready")
    p_ready.add_argument("--pid", required=True, type=int)
    p_ready.add_argument("--url", action="append", required=True)
    p_ready.add_argument("--timeout", required=True, type=float)
    p_ready.add_argument("--interval", type=float, default=1.0)

    args = parser.parse_args()
    if args.command == "port-free":
        return port_free(args.host, args.port)
    return wait_ready(args.pid, args.url, args.timeout, args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
