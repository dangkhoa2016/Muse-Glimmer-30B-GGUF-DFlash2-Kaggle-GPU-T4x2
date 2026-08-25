#!/usr/bin/env python3
"""Bilingual documentation validator.

Enforces the EN (*.md) / VI (*.vi.md) pairing contract for public Markdown
documentation:

1. every public *.md doc has a matching *.vi.md and vice versa;
2. every doc has an H1;
3. the language line sits immediately after the H1 (no badge/description/blank
   block between them);
4. the counterpart link in the language line resolves;
5. the required README/CHANGELOG/SECURITY/CONTRIBUTING pairs exist.

Scanned directories: the repository root, docs/ (if present), and .github/
(recursively, so authored Markdown such as the PR template is covered too).
Non-documentation files (YAML, CODEOWNERS, workflows, scripts) are out of scope.

Expected:
    BILINGUAL_PAIRING=PASS
    LANGUAGE_SWITCH_POSITION=PASS
    COUNTERPART_LINKS=PASS
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ["README", "CHANGELOG", "SECURITY", "CONTRIBUTING", "CODE_OF_CONDUCT", "SUPPORT"]
LANG_LINE = re.compile(r"^>\s*🌐\s*Language / Ngôn ngữ:")

FAILURES: list[str] = []


def fail(name: str, msg: str) -> None:
    FAILURES.append(f"{name}: {msg}")
    print(f"FAIL  {name}: {msg}")


def scan_dirs() -> list[Path]:
    dirs = [ROOT]
    docs = ROOT / "docs"
    if docs.is_dir():
        dirs.append(docs)
    github = ROOT / ".github"
    if github.is_dir():
        dirs.append(github)
    return dirs


def collect(dirs: list[Path]) -> dict[Path, Path]:
    pairs: dict[Path, Path] = {}
    for base in dirs:
        if base == ROOT:
            files = sorted(base.glob("*.md"))
        else:
            files = sorted(base.rglob("*.md"))
        for p in files:
            text = p.read_text(encoding="utf-8")
            lines = text.splitlines()
            has_h1 = any(line.startswith("# ") for line in lines)
            if not has_h1:
                fail("H1", f"{p.relative_to(ROOT)} lacks an H1 (markdown files must have one)")
            pairs[p] = text
    return pairs


def lang_line_check(doc: Path, text: str, our_suffix: str) -> None:
    lines = text.splitlines()
    if len(lines) < 2 or not lines[0].startswith("# "):
        fail("LANGUAGE_SWITCH_POSITION", f"{doc.relative_to(ROOT)} language line is not directly after H1")
        return
    if not LANG_LINE.match(lines[1]):
        fail("LANGUAGE_SWITCH_POSITION",
             f"{doc.relative_to(ROOT)} line 2 is not the language line (got {lines[1]!r})")

    if our_suffix == ".md":
        link = f"{doc.stem}.vi.md"
    else:
        link = doc.name[: -len(".vi.md")] + ".md"
    if link not in lines[1]:
        fail("COUNTERPART_LINKS", f"{doc.relative_to(ROOT)} language line does not link {link}")


def main() -> int:
    for req in REQUIRED:
        en = ROOT / f"{req}.md"
        vi = ROOT / f"{req}.vi.md"
        if not en.is_file():
            fail("BILINGUAL_PAIRING", f"missing {en.name}")
        if not vi.is_file():
            fail("BILINGUAL_PAIRING", f"missing {en.name}.vi.md")

    pairs = collect(scan_dirs())
    for en, text in sorted(pairs.items()):
        is_vi = en.name.endswith(".vi.md")
        if is_vi:
            counter = en.parent / (en.name[: -len(".vi.md")] + ".md")
            if not counter.is_file():
                fail("BILINGUAL_PAIRING", f"{en.relative_to(ROOT)} lacks its English counterpart")
            lang_line_check(en, text, ".vi.md")
        else:
            counter = en.parent / f"{en.stem}.vi.md"
            if not counter.is_file():
                fail("BILINGUAL_PAIRING", f"{en.relative_to(ROOT)} lacks its Vietnamese counterpart {counter.name}")
            lang_line_check(en, text, ".md")

    print()
    for k in ("BILINGUAL_PAIRING", "LANGUAGE_SWITCH_POSITION", "COUNTERPART_LINKS"):
        print(f"{k}={'FAIL' if FAILURES else 'PASS'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())