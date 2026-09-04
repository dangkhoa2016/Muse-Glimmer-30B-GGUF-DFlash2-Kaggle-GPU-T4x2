#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys

SUBJECT_RE = re.compile(
    r"^(core|cuda|llama|model|gateway|expose|runtime|ops|tests|repo|ci|license|docs): .+"
)
EXPECTED_IDENTITY = "Đăng Khoa <i.am@dangkhoa.dev>"

def run(*args):
    return subprocess.check_output(args, text=True).strip()

def fail(msg):
    print(f"COMMIT_MESSAGE_STANDARD=FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)

parser = argparse.ArgumentParser()
parser.add_argument("--range", default="HEAD")
parser.add_argument("--skip-identity", action="store_true")
args = parser.parse_args()

commits = run("git", "rev-list", "--reverse", args.range).splitlines()
if not commits:
    fail(f"no commits found for range {args.range!r}")

for sha in commits:
    message = subprocess.check_output(
        ["git", "show", "-s", "--format=%B", sha], text=True
    ).rstrip("\n")
    lines = message.splitlines()
    if not lines:
        fail(f"{sha}: empty message")

    subject = lines[0]
    if len(subject) > 72:
        fail(f"{sha}: subject exceeds 72 characters")
    if not SUBJECT_RE.match(subject):
        fail(f"{sha}: invalid subject format: {subject!r}")
    if len(lines) < 5 or lines[1] != "":
        fail(f"{sha}: expected blank line and three bullet body lines")

    body = [line for line in lines[2:] if line.strip()]
    if len(body) != 3 or not all(line.startswith("- ") for line in body):
        fail(f"{sha}: body must contain exactly three single-line bullets")

    if not args.skip_identity:
        identity = run(
            "git", "show", "-s", "--format=%an <%ae>%n%cn <%ce>", sha
        ).splitlines()
        if identity != [EXPECTED_IDENTITY, EXPECTED_IDENTITY]:
            fail(f"{sha}: author/committer identity mismatch: {identity!r}")

print(f"COMMIT_MESSAGE_STANDARD=PASS commits={len(commits)} range={args.range}")
