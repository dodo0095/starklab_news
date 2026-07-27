"""Shared helpers for data fetch scripts."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

TW = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def now_iso() -> str:
    return datetime.now(TW).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # atomic-ish write: temp then replace
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)
    print(f"[ok] wrote {path.relative_to(ROOT)}")


def safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def ma(values: list[float | None], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
            continue
        chunk = values[i + 1 - window : i + 1]
        if any(x is None for x in chunk):
            out.append(None)
            continue
        out.append(round(sum(chunk) / window, 4))  # type: ignore[arg-type]
    return out
