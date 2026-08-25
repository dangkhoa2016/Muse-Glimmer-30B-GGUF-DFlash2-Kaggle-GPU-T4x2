#!/usr/bin/env python3
"""CPU-safe public contract tests (no GPU, model, tunnel, or network).

Asserts deterministic facts about the public tree and the gateway contract so
CI can verify them without any runtime workload.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_VERSION = "1.0.0"
FAILURES = []
TOTAL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global TOTAL
    TOTAL += 1
    status = "ok" if ok else "FAIL"
    print(f"{status}   {name}" + (f" ({detail})" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def main() -> int:
    version = ROOT.joinpath("VERSION").read_text(encoding="utf-8").strip()
    check("project version singleton", version == PUBLIC_VERSION, f"VERSION={version!r}")

    license_text = ROOT.joinpath("LICENSE").read_text(encoding="utf-8")
    check("MIT license header", "MIT License" in license_text)
    check("MIT copyright", "Copyright (c) 2026 Đăng Khoa" in license_text)

    for name in ("README.md", "CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md",
                 "CODE_OF_CONDUCT.md", "SUPPORT.md"):
        check(f"required doc present {name}", ROOT.joinpath(name).is_file())
    for en in ("README", "CHANGELOG", "SECURITY", "CONTRIBUTING",
               "CODE_OF_CONDUCT", "SUPPORT"):
        check(f"required doc present {en}.vi.md", ROOT.joinpath(f"{en}.vi.md").is_file())

    sys.path.insert(0, str(ROOT / "scripts"))
    import demo_policy as P  # noqa: E402

    check("gateway single admission slot", P.MAX_ACTIVE_INFERENCE == 1)
    check("gateway zero queue", P.MAX_QUEUED_INFERENCE == 0)
    check("gateway busy retry-after", P.BUSY_RETRY_AFTER == "5")
    check("gateway error codes", P.ERROR_BUSY == "muse_demo_busy"
          and P.ERROR_AUTH_REQUIRED == "muse_auth_required"
          and P.ERROR_RATE_LIMITED == "muse_rate_limited")
    check("gateway /ready public route allowed", P.ROUTE_ALLOW is None)

    import auth_proxy  # noqa: E402
    check("gateway server version", getattr(auth_proxy.AuthProxyHandler, "server_version", None) == "MuseExternalProxy/1.0.0")

    cfg = ROOT.joinpath("config/default.env").read_text(encoding="utf-8")
    ports = {}
    for line in cfg.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k in ("SERVER_PORT", "SERVER_HOST", "SERVER_ALLOW_NONLOOPBACK", "PARALLEL_SLOTS", "GPU_REQUIRED_COUNT", "GPU_MIN_VRAM_MIB"):
            ports[k] = v
    check("backend loopback port 8088", ports.get("SERVER_PORT") == "8088")
    check("backend loopback host", ports.get("SERVER_HOST") == "127.0.0.1")
    check("backend loopback only", ports.get("SERVER_ALLOW_NONLOOPBACK") == "0")
    check("single parallel slot", ports.get("PARALLEL_SLOTS") == "1")
    check("gpu count 2 / vram 14000",
          ports.get("GPU_REQUIRED_COUNT") == "2" and ports.get("GPU_MIN_VRAM_MIB") == "14000")

    source_manifest = ROOT.joinpath("scripts/source_manifest.py").read_text(encoding="utf-8")
    check("manifest covers tracked root entrypoints",
          all(f"'{n}'" in source_manifest for n in
              ("serve.sh", "expose.sh", "external.sh", "readiness.sh", "doctor.sh",
               "release-export.sh", "demo-smoke.sh", "package-llama-runtime.sh", "VERSION")))
    check("manifest excludes benchmark tooling",
          "run.sh" not in source_manifest and "compare-models.sh" not in source_manifest)

    external_sh = ROOT.joinpath("external.sh").read_text(encoding="utf-8")
    usage = re.search(r"Usage:\s*\./external\.sh \{([^}]+)\}", external_sh)
    known_commands = set()
    if usage:
        known_commands.update(c.strip() for c in usage.group(1).split("|"))
    for m in re.finditer(
        r"^\s*(preflight|start|status|endpoint|local-endpoint|stop|stop-all)\s*\)",
        external_sh, re.M):
        known_commands.add(m.group(1))

    docs = ""
    for name in ("README.md", "README.vi.md", "CHANGELOG.md", "CHANGELOG.vi.md"):
        docs += ROOT.joinpath(name).read_text(encoding="utf-8") + "\n"
    documented = set(re.findall(r"\./external\.sh\s+([a-z][a-z-]*)", docs))
    check("release docs reference only real external.sh commands",
          documented <= known_commands, f"documented={sorted(documented - known_commands)}")
    check("release docs never use invalid ./external.sh expose",
          "external.sh expose" not in docs)
    check("external.sh usage lists the public operator commands",
          {"preflight", "start", "status", "endpoint", "local-endpoint", "stop", "stop-all"}
          <= known_commands)

    print(f"\npassed={TOTAL - len(FAILURES)} failed={len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())