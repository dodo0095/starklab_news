"""台積電個股新聞（中文，含摘要）→ data/tsmc_news.json

來源：鉅亨網 tw_stock（有真實摘要）+ Google 新聞（備援）。只留台積電相關；有摘要者優先。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, now_iso, write_json
from news_common import cnyes, fetch, gnews


def main() -> int:
    sources = [
        ("鉅亨網", cnyes("tw_stock")),  # 台股，有摘要（台積電新聞在此）
        ("Google 新聞", gnews("台積電 OR TSMC OR 2330 when:2d")),
    ]
    items = fetch(sources, keyword=r"台積電|TSMC|2330", max_per=60)
    if not items:
        print("[error] 無台積電新聞，保留舊 JSON")
        return 1

    items.sort(key=lambda x: (1 if x["summary"] else 0, x["_ts"]), reverse=True)
    top = items[:5]

    out = [
        {
            "rank": i,
            "title": e["title"],
            "summary": e["summary"],
            "source": e["source"],
            "url": e["url"],
            "time": e["time"],
        }
        for i, e in enumerate(top, start=1)
    ]
    print(f"  TSMC items={len(out)}（有摘要 {sum(1 for e in out if e['summary'])}）")
    write_json(
        DATA_DIR / "tsmc_news.json",
        {"updated_at": now_iso(), "symbol": "2330.TW", "name": "台積電", "items": out},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
