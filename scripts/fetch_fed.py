"""聯準會（Fed）發言重點（中文，含摘要）→ data/fed.json

原「川普發言」改為聯準會（常設機構、對盤影響穩定）。
來源：鉅亨網 wd_stock（有真實摘要）+ Google 新聞（備援）。以關鍵字粗分「偏鷹 / 偏鴿」。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, now_iso, write_json
from news_common import cnyes, fetch, gnews

KW_HAWK = re.compile(r"升息|加息|鷹|抗通膨|通膨|緊縮|按兵不動|維持利率|保持耐心|不急於|不降息")
KW_DOVE = re.compile(r"降息|減息|鴿|寬鬆|放緩|降溫|轉向|軟著陸|降利率")


def stance(text: str) -> str:
    h = 1 if KW_HAWK.search(text) else 0
    d = 1 if KW_DOVE.search(text) else 0
    if h and not d:
        return "hawk"
    if d and not h:
        return "dove"
    return "neutral"


def main() -> int:
    sources = [
        ("鉅亨網", cnyes("wd_stock")),  # 國際股市，有摘要
        ("Google 新聞", gnews("(聯準會 OR Fed OR 鮑爾 OR FOMC) (利率 OR 通膨 OR 降息 OR 升息) when:3d")),
    ]
    items = fetch(sources, keyword=r"聯準會|美聯儲|Fed|FOMC|鮑爾|降息|升息|利率|通膨")
    if not items:
        print("[error] 無聯準會新聞，保留舊 JSON")
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
            "stance": stance(f"{e['title']} {e['summary']}"),
        }
        for i, e in enumerate(top, start=1)
    ]
    print(f"  Fed items={len(out)}（有摘要 {sum(1 for e in out if e['summary'])}）")
    write_json(DATA_DIR / "fed.json", {"updated_at": now_iso(), "items": out})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
