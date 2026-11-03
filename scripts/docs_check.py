"""Fail if the docs quote a test count that a fresh collection does not match.

Collects the suite with pytest, then checks README.md and the guides for the
marker '<!-- tests:N -->'. Every marker must equal the real collected count.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [
    "README.md",
    "LEARNING_GUIDE.md",
    "PRESENTATION_GUIDE.md",
    "docs/03-interview-points.md",
    "docs/05-built-vs-planned.md",
]
MARK = re.compile(r"<!-- tests:(\d+) -->")


def collected() -> int:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    m = re.search(r"(\d+) tests? collected", out)
    if not m:
        raise SystemExit("could not read collected test count")
    return int(m.group(1))


def main() -> int:
    real = collected()
    print(f"collected tests: {real}")
    bad = []
    seen = 0
    for name in DOCS:
        text = (ROOT / name).read_text()
        for m in MARK.finditer(text):
            seen += 1
            if int(m.group(1)) != real:
                bad.append(f"{name}: says {m.group(1)}, real {real}")
    if seen == 0:
        bad.append("no test-count markers found in docs")
    for line in bad:
        print("DOCS CHECK FAILED:", line)
    if not bad:
        print(f"docs check passed: {seen} markers all equal {real}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
