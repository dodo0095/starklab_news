"""台積電個股新聞（中文）→ data/tsmc_news.json

需求：P0「TSMC 個股新聞/新訂單」獨立區塊。
來源：Google 新聞 zh-TW（關鍵字：台積電 / TSMC）。與大盤新聞分開，避免混在一起。
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
    + quote("台積電 OR TSMC OR 2330 when:2d")
    + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)

# 好訊號（訂單/擴產/財報）加權，純推銷降權
KW_GOOD = re.compile(r"訂單|擴產|產能|投片|量產|財報|營收|法說|目標價|外資|先進製程|CoWoS|奈米|AI")
KW_PITCH = re.compile(r"存股|抱緊|該不該買|報明牌|明牌|飆股")
# 個股跳動快訊（盤中速報等）— 直接濾除
KW_NOISE = re.compile(r"盤中速報|盤後速報|速報|急拉|急殺|急跌|急漲|委買|委賣|漲停|跌停|鎖死|跳空|成交\d+張")


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


def main() -> int:
    import feedparser

    feed = feedparser.parse(FEED)
    if getattr(feed, "bozo", False) and not feed.entries:
        print(f"[error] TSMC feed issue: {getattr(feed, 'bozo_exception', '')}")
        return 1

    seen: set[str] = set()
    rows = []
    for entry in feed.entries[:30]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        if KW_NOISE.search(title):  # 濾掉盤中速報等個股跳動快訊
            continue
        # Google 新聞標題常帶 " - 來源"，拆出來源
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
        score = 0
        if KW_GOOD.search(clean):
            score += 2
        if KW_PITCH.search(clean):
            score -= 3
        rows.append(
            {
                "title": clean,
                "source": source,
                "url": entry.get("link") or "",
                "time": dt.isoformat() if dt else now_iso(),
                "_score": score,
                "_ts": dt.timestamp() if dt else 0,
            }
        )

    if not rows:
        print("[error] no TSMC news; keeping previous JSON")
        return 1

    rows.sort(key=lambda x: (x["_score"], x["_ts"]), reverse=True)
    items = [
        {"title": r["title"], "source": r["source"], "url": r["url"], "time": r["time"]}
        for r in rows[:6]
    ]
    write_json(
        DATA_DIR / "tsmc_news.json",
        {"updated_at": now_iso(), "symbol": "2330.TW", "name": "台積電", "items": items},
    )
    print(f"  TSMC items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
