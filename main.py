"""
PriceLabs pricing-analytics demo -- end-to-end run.

    python generate_sample_data.py   # once, writes sample_data/*.csv
    python main.py                    # prints portfolio KPIs, pacing, action list

Reads a nightly calendar + a market comp file, computes ADR/Occupancy/RevPAR,
forward pace vs same-time-last-year, and a ranked, dollar-impact action list.

This is a working sample of the engine behind the dashboard blueprint. In a
real engagement it reads your actual PriceLabs / PMS exports and feeds a
Streamlit / Looker Studio / Power BI dashboard.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

DATA = Path(__file__).parent / "sample_data"
AS_OF = dt.date(2026, 1, 5)   # pretend "today"; summer peak + STLY data available


def _load():
    import pandas as pd
    if not (DATA / "calendar.csv").exists():
        print("sample_data/calendar.csv not found -- run:  python generate_sample_data.py")
        sys.exit(1)
    calendar = pd.read_csv(DATA / "calendar.csv")
    market = pd.read_csv(DATA / "market.csv")
    return calendar, market


def _fmt_money(x: float) -> str:
    return f"${x:,.0f}"


def main() -> None:
    try:
        import pandas as pd  # noqa: F401
    except ImportError:
        print("This demo needs pandas:  pip install -r requirements.txt")
        sys.exit(1)

    from pricelabs_analytics import (
        listing_metrics,
        portfolio_kpis,
        pace_vs_stly,
        find_actions,
    )

    calendar, market = _load()

    metrics = listing_metrics(calendar)
    kpis = portfolio_kpis(metrics)
    pace = pace_vs_stly(calendar, AS_OF, horizon_days=30)
    actions = find_actions(calendar, market, AS_OF)

    print("=" * 68)
    print("  PORTFOLIO KPIs")
    print("=" * 68)
    print(f"  Listings        {kpis['listings']}")
    print(f"  Occupancy       {kpis['occupancy'] * 100:5.1f}%")
    print(f"  ADR             {_fmt_money(kpis['adr'])}")
    print(f"  RevPAR          {_fmt_money(kpis['revpar'])}")
    print(f"  Revenue (13mo)  {_fmt_money(kpis['revenue'])}")

    print("\n" + "=" * 68)
    print("  NEXT-30-DAY PACE vs SAME-TIME-LAST-YEAR")
    print("=" * 68)
    row = pace.iloc[0]
    arrow = "up" if row["delta_pts"] >= 0 else "DOWN"
    print(f"  Now {row['pace_now']*100:.0f}%   STLY {row['pace_stly']*100:.0f}%"
          f"   delta {row['delta_pts']:+.1f} pts  ({arrow})")

    print("\n" + "=" * 68)
    print("  PER-LISTING (sorted by RevPAR)")
    print("=" * 68)
    print(f"  {'Listing':<32}{'Occ':>6}{'ADR':>9}{'RevPAR':>9}")
    for _, r in metrics.iterrows():
        print(f"  {r['listing'][:31]:<32}{r['occupancy']*100:5.0f}%"
              f"{_fmt_money(r['adr']):>9}{_fmt_money(r['revpar']):>9}")

    print("\n" + "=" * 68)
    print(f"  ACTION LIST  (as of {AS_OF},  ranked by est. impact)")
    print("=" * 68)
    if actions.empty:
        print("  No actions triggered.")
    else:
        for _, a in actions.iterrows():
            print(f"  [{a['confidence'].upper():<6}] {a['listing'][:28]:<29}"
                  f"{a['recommendation']:<22}{a['suggested_change_pct']:+.0f}%"
                  f"   {_fmt_money(a['est_revenue_impact']):>7}")
        total = actions["est_revenue_impact"].sum()
        print("-" * 68)
        print(f"  Estimated recoverable revenue this cycle: {_fmt_money(total)}")


if __name__ == "__main__":
    main()
