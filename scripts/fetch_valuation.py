"""本益比（PE）河流圖資料 → data/valuation.json

決策 B（2026-07-28）：河流圖 = 本益比版。
作法：
  1. yfinance 取近 5 年股價（Close）與季度 EPS。
  2. 由季度 EPS 累加成 TTM（近四季）EPS，對齊到每個交易日。
  3. 歷史本益比 PE_t = 收盤價_t / TTM_EPS_t。
  4. 取 PE 的分位數（10/30/50/70/90%）當「便宜～昂貴」估值帶。
  5. 把各分位 PE 乘回當日 TTM_EPS，得到「股價空間」的河流色帶。
  6. 疊上實際收盤價，並算出目前落在哪一帶。

穩健性：若抓不到季度 EPS（台股常見），退回以 info.trailingEps 之常數 EPS 計算，
標記 approximate=True（此時色帶等同股價分位帶，仍可展示，只是精度較低）。

覆寫規則沿用專案慣例：失敗直接 return 1，不覆寫既有 JSON。
環境變數 STOCK_SYMBOL / STOCK_NAME 可切換標的。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, now_iso, safe_float, write_json

DEFAULT_SYMBOL = os.environ.get("STOCK_SYMBOL", "2330.TW")
DEFAULT_NAME = os.environ.get("STOCK_NAME", "台積電")

# 分位 → 中文帶名（低 PE = 便宜）
QUANTILES = [(0.10, "便宜"), (0.30, "偏低"), (0.50, "合理"), (0.70, "偏高"), (0.90, "昂貴")]
BAND_ORDER = ["便宜", "偏低", "合理", "偏高", "昂貴"]


def _get_price(t):
    """回傳 (dates:list[str], closes:list[float])，近 5 年、實際收盤。"""
    import pandas as pd  # noqa: F401  (yfinance 依賴)

    for period in ("5y", "3y", "2y", "1y"):
        hist = t.history(period=period, auto_adjust=False)
        if hist is not None and not hist.empty:
            hist = hist.dropna(subset=["Close"])
            if len(hist) >= 60:
                dates, closes = [], []
                for idx, row in hist.iterrows():
                    try:
                        d = idx.tz_localize(None).strftime("%Y-%m-%d") if hasattr(idx, "tz_localize") else str(idx)[:10]
                    except Exception:
                        d = str(idx)[:10]
                    c = safe_float(row["Close"])
                    if c is None:
                        continue
                    dates.append(d)
                    closes.append(round(c, 4))
                return dates, closes
    return [], []


def _quarterly_eps(t):
    """回傳 pandas.Series（index=季末日期 Timestamp, value=EPS），失敗回 None。"""
    for attr in ("quarterly_income_stmt", "quarterly_financials", "quarterly_incomestmt"):
        df = getattr(t, attr, None)
        try:
            if df is None or getattr(df, "empty", True):
                continue
            # 找含 'eps' 的列（Diluted EPS 優先）
            rows = [i for i in df.index if isinstance(i, str) and "eps" in i.lower()]
            if not rows:
                continue
            row = None
            for pref in ("diluted eps", "basic eps"):
                for r in rows:
                    if pref in r.lower():
                        row = r
                        break
                if row:
                    break
            row = row or rows[0]
            s = df.loc[row].dropna()
            s = s[[c for c in s.index]]
            s.index = [c for c in s.index]  # keep timestamps
            s = s.sort_index()
            if len(s) >= 4:
                return s
        except Exception:
            continue
    return None


def _ttm_eps_for_dates(eps_q, dates):
    """由季度 EPS 累加 TTM，對齊到每個交易日。

    改用「季度間線性內插」而非 forward-fill：EPS 每季才更新一次，若直接沿用會讓
    估值帶呈現難看的階梯狀。線性內插後帶子平滑，視覺更接近正規本益比河流圖。
    回傳 list 或 None。
    """
    try:
        import bisect

        import pandas as pd

        eps_q = eps_q.astype(float).sort_index()
        ttm = eps_q.rolling(4).sum().dropna()  # 近四季加總
        if ttm.empty:
            return None
        xs = [pd.Timestamp(str(x)[:10]).value for x in ttm.index]  # ns 時間戳
        ys = [float(v) for v in ttm.values]

        out = []
        for d in dates:
            t = pd.Timestamp(d).value
            if t <= xs[0]:
                out.append(ys[0])
            elif t >= xs[-1]:
                out.append(ys[-1])
            else:
                j = bisect.bisect_right(xs, t)
                x0, x1, y0, y1 = xs[j - 1], xs[j], ys[j - 1], ys[j]
                frac = (t - x0) / (x1 - x0) if x1 > x0 else 0.0
                out.append(y0 + (y1 - y0) * frac)
        return out
    except Exception:
        return None


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    if q <= 0:
        return sorted_vals[0]
    if q >= 1:
        return sorted_vals[-1]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    frac = pos - lo
    if lo + 1 < len(sorted_vals):
        return sorted_vals[lo] * (1 - frac) + sorted_vals[lo + 1] * frac
    return sorted_vals[lo]


def main() -> int:
    import yfinance as yf

    symbol, name = DEFAULT_SYMBOL, DEFAULT_NAME
    print(f"  symbol={symbol} name={name}")
    t = yf.Ticker(symbol)

    dates, closes = _get_price(t)
    if len(closes) < 60:
        print(f"[error] 股價資料不足（{len(closes)} 筆）")
        return 1

    approximate = False
    ttm_eps = None
    eps_q = _quarterly_eps(t)
    if eps_q is not None:
        ttm_eps = _ttm_eps_for_dates(eps_q, dates)

    if not ttm_eps or all(v is None or v <= 0 for v in ttm_eps):
        # fallback：常數 trailing EPS
        eps_const = None
        try:
            info = t.get_info() if hasattr(t, "get_info") else t.info
            eps_const = safe_float(info.get("trailingEps"))
        except Exception:
            eps_const = None
        if eps_const is None or eps_const <= 0:
            print("[error] 無法取得 EPS（季度與 trailing 皆缺），無法計算本益比")
            return 1
        ttm_eps = [eps_const] * len(dates)
        approximate = True
        print(f"  [warn] 季度 EPS 不可得，改用常數 trailing EPS={eps_const}（approximate）")

    # 歷史 PE 序列（只取 EPS>0）
    pe_series = []
    for c, e in zip(closes, ttm_eps):
        if e and e > 0:
            pe_series.append(c / e)
    if len(pe_series) < 30:
        print("[error] 有效本益比樣本不足")
        return 1

    # 分法（參考正規本益比河流圖）：取歷史 PE 的最小/最大並向外留邊，
    # 切成 N-1 條等距倍數線。因 price = PE × EPS 且 minPE ≤ PE_t ≤ maxPE，
    # 外緣線向外擴後，色帶必定「完整包住股價線」。
    pe_sorted = sorted(pe_series)
    pe_min, pe_max = pe_sorted[0], pe_sorted[-1]
    rng = pe_max - pe_min if pe_max > pe_min else max(pe_max, 1.0)
    pad = rng * 0.05
    lo = max(pe_min - pad, pe_min * 0.85, 0.5)
    hi = pe_max + pad
    N_LINES = 6
    pe_lines = [round(lo + (hi - lo) * k / (N_LINES - 1), 1) for k in range(N_LINES)]

    # 每條 PE 線反推股價空間：pe_k × 當日 TTM EPS
    band_prices = []
    for pe_k in pe_lines:
        band_prices.append([round(pe_k * e, 2) if (e and e > 0) else None for e in ttm_eps])

    last_close = closes[-1]
    last_eps = ttm_eps[-1]
    current_pe = round(last_close / last_eps, 4) if last_eps and last_eps > 0 else None

    # 目前落在第幾帶（0=最便宜 .. N-2=最貴）＋區間標籤
    band_idx = None
    zone_label = "區間內"
    if current_pe is not None:
        if current_pe >= pe_lines[-1]:
            band_idx = N_LINES - 2
        elif current_pe <= pe_lines[0]:
            band_idx = 0
        else:
            for k in range(N_LINES - 1):
                if pe_lines[k] <= current_pe <= pe_lines[k + 1]:
                    band_idx = k
                    break
        top = N_LINES - 2
        if band_idx >= top:
            zone_label = "本益比 5 年高點"
        elif band_idx == 0:
            zone_label = "本益比 5 年低點"
        elif band_idx >= top - 1:
            zone_label = "本益比偏高"
        elif band_idx <= 1:
            zone_label = "本益比偏低"
        else:
            zone_label = "本益比合理區"

    payload = {
        "symbol": symbol,
        "name": name,
        "updated_at": now_iso(),
        "metric": "PE",
        "approximate": approximate,
        "current_close": round(last_close, 2),
        "current_eps": round(last_eps, 4) if last_eps else None,
        "current_pe": current_pe,
        "current_band_index": band_idx,
        "zone_label": zone_label,
        "pe_lines": pe_lines,
        "dates": dates,
        "close": closes,
        "band_prices": band_prices,
    }
    write_json(DATA_DIR / "valuation.json", payload)
    print(f"  現價(收盤)={round(last_close, 2)} EPS(TTM)={round(last_eps, 2)} PE_now={current_pe} zone={zone_label}")
    print(f"  bars={len(dates)} pe_lines={pe_lines} approx={approximate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
