"""美國重大新聞前五大（中文，含摘要）→ data/news.json

來源：鉅亨網 wd_stock（國際股市，有真實摘要）+ Google 新聞 zh-TW（備援補量）。
只留美股/總經/重大主題；有摘要者優先。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, now_iso, write_json
from news_common import cnyes, enrich, fetch, gnews

KEYWORDS_MAJOR = re.compile(
    r"美股|台股|大盤|加權|道瓊|那斯達克|納斯達克|標普|S&P|費半|"
    r"聯準會|美聯儲|Fed|FOMC|鮑爾|升息|降息|利率|通膨|CPI|非農|就業|"
    r"台積|半導體|晶片|輝達|AI|財報|殖利率|公債|油價|關稅|經濟|GDP|"
    r"科技|巨頭|蘋果|微軟|亞馬遜|特斯拉",
    re.I,
)


def main() -> int:
    sources = [
        ("鉅亨網", cnyes("wd_stock")),  # 國際股市，有摘要
        ("Google 新聞", gnews("(美股 OR 華爾街 OR 那斯達克 OR 道瓊 OR 標普 OR 聯準會 OR 財報) when:1d")),
    ]
    items = fetch(sources)
    items = [it for it in items if KEYWORDS_MAJOR.search(f"{it['title']} {it['summary']}")]
    if not items:
        print("[error] 無重大新聞，保留舊 JSON")
        return 1

    # 有摘要（鉅亨）優先，再依時間新到舊
    items.sort(key=lambda x: (1 if x["summary"] else 0, x["_ts"]), reverse=True)
    cands = items[:8]
    enrich(cands)  # 對缺摘要者抓文章頁補摘要
    cands.sort(key=lambda x: (1 if x["summary"] else 0, x["_ts"]), reverse=True)
    top = cands[:5]

    out = [
        {
            "rank": i,
            "title": e["title"],
            "summary": e["summary"],
            "source": e["source"],
            "url": e["url"],
            "time": e["time"],
            "tags": ["美股", "重大"],
        }
        for i, e in enumerate(top, start=1)
    ]
    for e in out:
        print(f"  #{e['rank']} {e['title'][:48]}（{'有摘要' if e['summary'] else '無摘要'}）")
    write_json(DATA_DIR / "news.json", {"updated_at": now_iso(), "items": out})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
