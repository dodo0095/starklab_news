"""共用新聞抓取。

- 鉅亨網（cnYES）分類 RSS：description 有**真實內文摘要** → 取為 summary。
- Google 新聞 zh-TW：穩定、必中文，但 description 僅標題/來源 → summary 留空（僅當備援補量）。
- 統一濾除「盤中速報」等個股跳動快訊、去重、可用關鍵字過濾。

回傳項目：{title, summary, source, url, time(iso), _ts}
"""

from __future__ import annotations

import re
import sys
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import TW, now_iso

# 個股跳動快訊 — 一律濾除
NOISE = re.compile(
    r"盤中速報|盤後速報|速報|急拉|急殺|急跌|急漲|委買|委賣|漲停|跌停|鎖死|跳空|"
    r"成交\d+張|近\d+日股價|三大法人買賣超"
)


def gnews(query: str) -> str:
    return "https://news.google.com/rss/search?q=" + quote(query) + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"


def cnyes(category: str) -> str:
    return f"https://news.cnyes.com/rss/v1/news/category/{category}"


def _strip(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"\s+", " ", t).strip()


def _summarize(t: str, n: int = 90) -> str:
    t = _strip(t)
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _parse_time(entry):
    for k in ("published", "updated"):
        raw = entry.get(k)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(TW)
            except Exception:
                pass
    return None


def fetch(sources, keyword: str | None = None, max_per: int = 50):
    """sources: list[(name, url)]。cnYES 來源取真實摘要，Google 僅標題。

    keyword: 需符合的正規式（比對 title+summary），None 不過濾。
    回傳去重、濾噪音後的 list（未截斷數量，呼叫端自行排序取前 N）。
    """
    import feedparser

    kw = re.compile(keyword) if keyword else None
    seen: set[str] = set()
    out: list[dict] = []

    for name, url in sources:
        has_summary = "cnyes" in url
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:max_per]:
                title = _strip(e.get("title") or "")
                if not title:
                    continue
                src, clean = name, title
                m = re.match(r"^(.*?)\s+-\s+([^-]+)$", title)
                if m and not has_summary:  # Google 新聞標題常帶 " - 來源"
                    clean, src = m.group(1).strip(), m.group(2).strip()
                if NOISE.search(clean):
                    continue
                summary = _summarize(e.get("summary") or e.get("description") or "") if has_summary else ""
                if summary and summary[:12] == clean[:12]:
                    summary = ""  # 摘要與標題重複則不顯示
                key = re.sub(r"\s+", " ", clean.lower())
                if key in seen:
                    continue
                if kw and not kw.search(f"{clean} {summary}"):
                    continue
                seen.add(key)
                dt = _parse_time(e)
                out.append(
                    {
                        "title": clean,
                        "summary": summary,
                        "source": src,
                        "url": e.get("link") or "",
                        "time": dt.isoformat() if dt else now_iso(),
                        "_ts": dt.timestamp() if dt else 0,
                    }
                )
        except Exception as ex:
            print(f"  [warn] {name}: {ex}")
    return out
