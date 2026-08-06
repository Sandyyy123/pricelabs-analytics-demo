"""
Generate a synthetic PriceLabs-style nightly calendar + a market comp file,
so the demo runs with zero real data. Deterministic (fixed seed).

Real projects read your actual PriceLabs / PMS exports instead — the schema
here mirrors what those exports give you (one row per listing per night).
"""
from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

SEED = 42
START = dt.date(2025, 1, 1)
DAYS = 400  # ~13 months so we can compute same-time-last-year pacing

LISTINGS = [
    # name, base_price, quality (drives demand), min_stay
    ("Beach House - Trigg", 265, 0.92, 2),
    ("Coastal 2BR - Scarborough", 205, 0.85, 2),
    ("Riverfront 1BR - South Perth", 185, 0.74, 1),
    ("CBD Studio - Perth", 150, 0.60, 3),
    ("Hills Cottage - Kalamunda", 175, 0.55, 2),
]


def demand_multiplier(d: dt.date, quality: float) -> float:
    """Weekend + summer (Southern-Hemisphere Dec-Feb) lift, scaled by quality."""
    weekend = 1.25 if d.weekday() >= 4 else 1.0        # Fri/Sat/Sun
    summer = 1.20 if d.month in (12, 1, 2) else 1.0    # Perth peak
    return quality * weekend * summer


def main() -> None:
    random.seed(SEED)
    out = Path(__file__).parent / "sample_data"
    out.mkdir(exist_ok=True)

    cal_rows = []
    for name, base, quality, min_stay in LISTINGS:
        for i in range(DAYS):
            d = START + dt.timedelta(days=i)
            mult = demand_multiplier(d, quality)
            p_booked = min(0.97, 0.66 * mult)
            r = random.random()
            if r < 0.03:
                status = "blocked"          # owner/maintenance block
            elif r < p_booked:
                status = "booked"
            else:
                status = "open"
            # nightly price wobbles around base with the same demand signal
            price = round(base * (0.85 + 0.30 * (mult - quality) + random.uniform(-0.05, 0.08)), 0)
            cal_rows.append([name, d.isoformat(), status, int(price), min_stay])

    with open(out / "calendar.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["listing", "date", "status", "price", "min_stay"])
        w.writerows(cal_rows)

    # market comp file: median market ADR per listing (PriceLabs neighborhood data proxy).
    # Deliberately set a couple of listings *below* market to trigger the raise rule.
    market = {
        "Beach House - Trigg": 275,
        "Coastal 2BR - Scarborough": 238,   # selling out but priced under market
        "Riverfront 1BR - South Perth": 190,
        "CBD Studio - Perth": 158,
        "Hills Cottage - Kalamunda": 172,
    }
    with open(out / "market.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["listing", "market_adr_p50"])
        for k, v in market.items():
            w.writerow([k, v])

    print(f"Wrote {len(cal_rows):,} calendar rows and {len(market)} market rows to {out}/")


if __name__ == "__main__":
    main()
