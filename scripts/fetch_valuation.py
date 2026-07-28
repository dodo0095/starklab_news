"""本益比(PE) / 淨值比(PB) 河流圖資料 → data/valuation_{代碼}.json（+ 預設 valuation.json）

- 對觀察名單每檔股票，用近 5 年股價 + 季度 EPS / 每股淨值(BVPS) 計算 PE、PB 河流帶。
- 分法：取歷史比值最小/最大向外留邊，切 6 條等距倍數線 → 反推股價空間，色帶完整包住股價。
- PE 為必要（算不出就略過該檔）；PB 為選配（抓不到淨值就只出 PE）。
- 每檔寫 valuation_{代碼}.json；預設標的(2330 或 STOCK_SYMBOL)另寫 valuation.json 供首頁預設載入。
- 另寫 watchlist.json 供前端「輸入代碼查詢」用。

穩健性：季度 EPS 缺 → 退回常數 trailing EPS（approximate）。失敗不覆寫既有檔。
環境變數 STOCK_SYMBOL / STOCK_NAME 可指定單一標的（覆蓋觀察名單）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, now_iso, safe_float, write_json

# 觀察名單（僅個股；ETF 無 EPS/淨值，不適用估值河流圖）
WATCHLIST = [
    ("2330.TW", "台積電"),
    ("2317.TW", "鴻海"),
    ("2454.TW", "聯發科"),
    ("2308.TW", "台達電"),
]

N_LINES = 6


def _get_price(t):
    """回傳 (dates, closes)，近 5 年實際收盤。"""
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


def _interp_to_dates(points, dates):
    """points: list[(ts_ns, value)] 依時間排序；線性內插對齊到 dates。回傳 list 或 None。"""
    try:
        import bisect

        import pandas as pd

        if len(points) < 2:
            return None
        points = sorted(points)
        xs = [p[0] for p in points]
        ys = [float(p[1]) for p in points]
        out = []
        for d in dates:
            tt = pd.Timestamp(d).value
            if tt <= xs[0]:
                out.append(ys[0])
            elif tt >= xs[-1]:
                out.append(ys[-1])
            else:
                j = bisect.bisect_right(xs, tt)
                x0, x1, y0, y1 = xs[j - 1], xs[j], ys[j - 1], ys[j]
                frac = (tt - x0) / (x1 - x0) if x1 > x0 else 0.0
                out.append(y0 + (y1 - y0) * frac)
        return out
    except Exception:
        return None


def _quarterly_eps(t):
    for attr in ("quarterly_income_stmt", "quarterly_financials", "quarterly_incomestmt"):
        df = getattr(t, attr, None)
        try:
            if df is None or getattr(df, "empty", True):
                continue
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
            s = df.loc[row].dropna().sort_index()
            if len(s) >= 4:
                return s
        except Exception:
            continue
    return None


def _ttm_eps_for_dates(eps_q, dates):
    """季度 EPS → 近四季 TTM，內插對齊到 dates。"""
    try:
        import pandas as pd

        eps_q = eps_q.astype(float).sort_index()
        ttm = eps_q.rolling(4).sum().dropna()
        if ttm.empty:
            return None
        pts = [(pd.Timestamp(str(x)[:10]).value, float(v)) for x, v in zip(ttm.index, ttm.values)]
        return _interp_to_dates(pts, dates)
    except Exception:
        return None


def _bvps_for_dates(t, dates):
    """每股淨值(BVPS) 序列：季度股東權益 / 流通股數，內插對齊到 dates。抓不到回 None。"""
    try:
        import pandas as pd

        bs = None
        for attr in ("quarterly_balance_sheet", "quarterly_balancesheet"):
            df = getattr(t, attr, None)
            if df is not None and not getattr(df, "empty", True):
                bs = df
                break
        if bs is None:
            return None

        def find_row(names):
            idx = list(bs.index)
            for n in names:  # 先精準
                for i in idx:
                    if isinstance(i, str) and n.lower() == i.lower():
                        return i
            for n in names:  # 再模糊
                for i in idx:
                    if isinstance(i, str) and n.lower() in i.lower():
                        return i
            return None

        eq_row = find_row(["Common Stock Equity", "Stockholders Equity", "Total Stockholder Equity", "Total Equity Gross Minority Interest"])
        if eq_row is None:
            return None
        eq = bs.loc[eq_row].dropna()
        sh_row = find_row(["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"])
        sh_series = bs.loc[sh_row].dropna() if sh_row is not None else None

        shares_const = None
        try:
            info = t.get_info() if hasattr(t, "get_info") else t.info
            shares_const = safe_float(info.get("sharesOutstanding"))
        except Exception:
            shares_const = None

        pts = []
        for col in eq.index:
            e = safe_float(eq[col])
            if e is None:
                continue
            sh = None
            if sh_series is not None and col in sh_series.index:
                sh = safe_float(sh_series[col])
            if sh is None or sh <= 0:
                sh = shares_const
            if sh is None or sh <= 0:
                continue
            pts.append((pd.Timestamp(str(col)[:10]).value, e / sh))
        return _interp_to_dates(pts, dates)
    except Exception:
        return None


def build_bands(closes, per_share, unit):
    """通用估值帶。per_share 對齊 closes（TTM EPS 或 BVPS）。unit=中文比值名。"""
    ratio = [c / p for c, p in zip(closes, per_share) if p and p > 0]
    if len(ratio) < 30:
        return None
    rs = sorted(ratio)
    r_min, r_max = rs[0], rs[-1]
    rng = r_max - r_min if r_max > r_min else max(r_max, 1.0)
    pad = rng * 0.05
    lo = max(r_min - pad, r_min * 0.85, 0.01)
    hi = r_max + pad
    lines = [round(lo + (hi - lo) * k / (N_LINES - 1), 2) for k in range(N_LINES)]
    band_prices = [[round(L * p, 2) if (p and p > 0) else None for p in per_share] for L in lines]

    last_c, last_p = closes[-1], per_share[-1]
    current = round(last_c / last_p, 4) if last_p and last_p > 0 else None
    band_idx = None
    zone = "區間內"
    if current is not None:
        if current >= lines[-1]:
            band_idx = N_LINES - 2
        elif current <= lines[0]:
            band_idx = 0
        else:
            for k in range(N_LINES - 1):
                if lines[k] <= current <= lines[k + 1]:
                    band_idx = k
                    break
        top = N_LINES - 2
        if band_idx >= top:
            zone = f"{unit} 5 年高點"
        elif band_idx == 0:
            zone = f"{unit} 5 年低點"
        elif band_idx >= top - 1:
            zone = f"{unit}偏高"
        elif band_idx <= 1:
            zone = f"{unit}偏低"
        else:
            zone = f"{unit}合理區"
    return {"lines": lines, "band_prices": band_prices, "current": current, "current_band_index": band_idx, "zone_label": zone}


def build_symbol(symbol, name):
    import yfinance as yf

    print(f"  --- {symbol} {name} ---")
    t = yf.Ticker(symbol)
    dates, closes = _get_price(t)
    if len(closes) < 60:
        print(f"  [warn] {symbol} 股價資料不足（{len(closes)}）")
        return None

    # PE（必要）
    pe_approx = False
    ttm_eps = None
    eps_q = _quarterly_eps(t)
    if eps_q is not None:
        ttm_eps = _ttm_eps_for_dates(eps_q, dates)
    if not ttm_eps or all(v is None or v <= 0 for v in ttm_eps):
        eps_const = None
        try:
            info = t.get_info() if hasattr(t, "get_info") else t.info
            eps_const = safe_float(info.get("trailingEps"))
        except Exception:
            eps_const = None
        if eps_const and eps_const > 0:
            ttm_eps = [eps_const] * len(dates)
            pe_approx = True
        else:
            ttm_eps = None
    pe_block = build_bands(closes, ttm_eps, "本益比") if ttm_eps else None
    if pe_block is None:
        print(f"  [warn] {symbol} 無法計算本益比，略過")
        return None

    # PB（選配）
    bvps = _bvps_for_dates(t, dates)
    pb_block = build_bands(closes, bvps, "淨值比") if bvps else None

    last_close, last_eps = closes[-1], ttm_eps[-1]
    payload = {
        "symbol": symbol,
        "name": name,
        "updated_at": now_iso(),
        "dates": dates,
        "close": closes,
        # PE（頂層，維持既有前端相容）
        "metric": "PE",
        "approximate": pe_approx,
        "current_close": round(last_close, 2),
        "current_eps": round(last_eps, 4) if last_eps else None,
        "current_pe": pe_block["current"],
        "current_band_index": pe_block["current_band_index"],
        "zone_label": pe_block["zone_label"],
        "pe_lines": pe_block["lines"],
        "band_prices": pe_block["band_prices"],
    }
    if pb_block:
        payload["pb"] = {
            "approximate": False,
            "current": pb_block["current"],
            "current_band_index": pb_block["current_band_index"],
            "zone_label": pb_block["zone_label"],
            "lines": pb_block["lines"],
            "band_prices": pb_block["band_prices"],
        }
    print(f"  現價={round(last_close, 2)} PE={pe_block['current']} zone={pe_block['zone_label']} PB={'有' if pb_block else '無'} approx={pe_approx}")
    return payload


def main() -> int:
    env_sym = os.environ.get("STOCK_SYMBOL")
    if env_sym:
        targets = [(env_sym, os.environ.get("STOCK_NAME", env_sym))]
    else:
        targets = WATCHLIST

    ok = 0
    default_written = False
    wl_items = []
    for i, (symbol, name) in enumerate(targets):
        payload = build_symbol(symbol, name)
        if payload is None:
            continue
        code = symbol.split(".")[0]
        write_json(DATA_DIR / f"valuation_{code}.json", payload)
        wl_items.append({"code": code, "symbol": symbol, "name": name})
        # 預設 valuation.json：優先 2330，否則第一檔成功者
        if symbol.startswith("2330") or (i == 0 and not default_written):
            write_json(DATA_DIR / "valuation.json", payload)
            default_written = True
        ok += 1

    if ok == 0:
        print("[error] 全部標的失敗，保留舊 JSON")
        return 1
    if not default_written and wl_items:
        # 保底：把第一檔成功者當預設
        first = wl_items[0]["code"]
        import shutil

        shutil.copyfile(DATA_DIR / f"valuation_{first}.json", DATA_DIR / "valuation.json")

    write_json(DATA_DIR / "watchlist.json", {"updated_at": now_iso(), "items": wl_items})
    print(f"  完成 {ok}/{len(targets)} 檔；觀察名單 {[w['code'] for w in wl_items]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
