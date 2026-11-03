"""Run the full test suite and write the real totals to results/test_summary.json.

Prints the totals so a CI log always shows them (no -qq swallowing the count).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XML = ROOT / "results" / "junit.xml"


def main() -> int:
    XML.parent.mkdir(exist_ok=True)
    start = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={XML}"], cwd=ROOT)
    wall = time.perf_counter() - start
    suite = ET.parse(XML).getroot()
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    total = int(suite.get("tests"))
    failed = int(suite.get("failures")) + int(suite.get("errors"))
    skipped = int(suite.get("skipped"))
    summary = {
        "label": "measured",
        "tests_total": total,
        "passed": total - failed - skipped,
        "failed": failed,
        "skipped": skipped,
        "wall_seconds": round(wall, 2),
    }
    (ROOT / "results" / "test_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"TOTAL TESTS: {total}  passed={summary['passed']}  failed={failed}  skipped={skipped}")
    XML.unlink()
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
