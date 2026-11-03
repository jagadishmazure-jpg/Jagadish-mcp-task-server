"""Report any 8-word run shared between our docs and a reference text.

    python scripts/overlap_check.py /path/to/reference.txt

The reference text is never committed; pass its path at run time. Target: 0 shared 8-word runs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = 8


def grams(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(words[i : i + N]) for i in range(len(words) - N + 1)}


def main() -> int:
    source = grams(Path(sys.argv[1]).read_text())
    total = 0
    for path in sorted(ROOT.rglob("*.md")):
        if ".venv" in path.parts or ".git" in path.parts:
            continue
        shared = grams(path.read_text()) & source
        total += len(shared)
        for g in sorted(shared):
            print(f"{path.relative_to(ROOT)}: {' '.join(g)}")
    print(f"8-word overlap hits: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
