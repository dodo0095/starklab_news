"""Run all data fetchers. Safe: failed modules keep previous JSON."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "fetch_market.py",
    "fetch_news.py",
    "fetch_stock_ma.py",
    "fetch_events.py",
]


def main() -> int:
    here = Path(__file__).resolve().parent
    python = sys.executable
    codes = []

    print("=== StarkLab News data update ===")
    for name in SCRIPTS:
        print(f"\n--- {name} ---")
        r = subprocess.run([python, str(here / name)], cwd=str(here.parent))
        codes.append(r.returncode)
        if r.returncode != 0:
            print(f"[warn] {name} exit={r.returncode} (previous JSON retained if any)")

    failed = sum(1 for c in codes if c != 0)
    print(f"\n=== done: {len(codes) - failed}/{len(codes)} ok ===")
    # exit 0 if at least one succeeded so scheduler doesn't spam failure every time
    return 0 if failed < len(codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
