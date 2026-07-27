"""Fetch OHLCV + moving averages via yfinance → data/stock_ma.json

Default symbol: 2330.TW (TSMC TW listing). Override with env STOCK_SYMBOL / STOCK_NAME.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, ma, now_iso, safe_float, write_json

DEFAULT_SYMBOL = os.environ.get("STOCK_SYMBOL", "2330.TW")
DEFAULT_NAME = os.environ.get("STOCK_NAME", "台積電")


def main() -> int:
    import yfinance as yf

    symbol = DEFAULT_SYMBOL
    name = DEFAULT_NAME
    print(f"  symbol={symbol} name={name}")

    t = yf.Ticker(symbol)
    # enough history for MA60
    hist = t.history(period="6mo", auto_adjust=True)
    if hist is None or hist.empty:
        print(f"[error] no history for {symbol}")
        return 1

    hist = hist.dropna(subset=["Close"])
    dates: list[str] = []
    closes: list[float | None] = []

    for idx, row in hist.iterrows():
        # idx is Timestamp
        try:
            d = idx.tz_localize(None).strftime("%Y-%m-%d") if hasattr(idx, "tz_localize") else str(idx)[:10]
        except Exception:
            d = str(idx)[:10]
        c = safe_float(row["Close"])
        if c is None:
            continue
        dates.append(d)
        closes.append(round(c, 4))

    if len(closes) < 20:
        print(f"[error] not enough bars ({len(closes)}) for MA20")
        return 1

    ma5 = ma(closes, 5)
    ma20 = ma(closes, 20)
    ma60 = ma(closes, 60)

    # round for JSON friendliness
    def rnd(xs: list[float | None]) -> list[float | None]:
        return [None if x is None else round(float(x), 4) for x in xs]

    payload = {
        "symbol": symbol,
        "name": name,
        "updated_at": now_iso(),
        "dates": dates,
        "series": {
            "close": closes,
            "ma5": rnd(ma5),
            "ma20": rnd(ma20),
            "ma60": rnd(ma60),
        },
    }
    write_json(DATA_DIR / "stock_ma.json", payload)
    print(f"  bars={len(dates)} last_close={closes[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
