"""Fail if any tracked text file contains a blocklisted name.

The blocklist (scripts/brand_blocklist.sha256) stores SHA-256 hashes of
lower-cased names and two-word phrases, never the names themselves.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOCKLIST = Path(__file__).with_name("brand_blocklist.sha256")
TEXT_SUFFIXES = {".md", ".py", ".toml", ".json", ".yml", ".yaml", ".txt", ".cfg"}


def _digest(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def hits(text: str, blocked: set[str]) -> bool:
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9&'.-]+", text)]
    grams = words + [" ".join(words[i : i + 2]) for i in range(len(words) - 1)]
    return any(_digest(g) in blocked for g in grams)


def main() -> int:
    blocked = {ln.strip() for ln in BLOCKLIST.read_text().splitlines() if ln.strip()}
    files = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    bad = [
        f
        for f in files
        if Path(f).suffix in TEXT_SUFFIXES and hits((ROOT / f).read_text(errors="replace"), blocked)
    ]
    for f in bad:
        print("BRAND CHECK FAILED:", f)
    if not bad:
        print(f"brand check passed: {len(files)} tracked files, {len(blocked)} hashed names")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
