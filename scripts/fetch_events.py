"""Maintain data/events.json for conditional macro events (e.g. NFP).

MVP strategy:
- Keep a small static calendar of known high-impact events.
- On run day: if event date is within the next 14 days (or past 3 days), set visible=True.
- Does not scrape live actuals yet (manual fill or future API).

This keeps the events block non-empty around NFP week without depending on Jin10.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA_DIR, now_iso, write_json

# Rough upcoming NFP-style placeholders (first Friday vibe — update as needed)
# Format: name, date ISO, forecast, previous, unit
CALENDAR = [
    {
        "name": "非農就業",
        "date": "2026-08-07",
        "actual": None,
        "forecast": 175000,
        "previous": 206000,
        "unit": "人",
        "note": "美國非農就業報告（預估日程，請依官方確認）",
    },
    {
        "name": "非農就業",
        "date": "2026-09-04",
        "actual": None,
        "forecast": None,
        "previous": None,
        "unit": "人",
        "note": "預估日程",
    },
]


def should_show(event_date: date, today: date) -> bool:
    return (today - timedelta(days=3)) <= event_date <= (today + timedelta(days=14))


def main() -> int:
    today = datetime.now().date()
    events = []
    for raw in CALENDAR:
        try:
            d = date.fromisoformat(raw["date"])
        except ValueError:
            continue
        visible = should_show(d, today)
        events.append(
            {
                "name": raw["name"],
                "date": raw["date"],
                "actual": raw.get("actual"),
                "forecast": raw.get("forecast"),
                "previous": raw.get("previous"),
                "unit": raw.get("unit", "人"),
                "note": raw.get("note", ""),
                "visible": visible,
            }
        )
        print(f"  {raw['name']} {raw['date']} visible={visible}")

    payload = {
        "updated_at": now_iso(),
        "events": events,
    }
    write_json(DATA_DIR / "events.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
