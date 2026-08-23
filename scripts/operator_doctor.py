#!/usr/bin/env python3
"""Read-only operator doctor built on the operator status authority."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1


def load_operator_status(root: Path):
    path = root / "scripts" / "operator_status.py"
    spec = importlib.util.spec_from_file_location("operator_status", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load status authority: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def manifest_summary(root: Path, skip: bool) -> dict:
    manifest = root / "SOURCE_MANIFEST.sha256"
    digest = file_sha256(manifest) if manifest.is_file() else ""
    if skip:
        return {"manifest_sha256": digest, "manifest_status": "NOT_CHECKED"}
    checker = root / "scripts" / "source_manifest.py"
    if not manifest.is_file() or not checker.is_file():
        return {"manifest_sha256": digest, "manifest_status": "MISSING"}
    p = subprocess.run(
        [sys.executable, str(checker), "check", "--root", str(root)],
        cwd=root,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"manifest_sha256": digest, "manifest_status": "PASS" if p.returncode == 0 else "FAIL"}


def listener_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def listener_summary(skip: bool) -> dict:
    if skip:
        return {"backend_8088": None, "proxy_8090": None}
    return {
        "backend_8088": listener_open("127.0.0.1", 8088),
        "proxy_8090": listener_open("127.0.0.1", 8090),
    }


def gpu_summary(skip: bool) -> dict:
    if skip:
        return {"probe_status": "NOT_CHECKED", "count": None, "devices": []}
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {"probe_status": "UNAVAILABLE", "count": 0, "devices": []}
    p = subprocess.run(
        [nvidia_smi, "--query-gpu=index,name", "--format=csv,noheader,nounits"],
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        return {"probe_status": "ERROR", "count": None, "devices": []}
    devices = [line.strip() for line in p.stdout.splitlines() if line.strip()]
    return {"probe_status": "PASS", "count": len(devices), "devices": devices}


def acceptance_summary(path: str | None) -> dict:
    if not path:
        return {"status": "", "timestamp": ""}
    p = Path(path)
    if not p.is_file():
        raise RuntimeError(f"acceptance result not found: {p}")
    allowed = {"FINAL_ACCEPTANCE", "TIMESTAMP", "ACCEPTANCE_TIMESTAMP", "RUN_TIMESTAMP"}
    values: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if key in allowed:
            values[key] = value.strip()
    return {
        "status": values.get("FINAL_ACCEPTANCE", ""),
        "timestamp": values.get("TIMESTAMP") or values.get("ACCEPTANCE_TIMESTAMP") or values.get("RUN_TIMESTAMP", ""),
    }


def recommended_action(doc: dict) -> str:
    state = doc["operator_state"]
    if state == "stopped":
        return "run ./external.sh start"
    if state == "backend-only":
        return "run ./external.sh start to enable authenticated ingress"
    if state == "proxy-ready":
        return "connect BYO HTTPS ingress to http://127.0.0.1:8090"
    if state == "public-ready":
        return "service is ready"
    if state == "starting":
        return "wait for lifecycle readiness"
    return "inspect diagnostics and lifecycle status before restarting"


def build_doctor_document(root: Path, args) -> dict:
    status_module = load_operator_status(root)
    if bool(args.external_status_file) != bool(args.backend_status_file):
        raise RuntimeError("provide both --external-status-file and --backend-status-file, or neither")
    if args.external_status_file:
        external_text = status_module.read_status_file(Path(args.external_status_file))
        backend_text = status_module.read_status_file(Path(args.backend_status_file))
    else:
        external_text = status_module.run_status(root, "external.sh")
        backend_text = status_module.run_status(root, "serve.sh")
    version_file = root / "VERSION"
    version = version_file.read_text(encoding="utf-8", errors="replace").strip() if version_file.is_file() else ""
    doc = status_module.build_document(status_module.parse_env(external_text), status_module.parse_env(backend_text), version)
    doc["schema_version"] = SCHEMA_VERSION
    doc["listeners"] = listener_summary(args.skip_listener_probe)
    doc["gpu"] = gpu_summary(args.skip_gpu_probe)
    doc["source"] = manifest_summary(root, args.skip_manifest_check)
    doc["last_acceptance"] = acceptance_summary(args.acceptance_result)
    doc["recommended_action"] = recommended_action(doc)
    return doc


def render_env(doc: dict) -> str:
    fields = {
        "SCHEMA_VERSION": doc["schema_version"],
        "RELEASE_VERSION": doc["release_version"],
        "OPERATOR_STATE": doc["operator_state"],
        "MODE": doc["mode"],
        "BACKEND_OWNED": int(doc["ownership"]["backend"]),
        "PROXY_OWNED": int(doc["ownership"]["proxy"]),
        "TUNNEL_OWNED": int(doc["ownership"]["tunnel"]),
        "BACKEND_HEALTHY": int(doc["health"]["backend"]),
        "AUTH_ENABLED": int(doc["health"]["auth_enabled"]),
        "BACKEND_STATUS": doc["backend"]["status"],
        "BACKEND_PROVENANCE": doc["backend"]["provenance"],
        "TARGET_SHA256": doc["backend"]["target_sha256"],
        "DRAFT_SHA256": doc["backend"]["draft_sha256"],
        "RUNTIME_COMMIT": doc["backend"]["runtime_commit"],
        "LOCAL_PROXY_URL": doc["ingress"]["local_proxy_url"],
        "PUBLIC_URL": doc["ingress"]["public_url"],
        "SOURCE_MANIFEST_SHA256": doc["source"]["manifest_sha256"],
        "SOURCE_MANIFEST_STATUS": doc["source"]["manifest_status"],
        "LAST_ACCEPTANCE_STATUS": doc["last_acceptance"]["status"],
        "LAST_ACCEPTANCE_TIMESTAMP": doc["last_acceptance"]["timestamp"],
        "DIAGNOSTICS": ",".join(doc["diagnostics"]),
        "RECOMMENDED_ACTION": doc["recommended_action"],
    }
    return "".join(f"{key}={value}\n" for key, value in fields.items())


def render_text(doc: dict) -> str:
    gpu = doc["gpu"]
    listeners = doc["listeners"]
    lines = [
        "Muse-Glimmer operator doctor",
        f"Release: {doc['release_version']}",
        f"State: {doc['operator_state']}",
        f"Ownership: backend={int(doc['ownership']['backend'])} proxy={int(doc['ownership']['proxy'])} tunnel={int(doc['ownership']['tunnel'])}",
        f"Backend: status={doc['backend']['status']} healthy={int(doc['health']['backend'])} provenance={doc['backend']['provenance']}",
        f"Listeners: 8088={listeners['backend_8088']} 8090={listeners['proxy_8090']}",
        f"GPU: status={gpu['probe_status']} count={gpu['count']}",
        f"Source manifest: {doc['source']['manifest_status']} sha256={doc['source']['manifest_sha256']}",
        f"Local endpoint: {doc['ingress']['local_proxy_url']}",
        f"Public endpoint: {doc['ingress']['public_url']}",
        f"Diagnostics: {','.join(doc['diagnostics'])}",
        f"Recommended action: {doc['recommended_action']}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only Muse-Glimmer operator doctor")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--external-status-file")
    ap.add_argument("--backend-status-file")
    ap.add_argument("--acceptance-result")
    ap.add_argument("--skip-manifest-check", action="store_true")
    ap.add_argument("--skip-gpu-probe", action="store_true")
    ap.add_argument("--skip-listener-probe", action="store_true")
    ap.add_argument("--format", choices=("json", "env", "text"), default="text")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        doc = build_doctor_document(root, args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(doc, indent=2, sort_keys=True))
    elif args.format == "env":
        sys.stdout.write(render_env(doc))
    else:
        sys.stdout.write(render_text(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
