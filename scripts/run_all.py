"""Run all data fetchers. Safe: failed modules keep previous JSON."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "fetch_market.py",       # 市場總覽（大盤 + 台積電 ADR）P0
    "fetch_news.py",         # 美國重大新聞前五大（中文源）P0
    "fetch_tsmc_news.py",    # 台積電個股新聞專區 P0
    "fetch_valuation.py",    # 本益比河流圖（主角）
    "fetch_events.py",       # 非農等條件事件 P0
    "fetch_fed.py",          # 聯準會發言重點 P1（原川普）
    "fetch_stock_ma.py",     # 均線河流圖（P1，保留為另一種檢視模式）
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

    # 排程心跳：每次執行都寫入「最後執行時間 + 各來源成敗」，供網頁顯示、驗收確認
    try:
        sys.path.insert(0, str(here))
        from common import now_iso, write_json, DATA_DIR

        write_json(
            DATA_DIR / "status.json",
            {
                "ran_at": now_iso(),
                "ok": failed == 0,
                "ok_count": len(codes) - failed,
                "total": len(codes),
                "sources": [{"script": n, "ok": c == 0} for n, c in zip(SCRIPTS, codes)],
            },
        )
    except Exception as e:
        print(f"[warn] status.json 寫入失敗: {e}")

    # exit 0 if at least one succeeded so scheduler doesn't spam failure every time
    return 0 if failed < len(codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
