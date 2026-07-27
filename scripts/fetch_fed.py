"""聯準會（Fed）發言重點（中文）→ data/fed.json

需求：原「川普發言重點」改為聯準會主席/聯準會發言（2026-07-28 決策）。
理由：川普未必持續在任，聯準會為常設機構、對盤勢影響更穩定。
來源：Google 新聞 zh-TW（聯準會 / Fed / 鮑爾）。以關鍵字粗分「偏鷹 / 偏鴿」。
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, TW, now_iso, write_json

FEED = (
    "https://news.google.com/rss/search?q="
    + quote("(聯準會 OR Fed OR 鮑爾 OR FOMC) (利率 OR 通膨 OR 降息 OR 升息) when:3d")
    + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)

# 鷹 = 抗通膨 / 偏緊；鴿 = 寬鬆 / 降息
KW_HAWK = re.compile(r"升息|加息|鷹|抗通膨|通膨|緊縮|按兵不動|維持利率|保持耐心|不急於")
KW_DOVE = re.compile(r"降息|減息|鴿|寬鬆|放緩|降溫|轉向|寬鬆|軟著陸")


def strip_html(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"\s+", " ", t).strip()


def parse_time(entry):
    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(TW)
        except Exception:
            pass
    return None


def stance(text: str) -> str:
    h = 1 if KW_HAWK.search(text) else 0
    d = 1 if KW_DOVE.search(text) else 0
    if h and not d:
        return "hawk"
    if d and not h:
        return "dove"
    return "neutral"


def main() -> int:
    import feedparser

    feed = feedparser.parse(FEED)
    if getattr(feed, "bozo", False) and not feed.entries:
        print(f"[error] Fed feed issue: {getattr(feed, 'bozo_exception', '')}")
        return 1

    seen: set[str] = set()
    rows = []
    for entry in feed.entries[:30]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        m = re.match(r"^(.*?)\s+-\s+([^-]+)$", title)
        source = "Google 新聞"
        clean = title
        if m:
            clean, source = m.group(1).strip(), m.group(2).strip()
        key = re.sub(r"\s+", " ", clean.lower())
        if key in seen:
            continue
        seen.add(key)
        dt = parse_time(entry)
        rows.append(
            {
                "title": clean,
                "source": source,
                "url": entry.get("link") or "",
                "time": dt.isoformat() if dt else now_iso(),
                "stance": stance(clean),
                "_ts": dt.timestamp() if dt else 0,
            }
        )

    if not rows:
        print("[error] no Fed news; keeping previous JSON")
        return 1

    rows.sort(key=lambda x: x["_ts"], reverse=True)
    items = [
        {"title": r["title"], "source": r["source"], "url": r["url"], "time": r["time"], "stance": r["stance"]}
        for r in rows[:5]
    ]
    write_json(
        DATA_DIR / "fed.json",
        {"updated_at": now_iso(), "items": items},
    )
    print(f"  Fed items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
