#!/usr/bin/env python3
"""Provider-neutral HTTPS smoke test with always-on, secret-safe evidence packaging."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_MODEL = "muse-glimmer-30B"
DEFAULT_EXPECTED = "MUSE_BYO_OK"


def validate_public_url(value: str) -> str:
    try:
        u = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"invalid public URL: {exc}") from exc
    if u.scheme != "https" or not u.hostname:
        raise ValueError("public URL must be an https:// origin")
    if u.username or u.password:
        raise ValueError("userinfo is forbidden in public URL")
    if u.path not in ("", "/") or u.query or u.fragment:
        raise ValueError("public URL must be a clean HTTPS origin with no path/query/fragment")
    try:
        port = u.port
    except ValueError as exc:
        raise ValueError("invalid public URL port") from exc
    host = u.hostname
    if ":" in host and not host.startswith("["):
        host_fmt = f"[{host}]"
    else:
        host_fmt = host
    return f"https://{host_fmt}{':' + str(port) if port else ''}"


def is_nonpublic_host(host: str) -> bool:
    if host.lower() == "localhost" or host.lower().endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not ip.is_global


def printable_token_ok(token: str) -> bool:
    return len(token) >= 32 and not any(ord(ch) < 32 or ord(ch) == 127 for ch in token)


def safe_text(value: object) -> str:
    return str(value).replace("\r", "\\r").replace("\n", "\\n")


class Evidence:
    def __init__(self, root: Path, token: str):
        self.root = root
        self.token = token
        self.result = root / "result.env"
        root.mkdir(parents=True, exist_ok=True)
        try:
            root.chmod(0o700)
        except OSError:
            pass
        self.result.write_text("", encoding="utf-8")

    def record(self, key: str, value: object) -> None:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError(f"unsafe result key: {key}")
        text = safe_text(value)
        if self.token:
            text = text.replace(self.token, "[REDACTED]")
        with self.result.open("a", encoding="utf-8") as f:
            f.write(f"{key}={text}\n")

    def write_bytes(self, name: str, data: bytes) -> None:
        if self.token:
            data = data.replace(self.token.encode(), b"[REDACTED]")
        # Never persist a literal Bearer credential prefix from a reflected response.
        data = re.sub(br"Authorization:\s*Bearer\s+[^\s\"']+", b"Authorization: [REDACTED]", data, flags=re.I)
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        try:
            p.chmod(0o600)
        except OSError:
            pass

    def sanitize_tree(self) -> int:
        count = 0
        if not self.token:
            return count
        secret = self.token.encode()
        for p in sorted(self.root.rglob("*")):
            if not p.is_file():
                continue
            data = p.read_bytes()
            new = data.replace(secret, b"[REDACTED]")
            new = re.sub(br"Authorization:\s*Bearer\s+[^\s\"']+", b"Authorization: [REDACTED]", new, flags=re.I)
            if new != data:
                p.write_bytes(new)
                count += 1
        return count

    def assert_secret_free(self) -> None:
        secret = self.token.encode() if self.token else b""
        for p in sorted(self.root.rglob("*")):
            if not p.is_file():
                continue
            data = p.read_bytes()
            if secret and secret in data:
                raise RuntimeError(f"secret hygiene failure in {p.name}")
            if re.search(br"Authorization:\s*Bearer\s+", data, flags=re.I):
                raise RuntimeError(f"Authorization header leaked in {p.name}")

    def package(self) -> tuple[Path, str]:
        self.sanitize_tree()
        self.assert_secret_free()
        archive = Path(str(self.root) + ".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(self.root.rglob("*")):
                if not p.is_file():
                    continue
                arc = str(self.root.name + "/" + p.relative_to(self.root).as_posix())
                zi = zipfile.ZipInfo(arc, (1980, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o100600 << 16
                z.writestr(zi, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        sidecar = Path(str(archive) + ".sha256")
        sidecar.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        return archive, digest


def make_ssl_context(ca_file: str | None) -> ssl.SSLContext:
    return ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()


def request_once(url: str, method: str, token: str | None, body: bytes | None, timeout: float, ctx: ssl.SSLContext) -> tuple[int, bytes]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return int(r.status), r.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def request_with_retries(url: str, method: str, token: str | None, body: bytes | None, timeout: float, ctx: ssl.SSLContext, attempts: int, delay: float, evidence: Evidence, stage: str) -> tuple[int, bytes]:
    last_code = 0
    last_body = b""
    for attempt in range(1, attempts + 1):
        try:
            code, data = request_once(url, method, token, body, timeout, ctx)
            last_code, last_body = code, data
            evidence.write_bytes(f"{stage}.attempt-{attempt}.json", data)
            evidence.write_bytes(f"{stage}.attempt-{attempt}.meta", f"attempt={attempt}\nhttp={code}\n".encode())
            # 5xx is transport/provider retryable; 4xx is normally contractual.
            if code < 500:
                return code, data
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as exc:
            evidence.write_bytes(f"{stage}.attempt-{attempt}.meta", f"attempt={attempt}\nnetwork_error={type(exc).__name__}\n".encode())
        if attempt < attempts:
            time.sleep(delay)
    return last_code, last_body


def default_evidence_dir() -> Path:
    base = Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path.cwd()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return base / f"muse-byo-public-smoke-{stamp}-{os.getpid()}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Provider-neutral public HTTPS smoke with failure evidence")
    ap.add_argument("--public-url", required=True)
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument("--expected-model", default=DEFAULT_MODEL)
    ap.add_argument("--expected-content", default=DEFAULT_EXPECTED)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--retry-delay", type=float, default=1.0)
    ap.add_argument("--ca-file", default=None, help="optional CA bundle/private CA for TLS verification")
    ap.add_argument("--allow-loopback-test", action="store_true", help="CI-only: permit localhost/loopback HTTPS origin")
    args = ap.parse_args(argv)

    token = os.environ.get("MUSE_API_TOKEN", "")
    evidence = Evidence(Path(args.evidence_dir).resolve() if args.evidence_dir else default_evidence_dir(), token)
    failed_stage = "config"
    rc = 1
    try:
        evidence.record("VERSION", "1.0.0")
        evidence.record("MODE", "byo-public-smoke")
        evidence.record("TOKEN_SOURCE", "environment")
        evidence.record("TOKEN_PRESENT", int(bool(token)))
        if not printable_token_ok(token):
            raise RuntimeError("MUSE_API_TOKEN must be >=32 printable characters")
        if args.attempts < 1 or args.attempts > 10:
            raise RuntimeError("--attempts must be between 1 and 10")
        origin = validate_public_url(args.public_url)
        host = urlsplit(origin).hostname or ""
        if is_nonpublic_host(host) and not args.allow_loopback_test:
            raise RuntimeError("public smoke refuses localhost/private/non-global host")
        if args.allow_loopback_test and not is_nonpublic_host(host):
            raise RuntimeError("--allow-loopback-test is only valid for localhost/non-public hosts")
        evidence.record("PUBLIC_URL", origin)
        evidence.record("URL_CLASS", "loopback-test" if is_nonpublic_host(host) else "public")
        evidence.record("RAW_BACKEND_PUBLIC", 0)
        ctx = make_ssl_context(args.ca_file)

        failed_stage = "unauth-health"
        code, _ = request_with_retries(origin + "/health", "GET", None, None, args.timeout, ctx, args.attempts, args.retry_delay, evidence, "unauth-health")
        evidence.record("UNAUTH_HEALTH_HTTP", code)
        if code != 401:
            raise RuntimeError(f"unauthenticated /health expected 401, got {code or 'network-failure'}")

        failed_stage = "auth-health"
        code, _ = request_with_retries(origin + "/health", "GET", token, None, args.timeout, ctx, args.attempts, args.retry_delay, evidence, "auth-health")
        evidence.record("AUTH_HEALTH_HTTP", code)
        if not 200 <= code <= 299:
            raise RuntimeError(f"authenticated /health expected 2xx, got {code or 'network-failure'}")

        failed_stage = "models"
        code, body = request_with_retries(origin + "/v1/models", "GET", token, None, args.timeout, ctx, args.attempts, args.retry_delay, evidence, "models")
        evidence.record("MODELS_HTTP", code)
        if code != 200:
            raise RuntimeError(f"/v1/models expected 200, got {code or 'network-failure'}")
        try:
            data = json.loads(body.decode("utf-8"))
            items = data.get("data") or []
            model_id = str(items[0].get("id", "")) if items and isinstance(items[0], dict) else ""
        except Exception as exc:
            raise RuntimeError(f"invalid /v1/models JSON: {exc}") from exc
        evidence.record("MODEL_ID", model_id)
        if model_id != args.expected_model:
            raise RuntimeError(f"unexpected model id: {model_id!r}")

        failed_stage = "chat"
        chat = {
            "model": args.expected_model,
            "messages": [{"role": "user", "content": f"Reply with exactly {args.expected_content} and nothing else."}],
            "temperature": 0,
            "stream": False,
            "max_tokens": 256,
        }
        code, body = request_with_retries(origin + "/v1/chat/completions", "POST", token, json.dumps(chat, separators=(",", ":")).encode(), args.timeout, ctx, args.attempts, args.retry_delay, evidence, "chat")
        evidence.record("CHAT_HTTP", code)
        if code != 200:
            raise RuntimeError(f"chat expected 200, got {code or 'network-failure'}")
        try:
            data = json.loads(body.decode("utf-8"))
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            content = str(msg.get("content") or "").strip()
            finish = str(choice.get("finish_reason") or "")
            timings = data.get("timings") or {}
            draft_n = int(timings.get("draft_n") or 0)
            draft_ok = int(timings.get("draft_n_accepted") or 0)
        except Exception as exc:
            raise RuntimeError(f"invalid chat JSON: {exc}") from exc
        evidence.record("CHAT_FINISH_REASON", finish)
        evidence.record("CHAT_CONTENT", content)
        evidence.record("DRAFT_N", draft_n)
        evidence.record("DRAFT_N_ACCEPTED", draft_ok)
        evidence.record("DFLASH_ACTIVITY_OBSERVED", int(draft_n > 0 and draft_ok > 0))
        if finish != "stop":
            raise RuntimeError(f"chat finish_reason expected stop, got {finish!r}")
        if content != args.expected_content:
            raise RuntimeError(f"chat exact-content mismatch: {content!r}")

        failed_stage = "complete"
        evidence.record("FAILED_STAGE", "")
        evidence.record("FINAL_SMOKE", "PASS")
        rc = 0
    except Exception as exc:
        evidence.record("FAILED_STAGE", failed_stage)
        evidence.record("ERROR_TYPE", type(exc).__name__)
        evidence.record("ERROR", str(exc))
        evidence.record("FINAL_SMOKE", "FAIL")
        print(f"ERROR: {exc}", file=sys.stderr)
        rc = 1
    finally:
        try:
            redactions = evidence.sanitize_tree()
            evidence.record("SECRET_REDACTION_FILES", redactions)
            evidence.assert_secret_free()
            # Record hygiene after scan; this line itself contains no secret.
            evidence.record("SECRET_HYGIENE", "PASS")
            archive, digest = evidence.package()
            print(f"EVIDENCE_ZIP={archive}")
            print(f"EVIDENCE_SHA256={digest}")
        except Exception as exc:
            print(f"ERROR: failed to package secret-safe evidence: {exc}", file=sys.stderr)
            return 3
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
