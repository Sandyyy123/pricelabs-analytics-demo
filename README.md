> **⚠️ Proprietary — All Rights Reserved.** © 2026 Sandeep Grover. This repository is licensed to Sandeep Grover and may **not** be used, run, copied, modified, distributed, or used to train models without prior written permission. Public visibility does not grant a license. See [LICENSE](LICENSE).

---

# PriceLabs Pricing Analytics Demo

A small, **runnable** engine that turns short-term-rental pricing data
(PriceLabs / PMS exports) into the two things a revenue decision actually
needs: the right metrics, and a **ranked action list** that says what to
change this week and roughly what it is worth.

It is a working sample of the analytics layer behind a pricing-decision
dashboard — computes ADR / Occupancy / RevPAR, forward **booking pace vs
same-time-last-year (STLY)**, and four decision rules, all on data you can
regenerate locally in one command.

## What it computes

| Metric | Definition |
|---|---|
| **ADR** | booked revenue ÷ booked nights |
| **Occupancy** | booked nights ÷ available nights (blocked nights excluded) |
| **RevPAR** | booked revenue ÷ available nights ( = ADR × Occupancy ) |
| **Pace vs STLY** | forward-window occupancy now vs the same window 364 days ago |

## Decision rules (the "action list")

| Signal | Recommendation |
|---|---|
| `high_occupancy_below_market` | raise base price |
| `soft_pace_far_out` | lower far-out price |
| `min_stay_blocking` | reduce minimum stay (frees short-stay demand) |
| `orphan_night` | last-minute discount on single gap nights |

Each recommendation carries an **estimated revenue impact** so the list
ranks by dollars, not alphabetically.

## Run it

```bash
pip install -r requirements.txt
python generate_sample_data.py   # writes deterministic sample_data/*.csv
python main.py
```

### Example output (real, from `python main.py`)

```
  PORTFOLIO KPIs
  Listings        5
  Occupancy        54.8%
  ADR             $185
  RevPAR          $102
  Revenue (13mo)  $197,811

  NEXT-30-DAY PACE vs SAME-TIME-LAST-YEAR
  Now 66%   STLY 63%   delta +3.6 pts  (up)

  PER-LISTING (sorted by RevPAR)
  Beach House - Trigg                70%     $244     $170
  Coastal 2BR - Scarborough          63%     $188     $118
  Riverfront 1BR - South Perth       59%     $169     $100
  Hills Cottage - Kalamunda          38%     $158      $61
  CBD Studio - Perth                 44%     $135      $60

  ACTION LIST  (ranked by est. impact)
  [MEDIUM] CBD Studio - Perth        reduce_min_stay        +0%   $278
  [HIGH  ] Beach House - Trigg       last_minute_discount  -15%   $238
  [HIGH  ] Coastal 2BR - Scarborough last_minute_discount  -15%   $178
  [HIGH  ] Beach House - Trigg       raise_base_price       +8%    $40
  ...
  Estimated recoverable revenue this cycle: $1,808
```

## Data schema

`sample_data/calendar.csv` — one row per listing per night (mirrors a
PriceLabs/PMS calendar export):

```
listing,date,status,price,min_stay
Beach House - Trigg,2025-01-01,booked,268,2
```

`status` ∈ `booked` | `open` | `blocked`. `sample_data/market.csv` gives a
per-listing median market ADR (the comp-set benchmark PriceLabs
neighborhood data provides).

## Architecture

```
                 PriceLabs / PMS exports (CSV or API)
                              |
                    [ ingest + clean ]   one tidy row per listing-night
                              |
       +----------------------+----------------------+
       |                      |                      |
  metrics.py             metrics.py             signals.py
  ADR/Occ/RevPAR      pace vs STLY          4 decision rules
       |                      |                      |
       +----------------------+----------------------+
                              |
                    ranked action list  ->  dashboard + weekly report
                    (Streamlit / Looker Studio / Power BI)
```

- `pricelabs_analytics/metrics.py` — ADR / Occupancy / RevPAR, portfolio
  roll-up, forward pace vs STLY.
- `pricelabs_analytics/signals.py` — the four decision rules and impact
  estimates.
- `generate_sample_data.py` — deterministic synthetic data so the demo
  runs with no real inputs.
- `main.py` — end-to-end run and console report.

## Notes

- Dependency-light on purpose (pandas + numpy). The dashboard layer plugs
  onto the same functions.
- Sample numbers are illustrative; the logic is genuine and runs as shown.

---

*Dr. Sandeep Grover — PhD (Data Science). Data analyst & statistician
(Python, pandas, SQL, R, dashboards).*
