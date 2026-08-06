"""
Core short-term-rental revenue metrics.

Everything here is deliberately dependency-light (pandas only) and
uses the standard STR definitions a PriceLabs user already thinks in:

    ADR      = booked revenue / booked nights
    Occupancy= booked nights / available nights
    RevPAR   = booked revenue / available nights  ( = ADR * Occupancy )

Pacing compares a forward window this year against the *same window*
last year (same-time-last-year, "STLY") so seasonality cancels out.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd


@dataclass
class ListingMetrics:
    listing: str
    booked_nights: int
    available_nights: int
    revenue: float

    @property
    def occupancy(self) -> float:
        return self.booked_nights / self.available_nights if self.available_nights else 0.0

    @property
    def adr(self) -> float:
        return self.revenue / self.booked_nights if self.booked_nights else 0.0

    @property
    def revpar(self) -> float:
        return self.revenue / self.available_nights if self.available_nights else 0.0


def _nightly_frame(calendar: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise the nightly calendar frame."""
    required = {"listing", "date", "status", "price"}
    missing = required - set(calendar.columns)
    if missing:
        raise ValueError(f"calendar is missing columns: {sorted(missing)}")
    cal = calendar.copy()
    cal["date"] = pd.to_datetime(cal["date"])
    cal["status"] = cal["status"].str.lower()
    return cal


def listing_metrics(calendar: pd.DataFrame) -> pd.DataFrame:
    """ADR / Occupancy / RevPAR per listing over the whole calendar.

    A night counts as *available* unless it is host-blocked; a *booked*
    night is one with status == "booked". This mirrors how PriceLabs and
    the major PMSs treat blocked vs. available inventory.
    """
    cal = _nightly_frame(calendar)
    rows = []
    for listing, grp in cal.groupby("listing"):
        available = int((grp["status"] != "blocked").sum())
        booked_mask = grp["status"] == "booked"
        booked = int(booked_mask.sum())
        revenue = float(grp.loc[booked_mask, "price"].sum())
        m = ListingMetrics(listing, booked, available, revenue)
        rows.append(
            {
                "listing": listing,
                "available_nights": m.available_nights,
                "booked_nights": m.booked_nights,
                "occupancy": round(m.occupancy, 4),
                "adr": round(m.adr, 2),
                "revpar": round(m.revpar, 2),
                "revenue": round(m.revenue, 2),
            }
        )
    out = pd.DataFrame(rows).sort_values("revpar", ascending=False).reset_index(drop=True)
    return out


def portfolio_kpis(metrics: pd.DataFrame) -> dict:
    """Roll listing metrics up to a portfolio summary (occupancy-weighted ADR)."""
    available = metrics["available_nights"].sum()
    booked = metrics["booked_nights"].sum()
    revenue = metrics["revenue"].sum()
    return {
        "listings": int(len(metrics)),
        "available_nights": int(available),
        "booked_nights": int(booked),
        "occupancy": round(booked / available, 4) if available else 0.0,
        "adr": round(revenue / booked, 2) if booked else 0.0,
        "revpar": round(revenue / available, 2) if available else 0.0,
        "revenue": round(float(revenue), 2),
    }


def pace_vs_stly(
    calendar: pd.DataFrame,
    as_of: dt.date,
    horizon_days: int = 30,
) -> pd.DataFrame:
    """Forward booking pace for the next `horizon_days`, this year vs last.

    Returns occupancy of the forward window now, and the occupancy of the
    equivalent window 364 days ago (same weekday alignment). A negative
    delta means we are booking *slower* than last year -> soften far-out
    pricing before the window closes.
    """
    cal = _nightly_frame(calendar)
    as_of = pd.Timestamp(as_of)

    def _window_occ(start: pd.Timestamp) -> float:
        end = start + pd.Timedelta(days=horizon_days)
        win = cal[(cal["date"] >= start) & (cal["date"] < end)]
        avail = (win["status"] != "blocked").sum()
        booked = (win["status"] == "booked").sum()
        return booked / avail if avail else 0.0

    this_year = _window_occ(as_of)
    last_year = _window_occ(as_of - pd.Timedelta(days=364))
    return pd.DataFrame(
        [
            {
                "window": f"next {horizon_days}d",
                "pace_now": round(this_year, 4),
                "pace_stly": round(last_year, 4),
                "delta_pts": round((this_year - last_year) * 100, 1),
            }
        ]
    )
