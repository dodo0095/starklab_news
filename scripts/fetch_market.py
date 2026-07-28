"""Fetch market indices + TSM ADR via yfinance → data/market.json"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, now_iso, safe_float, write_json

# name, yfinance symbol —— 美股/國際排
INDICES = [
    ("道瓊", "^DJI"),
    ("納斯達克", "^IXIC"),
    ("S&P 500", "^GSPC"),
    ("台積電 ADR", "TSM"),
]

# 台股排（盡量對應上排：大盤指數 + 代表性 ETF + 權值王）
TW_INDICES = [
    ("加權指數", "^TWII"),
    ("櫃買指數", "^TWOII"),
    ("元大台灣50", "0050.TW"),
    ("台積電", "2330.TW"),
]


def _fi_get(fi, *keys):
    for k in keys:
        try:
            if isinstance(fi, dict):
                v = fi.get(k)
            else:
                v = getattr(fi, k, None)
            v = safe_float(v)
            if v is not None:
                return v
        except Exception:
            continue
    return None


def fetch_quote(symbol: str) -> dict:
    import yfinance as yf

    t = yf.Ticker(symbol)
    price = None
    prev = None
    try:
        fi = t.fast_info
        price = _fi_get(fi, "last_price", "lastPrice", "regular_market_price")
        prev = _fi_get(fi, "previous_close", "previousClose")
    except Exception:
        pass

    if price is None or prev is None:
        hist = t.history(period="5d")
        if hist is None or hist.empty:
            raise RuntimeError(f"no history for {symbol}")
        closes = hist["Close"].dropna()
        if closes.empty:
            raise RuntimeError(f"empty close for {symbol}")
        price = safe_float(closes.iloc[-1])
        prev = safe_float(closes.iloc[-2]) if len(closes) >= 2 else price

    if price is None:
        raise RuntimeError(f"no price for {symbol}")
    if prev is None or prev == 0:
        change = 0.0
        change_pct = 0.0
    else:
        change = round(price - prev, 4)
        change_pct = round((price - prev) / prev * 100, 4)

    return {
        "value": round(price, 4),
        "change": change,
        "change_pct": change_pct,
    }


def fetch_group(pairs: list[tuple[str, str]]) -> tuple[list[dict], list[str]]:
    items: list[dict] = []
    errors: list[str] = []
    for name, symbol in pairs:
        try:
            q = fetch_quote(symbol)
            items.append({"name": name, "symbol": symbol, **q})
            print(f"  {name} ({symbol}): {q['value']} ({q['change_pct']}%)")
        except Exception as e:
            errors.append(f"{symbol}: {e}")
            print(f"  [warn] {name} ({symbol}): {e}")
    return items, errors


def main() -> int:
    items, errors = fetch_group(INDICES)
    tw_items, tw_errors = fetch_group(TW_INDICES)

    if not items and not tw_items:
        print("[error] all market quotes failed; keeping previous JSON")
        return 1

    # session label (TW time)
    from datetime import datetime
    from common import TW

    h = datetime.now(TW).hour
    if h < 8:
        session = "pre-tw-open"
    elif h < 21:
        session = "pre-us-open"
    else:
        session = "us-session"

    payload = {
        "updated_at": now_iso(),
        "session": session,
        "indices": items,       # 美股/國際排
        "tw_indices": tw_items,  # 台股排
    }
    errs = errors + tw_errors
    if errs:
        payload["partial_errors"] = errs

    write_json(DATA_DIR / "market.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
