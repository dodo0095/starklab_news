"""Fetch top financial headlines via public RSS → data/news.json

來源改為中文財經（決策 A：不用金十，走中文 RSS，2026-07-28）。
主幹：Google 新聞 zh-TW（穩定、必為中文），輔以鉅亨網 headline RSS。
中文源本身即中文標題/摘要，省去翻譯。Jin10 若日後有 key 再接（P1）。
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, TW, now_iso, write_json

def _gnews(query: str) -> str:
    from urllib.parse import quote
    return (
        "https://news.google.com/rss/search?q="
        + quote(query)
        + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )


FEEDS = [
    # 主幹：Google 新聞 zh-TW，保證中文、穩定
    ("Google 新聞", _gnews("美股 OR 台股 OR 華爾街 OR 那斯達克 OR 道瓊 when:1d")),
    ("Google 新聞", _gnews("(聯準會 OR Fed OR 通膨 OR 利率 OR 非農) when:1d")),
    # 輔助：鉅亨網頭條（若暫時失效不影響主幹）
    ("鉅亨網", "https://news.cnyes.com/rss/v1/news/category/headline"),
]

# 重大 / 總經主題 — 加權（中文為主，保留英文以防中英混雜來源）
KEYWORDS_MAJOR = re.compile(
    r"美股|台股|大盤|加權|道瓊|那斯達克|納斯達克|標普|S&P|費半|"
    r"聯準會|美聯儲|Fed|FOMC|鮑爾|升息|降息|利率|通膨|CPI|非農|就業|"
    r"台積|半導體|晶片|輝達|輝達|AI|財報|殖利率|公債|油價|關稅|"
    r"\b(fed|fomc|powell|inflation|nonfarm|tsmc|semiconductor|nasdaq|"
    r"dow|s&p|treasury|yield|tariff)\b",
    re.I,
)

# 個股推銷 / 標的推薦式 — 降權
KEYWORDS_PITCH = re.compile(
    r"存股|抱緊|飆股|漲停|買進評等|目標價上看|該不該買|報明牌|明牌|"
    r"\b(top|best) (stock|stocks) to (buy|watch)\b|\bshould you buy\b",
    re.I,
)


def parse_entry_time(entry: Any) -> datetime | None:
    for key in ("published", "updated", "created"):
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
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if not t:
            continue
        try:
            return datetime(*t[:6], tzinfo=timezone.utc).astimezone(TW)
        except Exception:
            pass
    return None


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def summarize(text: str, max_len: int = 140) -> str:
    text = strip_html(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def score_entry(title: str, summary: str, source: str) -> int:
    blob = f"{title} {summary}"
    score = 0
    if KEYWORDS_MAJOR.search(blob):
        score += 3
    if KEYWORDS_PITCH.search(title):
        score -= 4
    # ticker-only pitch: "Foo (XYZ) ..." often single-name content
    if "鉅亨" in source or "經濟日報" in source or "工商" in source:
        score += 1
    if "Google" in source:
        score += 1
    return score


def fetch_entries() -> list[dict]:
    import feedparser

    seen: set[str] = set()
    collected: list[dict] = []

    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url)
            if getattr(feed, "bozo", False) and not feed.entries:
                print(f"  [warn] feed issue {url}: {getattr(feed, 'bozo_exception', '')}")
                continue
            n = 0
            for entry in feed.entries[:25]:
                title = strip_html(entry.get("title") or "")
                if not title:
                    continue
                key = re.sub(r"\s+", " ", title.lower())
                if key in seen:
                    continue
                seen.add(key)

                summary = entry.get("summary") or entry.get("description") or ""
                summary = summarize(summary) or title
                # Google News often appends " - Source" in title
                clean_title = re.sub(r"\s+-\s+[^-]+$", "", title).strip() or title

                link = entry.get("link") or ""
                dt = parse_entry_time(entry)
                sc = score_entry(clean_title, summary, source)

                tags = ["財經"]
                if KEYWORDS_MAJOR.search(f"{clean_title} {summary}"):
                    tags = ["美股", "重大"]

                collected.append(
                    {
                        "title": clean_title,
                        "summary": summary if summary != clean_title else summarize(title),
                        "source": source,
                        "url": link,
                        "time": dt.isoformat() if dt else now_iso(),
                        "tags": tags,
                        "_score": sc,
                        "_ts": dt.timestamp() if dt else 0,
                    }
                )
                n += 1
            print(f"  fetched {source}: {n} new / {len(feed.entries)} raw")
        except Exception as e:
            print(f"  [warn] {source}: {e}")

    collected.sort(key=lambda x: (x["_score"], x["_ts"]), reverse=True)
    return collected


def main() -> int:
    entries = fetch_entries()
    if not entries:
        print("[error] no news entries; keeping previous JSON")
        return 1

    # Prefer non-negative scores; if all demoted, still take top 5
    positive = [e for e in entries if e["_score"] >= 0]
    pool = positive if len(positive) >= 5 else entries
    top = pool[:5]

    items = []
    for i, e in enumerate(top, start=1):
        items.append(
            {
                "rank": i,
                "title": e["title"],
                "summary": e["summary"],
                "source": e["source"],
                "url": e["url"],
                "time": e["time"],
                "tags": e["tags"],
            }
        )
        print(f"  #{i} [s={e['_score']}] {e['title'][:70]}")

    write_json(
        DATA_DIR / "news.json",
        {"updated_at": now_iso(), "items": items},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
