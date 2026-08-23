#!/usr/bin/env python3
import argparse
import contextlib
import io
import hashlib
import re
import stat
import tarfile
import sys
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


SECRET_ASSIGN_RE = re.compile(
    r"(?im)\b(MUSE_API_TOKEN|TUNNEL_TOKEN|CLOUDFLARE_TUNNEL_TOKEN)\s*=\s*(?:\"([^\"\r\n]*)\"|'([^'\r\n]*)'|([^\s#;]+))"
)
BEARER_RE = re.compile(r"(?im)\bAuthorization\s*:\s*Bearer\s+([^\s\r\n\"']+)")


def safe_secret_placeholder(value: str) -> bool:
    value = value.strip()
    upper = value.upper()
    if not value:
        return True
    if value.startswith("$"):
        return True
    if value.startswith("<") and value.endswith(">"):
        return True
    if upper in {"REDACTED", "***", "TOKEN", "CHANGE_ME", "CHANGEME"}:
        return True
    if upper.startswith("YOUR_") or upper.startswith("EXAMPLE_"):
        return True
    return False


def find_literal_secret(data: bytes) -> str | None:
    text = data.decode("utf-8", errors="replace")
    for match in SECRET_ASSIGN_RE.finditer(text):
        name = match.group(1)
        value = next((g for g in match.groups()[1:] if g is not None), "")
        if not safe_secret_placeholder(value):
            return name
    for match in BEARER_RE.finditer(text):
        value = match.group(1)
        if not safe_secret_placeholder(value):
            return "Authorization Bearer"
    return None


