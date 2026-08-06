"""
Turn metrics into *decisions*.

These are the rules that make the difference between a dashboard that
describes the past and one that tells you what to change tomorrow:

  1. high_occupancy_below_market  -> raise base price
  2. soft_pace_far_out            -> lower far-out price
  3. min_stay_blocking            -> reduce minimum stay
  4. orphan_night                 -> last-minute discount

Each rule emits a structured recommendation with an *estimated* revenue
impact so the action list can be ranked by dollars, not alphabetically.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd


def _fwd(cal: pd.DataFrame, listing: str, as_of: pd.Timestamp, days: int) -> pd.DataFrame:
    end = as_of + pd.Timedelta(days=days)
    m = (cal["listing"] == listing) & (cal["date"] >= as_of) & (cal["date"] < end)
    return cal[m]


def find_actions(
    calendar: pd.DataFrame,
    market: pd.DataFrame,
    as_of: dt.date,
    near_days: int = 21,
    far_days: tuple[int, int] = (30, 60),
) -> pd.DataFrame:
    """Scan every listing and return a ranked action list.

    `market` supplies a per-listing median market ADR (market_adr_p50),
    the comp-set benchmark PriceLabs neighborhood data would provide.
    """
    cal = calendar.copy()
    cal["date"] = pd.to_datetime(cal["date"])
    cal["status"] = cal["status"].str.lower()
    as_of = pd.Timestamp(as_of)
    mkt = dict(zip(market["listing"], market["market_adr_p50"]))

    actions: list[dict] = []

    for listing in sorted(cal["listing"].unique()):
        near = _fwd(cal, listing, as_of, near_days)
        if near.empty:
            continue
        avail = (near["status"] != "blocked").sum()
        booked_mask = near["status"] == "booked"
        occ = booked_mask.sum() / avail if avail else 0.0
        cur_adr = near.loc[booked_mask, "price"].mean()
        if pd.isna(cur_adr):
            cur_adr = near["price"].mean()
        market_adr = mkt.get(listing, cur_adr)

        # Rule 1 -- selling out below market -> raise
        if occ >= 0.85 and cur_adr < market_adr * 0.95:
            lift = min(0.20, (market_adr - cur_adr) / cur_adr)
            remaining = int((near["status"] != "booked").sum())
            impact = remaining * cur_adr * lift
            actions.append(
                _rec(listing, as_of, near_days, occ, cur_adr, market_adr,
                     "high_occupancy_below_market", "raise_base_price",
                     round(lift * 100, 1), impact, "high")
            )

        # Rule 2 -- forward window pacing soft -> lower far-out
        far = _fwd(cal, listing, as_of + pd.Timedelta(days=far_days[0]),
                   far_days[1] - far_days[0])
        if not far.empty:
            f_avail = (far["status"] != "blocked").sum()
            f_occ = (far["status"] == "booked").sum() / f_avail if f_avail else 0.0
            if f_occ < 0.35:
                open_nights = int((far["status"] == "open").sum())
                impact = open_nights * far["price"].mean() * 0.10 * 0.5
                actions.append(
                    _rec(listing, as_of + pd.Timedelta(days=far_days[0]),
                         far_days[1] - far_days[0], f_occ, far["price"].mean(),
                         market_adr, "soft_pace_far_out", "lower_far_out_price",
                         -8.0, impact, "medium")
                )

        # Rule 3 -- minimum stay blocking short-stay demand
        min_stay = int(near["min_stay"].iloc[0]) if "min_stay" in near.columns else 1
        if min_stay >= 3 and occ < 0.65:
            blocked_nights = _min_stay_blocked_nights(near, min_stay)
            if blocked_nights >= 3:
                impact = blocked_nights * cur_adr * 0.5
                actions.append(
                    _rec(listing, as_of, near_days, occ, cur_adr, market_adr,
                         "min_stay_blocking", "reduce_min_stay", 0.0, impact, "medium")
                )

        # Rule 4 -- orphan nights (single open night wedged between stays)
        orphans = _orphan_nights(cal, listing, as_of, near_days)
        for night in orphans:
            price = cal[(cal["listing"] == listing) & (cal["date"] == night)]["price"].iloc[0]
            actions.append(
                _rec(listing, night, 1, 0.0, price, market_adr,
                     "orphan_night", "last_minute_discount", -15.0, price * 0.85, "high")
            )

    if not actions:
        return pd.DataFrame(
            columns=["listing", "window_start", "window_nights", "occupancy",
                     "current_adr", "market_adr_p50", "signal", "recommendation",
                     "suggested_change_pct", "est_revenue_impact", "confidence"]
        )
    out = pd.DataFrame(actions).sort_values(
        "est_revenue_impact", ascending=False
    ).reset_index(drop=True)
    return out


def _min_stay_blocked_nights(near: pd.DataFrame, min_stay: int) -> int:
    """Count open nights sitting in gaps shorter than the minimum stay.

    A run of consecutive open nights whose length is < min_stay cannot be
    booked at all under the current rule -> those nights are lost demand.
    """
    seq = list(near.sort_values("date")["status"])
    blocked = 0
    run = 0
    for s in seq + ["booked"]:  # sentinel closes the final run
        if s == "open":
            run += 1
        else:
            if 0 < run < min_stay:
                blocked += run
            run = 0
    return blocked


def _orphan_nights(cal, listing, as_of, days) -> list:
    win = _fwd(cal, listing, as_of, days).sort_values("date")
    statuses = list(zip(win["date"], win["status"]))
    orphans = []
    for i in range(1, len(statuses) - 1):
        prev_s, cur_s, next_s = statuses[i - 1][1], statuses[i][1], statuses[i + 1][1]
        if cur_s == "open" and prev_s == "booked" and next_s == "booked":
            orphans.append(statuses[i][0])
    return orphans


def _rec(listing, start, nights, occ, cur_adr, market_adr, signal, rec,
         change_pct, impact, confidence) -> dict:
    return {
        "listing": listing,
        "window_start": pd.Timestamp(start).date().isoformat(),
        "window_nights": int(nights),
        "occupancy": round(float(occ), 3),
        "current_adr": round(float(cur_adr), 2),
        "market_adr_p50": round(float(market_adr), 2),
        "signal": signal,
        "recommendation": rec,
        "suggested_change_pct": change_pct,
        "est_revenue_impact": round(float(impact), 2),
        "confidence": confidence,
    }
