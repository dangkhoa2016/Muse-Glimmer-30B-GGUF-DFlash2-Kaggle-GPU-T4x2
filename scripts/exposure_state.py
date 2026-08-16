#!/usr/bin/env python3
"""Exposure lifecycle state with PID-reuse-safe ownership and safe shutdown."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "stale", "state_error": f"{type(exc).__name__}: {exc}"}
    return value if isinstance(value, dict) else {"status": "stale", "state_error": "state root is not object"}


def proc_identity(pid: int, command_token: str = "") -> tuple[str, str] | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    if len(stat) < 22 or stat[2] == "Z" or not cmdline:
        return None
    if command_token and command_token.encode() not in cmdline:
        return None
    return stat[21], hashlib.sha256(cmdline).hexdigest()


def capture_identity(pid: int, token: str, timeout: float = 1.0) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        ident = proc_identity(pid, token)
        if ident is not None:
            return {"pid": pid, "pid_start_ticks": ident[0], "command_sha256": ident[1]}
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.02)


def record_owned(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    pid = record.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    ident = proc_identity(pid)
    if ident is None:
        return False
    return str(record.get("pid_start_ticks", "")) == ident[0] and str(record.get("command_sha256", "")) == ident[1]


def status_report(path):
    data = load_state(path)
    if not data:
        return {"status": "stopped", "proxy_owned": False, "tunnel_owned": False, "state_file": str(path)}
    if data.get("status") == "stopped":
        out = dict(data); out.update(status="stopped", proxy_owned=False, tunnel_owned=False, state_file=str(path)); return out
    proxy_owned = record_owned(data.get("proxy"))
    tunnel_owned = record_owned(data.get("tunnel"))
    stored = str(data.get("status") or "stale")
    mode = str(data.get("mode") or "")
    if mode == "proxy":
        if not proxy_owned or tunnel_owned:
            status = "stale"
        elif stored in {"starting", "proxy-ready", "stopping"}:
            status = stored
        else:
            status = "stale"
    elif not proxy_owned or not tunnel_owned:
        status = "stale"
    elif stored in {"starting", "ready", "stopping"}:
        status = stored
    else:
        status = "stale"
    out = dict(data)
    out.update(status=status, proxy_owned=proxy_owned, tunnel_owned=tunnel_owned, state_file=str(path))
    return out



def print_report(report: dict[str, Any], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report, indent=2, sort_keys=True)); return
    mapping = [
        ("STATUS", "status"), ("MODE", "mode"), ("PUBLIC_URL", "public_url"),
        ("BACKEND_URL", "backend_url"), ("PROXY_URL", "proxy_url"),
        ("PROXY_OWNED", "proxy_owned"), ("TUNNEL_OWNED", "tunnel_owned"),
        ("AUTH_ENABLED", "auth_enabled"), ("STATE_FILE", "state_file"),
        ("PROXY_LOG", "proxy_log"), ("TUNNEL_LOG", "tunnel_log"),
    ]
    for label, key in mapping:
        value = report.get(key, "")
        if isinstance(value, bool): value = "1" if value else "0"
        print(f"{label}={value}")
    for role in ("proxy", "tunnel"):
        rec = report.get(role) if isinstance(report.get(role), dict) else {}
        print(f"{role.upper()}_PID={rec.get('pid', '')}")


def cmd_begin(args):
    proxy = capture_identity(args.proxy_pid, args.proxy_command_token, args.command_timeout)
    if proxy is None:
        print("ERROR: unable to capture owned proxy process identity", file=sys.stderr)
        return 40
    if args.mode == "proxy":
        tunnel = {}
    else:
        tunnel = capture_identity(args.tunnel_pid, args.tunnel_command_token, args.command_timeout)
        if tunnel is None:
            print("ERROR: unable to capture owned tunnel process identity", file=sys.stderr)
            return 40
    data = {
        "schema_version": 1, "status": "starting", "mode": args.mode,
        "backend_url": args.backend_url, "proxy_url": args.proxy_url,
        "proxy": proxy, "tunnel": tunnel, "public_url": "",
        "auth_enabled": True, "started_at": iso_now(),
        "proxy_log": args.proxy_log or "", "tunnel_log": args.tunnel_log or "",
    }
    atomic_write(Path(args.state), data)
    return 0



def cmd_mark_ready(args):
    path = Path(args.state); data = load_state(path)
    if str(data.get("mode") or "") == "proxy":
        print("ERROR: proxy mode must use mark-proxy-ready", file=sys.stderr)
        return 41
    if not record_owned(data.get("proxy")) or not record_owned(data.get("tunnel")):
        print("ERROR: cannot mark exposure ready without both owned processes", file=sys.stderr)
        return 41
    if not args.public_url.startswith("https://"):
        print("ERROR: public URL must use https://", file=sys.stderr)
        return 42
    data["status"] = "ready"; data["public_url"] = args.public_url
    data["ready_at"] = iso_now()
    atomic_write(path, data); return 0
def cmd_mark_proxy_ready(args):
    path = Path(args.state); data = load_state(path)
    if str(data.get("mode") or "") != "proxy":
        print("ERROR: mark-proxy-ready requires mode=proxy", file=sys.stderr)
        return 43
    proxy_url = str(data.get("proxy_url") or "")
    if not proxy_url.startswith("http://127.0.0.1:"):
        print("ERROR: proxy mode requires a loopback proxy URL", file=sys.stderr)
        return 44
    if not record_owned(data.get("proxy")) or record_owned(data.get("tunnel")):
        print("ERROR: proxy-ready requires owned proxy and no owned tunnel", file=sys.stderr)
        return 45
    data["status"] = "proxy-ready"; data["public_url"] = ""
    data["ready_at"] = iso_now()
    atomic_write(path, data); return 0




def still_same(record: dict[str, Any]) -> bool:
    return record_owned(record)


def terminate_records(records: list[dict[str, Any]], timeout: float) -> None:
    owned = [record for record in records if record_owned(record)]
    for record in owned:
        try: os.kill(int(record["pid"]), signal.SIGTERM)
        except ProcessLookupError: pass
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline and any(still_same(r) for r in owned):
        time.sleep(0.02)
    for record in owned:
        if still_same(record):
            try: os.kill(int(record["pid"]), signal.SIGKILL)
            except ProcessLookupError: pass


def cmd_stop_owned(args: argparse.Namespace) -> int:
    path = Path(args.state); data = load_state(path)
    records = []
    # Tunnel first: remove Internet ingress before local auth proxy.
    for role in ("tunnel", "proxy"):
        rec = data.get(role)
        if isinstance(rec, dict): records.append(rec)
    if data:
        data["status"] = "stopping"; atomic_write(path, data)
    terminate_records(records, args.timeout)
    if not data: data = {}
    data["status"] = "stopped"; data["stopped_at"] = iso_now(); data["proxy"] = {}; data["tunnel"] = {}
    atomic_write(path, data)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print_report(status_report(Path(args.state)), args.format)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("begin")
    p.add_argument("--state", required=True); p.add_argument("--mode", choices=["quick", "named", "proxy"], required=True)
    p.add_argument("--backend-url", required=True); p.add_argument("--proxy-url", required=True)
    p.add_argument("--proxy-pid", type=int, required=True); p.add_argument("--proxy-command-token", default="auth_proxy.py")
    p.add_argument("--tunnel-pid", type=int, default=0); p.add_argument("--tunnel-command-token", default="cloudflared")
    p.add_argument("--proxy-log", default=""); p.add_argument("--tunnel-log", default=""); p.add_argument("--command-timeout", type=float, default=1.0)
    p.set_defaults(func=cmd_begin)

    p = sub.add_parser("mark-ready")
    p.add_argument("--state", required=True); p.add_argument("--public-url", required=True); p.set_defaults(func=cmd_mark_ready)

    p = sub.add_parser("mark-proxy-ready")
    p.add_argument("--state", required=True); p.set_defaults(func=cmd_mark_proxy_ready)

    p = sub.add_parser("status")
    p.add_argument("--state", required=True); p.add_argument("--format", choices=["env", "json"], default="env"); p.set_defaults(func=cmd_status)

    p = sub.add_parser("stop-owned")
    p.add_argument("--state", required=True); p.add_argument("--timeout", type=float, default=5.0); p.set_defaults(func=cmd_stop_owned)

    args = ap.parse_args(); return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

# proxy/BYO state