def archive_member_path_is_safe(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return False
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    return ".." not in parts


def find_secret_in_evidence(path: Path) -> str | None:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ARCHIVE_MEMBERS:
                raise ValueError("archive member count limit exceeded")
            if sum(info.file_size for info in infos) > MAX_EXPANDED_BYTES:
                raise ValueError("archive expanded size limit exceeded")
            for info in infos:
                if not archive_member_path_is_safe(info.filename):
                    raise ValueError(f"unsafe archive member path: {info.filename}")
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise ValueError(f"unsafe archive member type: {info.filename}")
                if info.is_dir():
                    continue
                issue = find_literal_secret(zf.read(info))
                if issue:
                    return issue
        return None
    if tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as tf:
            members = tf.getmembers()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise ValueError("archive member count limit exceeded")
            if sum(member.size for member in members if member.isfile()) > MAX_EXPANDED_BYTES:
                raise ValueError("archive expanded size limit exceeded")
            for member in members:
                if not archive_member_path_is_safe(member.name):
                    raise ValueError(f"unsafe archive member path: {member.name}")
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError(f"unsafe archive member type: {member.name}")
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                issue = find_literal_secret(fh.read())
                if issue:
                    return issue
        return None
    return find_literal_secret(path.read_bytes())


MAX_ARCHIVE_MEMBERS = 4096
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def write_zip_bytes(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    zf.writestr(info, data, compress_type=zipfile.ZIP_STORED)


def parse_sidecar(path: Path) -> str:
    line = path.read_text(encoding="utf-8").strip()
    digest = line.split(None, 1)[0] if line else ""
    if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
        raise ValueError("invalid SHA256 sidecar")
    return digest.lower()


def main() -> int:
    parser = argparse.ArgumentParser(description="Portable deterministic release/evidence export")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--release-zip", required=True)
    parser.add_argument("--release-sidecar")
    parser.add_argument("--acceptance-harness")
    parser.add_argument("--acceptance-harness-sidecar")
    parser.add_argument("--verification-evidence")
    parser.add_argument("--verification-evidence-sidecar")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    release_zip = Path(args.release_zip)
    if not release_zip.is_file():
        print(f"ERROR: release ZIP missing: {release_zip}", file=sys.stderr)
        return 2

    if args.release_sidecar:
        sidecar = Path(args.release_sidecar)
        if not sidecar.is_file():
            print(f"ERROR: release sidecar missing: {sidecar}", file=sys.stderr)
            return 2
        try:
            expected = parse_sidecar(sidecar)
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"ERROR: invalid release sidecar: {exc}", file=sys.stderr)
            return 2
        actual = sha256_file(release_zip)
        if expected != actual:
            print("ERROR: release sidecar SHA256 mismatch", file=sys.stderr)
            return 2

    harness = Path(args.acceptance_harness) if args.acceptance_harness else None
    harness_sha = ""
    if harness is not None:
        if not harness.is_file():
            print(f"ERROR: acceptance harness missing: {harness}", file=sys.stderr)
            return 2
        harness_sha = sha256_file(harness)
        secret_name = find_literal_secret(harness.read_bytes())
        if secret_name:
            print(f"ERROR: secret hygiene failed: acceptance harness contains literal {secret_name}", file=sys.stderr)
            return 2
        if args.acceptance_harness_sidecar:
            sidecar = Path(args.acceptance_harness_sidecar)
            if not sidecar.is_file():
                print(f"ERROR: acceptance harness sidecar missing: {sidecar}", file=sys.stderr)
                return 2
            try:
                expected = parse_sidecar(sidecar)
            except (OSError, UnicodeError, ValueError) as exc:
                print(f"ERROR: invalid acceptance harness sidecar: {exc}", file=sys.stderr)
                return 2
            if expected != harness_sha:
                print("ERROR: acceptance harness sidecar SHA256 mismatch", file=sys.stderr)
                return 2
    elif args.acceptance_harness_sidecar:
        print("ERROR: acceptance harness sidecar requires --acceptance-harness", file=sys.stderr)
        return 2

    evidence = Path(args.verification_evidence) if args.verification_evidence else None
    evidence_sha = ""
    if evidence is not None:
        if not evidence.is_file():
            print(f"ERROR: verification evidence missing: {evidence}", file=sys.stderr)
            return 2
        evidence_sha = sha256_file(evidence)
        try:
            evidence_secret = find_secret_in_evidence(evidence)
        except (OSError, tarfile.TarError, ValueError) as exc:
            print(f"ERROR: verification evidence scan failed: {exc}", file=sys.stderr)
            return 2
        if evidence_secret:
            print(f"ERROR: secret hygiene failed: verification evidence contains literal {evidence_secret}", file=sys.stderr)
            return 2
        if args.verification_evidence_sidecar:
            sidecar = Path(args.verification_evidence_sidecar)
            if not sidecar.is_file():
                print(f"ERROR: verification evidence sidecar missing: {sidecar}", file=sys.stderr)
                return 2
            try:
                expected = parse_sidecar(sidecar)
            except (OSError, UnicodeError, ValueError) as exc:
                print(f"ERROR: invalid verification evidence sidecar: {exc}", file=sys.stderr)
                return 2
            if expected != evidence_sha:
                print("ERROR: verification evidence sidecar SHA256 mismatch", file=sys.stderr)
                return 2
    elif args.verification_evidence_sidecar:
        print("ERROR: verification evidence sidecar requires --verification-evidence", file=sys.stderr)
        return 2

    source_root = Path(args.source_root).resolve()
    manifest_tool = source_root / "scripts" / "source_manifest.py"
    manifest = source_root / "SOURCE_MANIFEST.sha256"
    if not manifest_tool.is_file() or not manifest.is_file():
        print("ERROR: source manifest checker unavailable", file=sys.stderr)
        return 2
    try:
        namespace = {
            "__name__": "_release_source_manifest_probe",
            "__file__": str(manifest_tool),
        }
        code = compile(manifest_tool.read_bytes(), str(manifest_tool), "exec")
        exec(code, namespace)
        manifest_output = io.StringIO()
        with contextlib.redirect_stdout(manifest_output):
            manifest_ok = bool(namespace["check"](source_root, manifest))
    except Exception as exc:
        print(f"ERROR: source manifest checker failed: {exc}", file=sys.stderr)
        return 2
    if not manifest_ok:
        print("ERROR: source manifest is dirty", file=sys.stderr)
        detail = manifest_output.getvalue().rstrip()
        if detail:
            print(detail, file=sys.stderr)
        return 2

    source_version = (source_root / "VERSION").read_text(encoding="utf-8").strip()
    try:
        with zipfile.ZipFile(release_zip, "r") as zf:
            version_members = [n for n in zf.namelist() if n.rstrip("/").endswith("/VERSION")]
            manifest_members = [n for n in zf.namelist() if n.rstrip("/").endswith("/SOURCE_MANIFEST.sha256")]
            if len(version_members) != 1:
                print("ERROR: release ZIP must contain exactly one VERSION", file=sys.stderr)
                return 2
            if len(manifest_members) != 1:
                print("ERROR: release ZIP must contain exactly one SOURCE_MANIFEST.sha256", file=sys.stderr)
                return 2
            release_version = zf.read(version_members[0]).decode("utf-8").strip()
            release_manifest = zf.read(manifest_members[0])
    except (OSError, zipfile.BadZipFile, UnicodeError) as exc:
        print(f"ERROR: invalid release ZIP: {exc}", file=sys.stderr)
        return 2
    if release_version != source_version:
        print("ERROR: release ZIP VERSION mismatch", file=sys.stderr)
        return 2
    if release_manifest != manifest.read_bytes():
        print("ERROR: release ZIP SOURCE_MANIFEST mismatch", file=sys.stderr)
        return 2

    try:
        prefix = version_members[0][:-len("VERSION")]
        manifest_rows = []
        for raw in release_manifest.decode("utf-8").splitlines():
            if not raw.strip():
                continue
            digest, rel = raw.split(None, 1)
            manifest_rows.append((digest.lower(), rel.strip()))
        with zipfile.ZipFile(release_zip, "r") as zf:
            names = zf.namelist()
            for digest, rel in manifest_rows:
                member_name = f"{prefix}{rel}"
                if names.count(member_name) != 1:
                    print(f"ERROR: release ZIP manifest entry mismatch: {rel}", file=sys.stderr)
                    return 2
                actual = hashlib.sha256(zf.read(member_name)).hexdigest()
                if actual != digest:
                    print(f"ERROR: release ZIP manifest entry mismatch: {rel}", file=sys.stderr)
                    return 2
    except (OSError, zipfile.BadZipFile, UnicodeError, ValueError) as exc:
        print(f"ERROR: invalid release ZIP manifest: {exc}", file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    release_sha = sha256_file(release_zip)
    manifest_bytes = manifest.read_bytes()
    declaration = "\n".join(
        [
            "SCHEMA_VERSION=1",
            f"RELEASE_VERSION={source_version}",
            "EXPORT_FORMAT=portable-release-evidence-zip-v1",
            f"RELEASE_FILE={release_zip.name}",
            f"RELEASE_SHA256={release_sha}",
            f"SOURCE_MANIFEST_SHA256={hashlib.sha256(manifest_bytes).hexdigest()}",
            f"SOURCE_MANIFEST_FILES={len(manifest_bytes.splitlines())}",
            f"ACCEPTANCE_HARNESS_FILE={harness.name if harness else ''}",
            f"ACCEPTANCE_HARNESS_SHA256={harness_sha}",
            f"VERIFICATION_EVIDENCE_FILE={evidence.name if evidence else ''}",
            f"VERIFICATION_EVIDENCE_SHA256={evidence_sha}",
            "",
        ]
    ).encode("utf-8")
    entries = {
        f"release/{release_zip.name}": release_zip.read_bytes(),
        f"release/{release_zip.name}.sha256": f"{release_sha}  {release_zip.name}\n".encode("utf-8"),
        "release-declaration.env": declaration,
    }
    if harness is not None:
        entries[f"acceptance/{harness.name}"] = harness.read_bytes()
        entries[f"acceptance/{harness.name}.sha256"] = f"{harness_sha}  {harness.name}\n".encode("utf-8")
    if evidence is not None:
        entries[f"evidence/{evidence.name}"] = evidence.read_bytes()
        entries[f"evidence/{evidence.name}.sha256"] = f"{evidence_sha}  {evidence.name}\n".encode("utf-8")
    checksum_text = "".join(
        f"{hashlib.sha256(entries[name]).hexdigest()}  {name}\n"
        for name in sorted(entries)
    ).encode("utf-8")
    entries["CHECKSUMS.sha256"] = checksum_text
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as zf:
        for name in sorted(entries):
            write_zip_bytes(zf, name, entries[name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
