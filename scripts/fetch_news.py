"""Fetch top financial headlines via public RSS → data/news.json

Primary: Yahoo Finance + BBC Business (+ optional CNBC/Reuters style feeds)
Jin10 deferred to P1 (needs API key). See docs/金十驗證結論.md
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

FEEDS = [
    ("Yahoo Finance", "https://finance.yahoo.com/rss/topfinstories"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    (
        "Google News",
        "https://news.google.com/rss/search?q=stock+market+OR+Federal+Reserve+OR+TSMC+when:1d&hl=en-US&gl=US&ceid=US:en",
    ),
]

# Major / macro themes — boost score
KEYWORDS_MAJOR = re.compile(
    r"\b(fed|fomc|powell|rate cut|rate hike|inflation|cpi|ppi|jobs report|nonfarm|nfp|"
    r"treasury|yield|recession|tariff|trade war|china|taiwan|tsmc|semiconductor|"
    r"nasdaq|dow jones|s&p|sp500|wall street|oil price|opec|bitcoin|crypto|"
    r"earnings season|gdp|unemployment|ecb|boj|yen|dollar)\b|"
    r"股指|美聯儲|聯準會|台積|半導體|非農|川普|關稅|美股|道瓊|納斯達克",
    re.I,
)

# Single-name pitch / affiliate style — demote
KEYWORDS_PITCH = re.compile(
    r"\bwhy .+ (traded|slid|gained|fell|rose)\b|"
    r"\b(top|best) (stock|stocks) to (buy|watch)\b|"
    r"\bshould you buy\b|\bstock to buy\b|"
    r"\(\s*[A-Z]{2,5}\s*\)\s+(slid|gained|rallied|plunged|traded)",
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
    if re.match(r"^.+\([A-Z]{1,5}\)\s", title):
        score -= 2
    if "BBC" in source or "Google" in source:
        score += 1
    if "Yahoo" in source:
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
