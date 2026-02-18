"""Running metrics analyzer.

Computes weekly running stats (flat vs. trail) and compares against a
4-week rolling average for trend detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from peakform.config import BODY_BATTERY_DRAIN_CONCERN, MILEAGE_OVERREACH_PCT
from peakform.parsers.garmin import format_pace


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class RunWeekStats:
    """Running statistics for a single week."""

    week_start: pd.Timestamp
    week_end: pd.Timestamp

    # Totals
    total_miles: float = 0.0
    total_elevation_gain_ft: float = 0.0
    run_count: int = 0

    # Flat-run averages (ascent < 500 ft)
    flat_run_count: int = 0
    flat_avg_pace_dec: Optional[float] = None   # decimal minutes/mile
    flat_avg_hr: Optional[float] = None
    flat_avg_cadence: Optional[float] = None
    flat_avg_aerobic_te: Optional[float] = None
    flat_avg_ground_contact_ms: Optional[float] = None

    # Longest single run
    longest_run_miles: float = 0.0

    # Trail/mountain runs
    trail_run_count: int = 0
    trail_total_miles: float = 0.0
    trail_total_elevation_ft: float = 0.0

    # Recovery
    avg_body_battery_drain: Optional[float] = None
    max_body_battery_drain: Optional[float] = None

    # HR:pace efficiency (flat runs, HR per min/mile)
    hr_pace_efficiency: Optional[float] = None

    # -----------------------------------------------------------------------
    # Display helpers
    # -----------------------------------------------------------------------

    @property
    def flat_avg_pace_mmss(self) -> str:
        return format_pace(self.flat_avg_pace_dec) if self.flat_avg_pace_dec else "--"

    @property
    def flat_avg_hr_display(self) -> str:
        return f"{self.flat_avg_hr:.0f}" if self.flat_avg_hr else "--"

    @property
    def flat_avg_cadence_display(self) -> str:
        return f"{self.flat_avg_cadence:.0f}" if self.flat_avg_cadence else "--"


@dataclass
class RunningAnalysis:
    """Output of the running analyzer for a given week."""

    current: RunWeekStats
    rolling_4wk: RunWeekStats          # average over prior 4 weeks

    # Directional change flags (current vs. rolling avg)
    mileage_change_pct: Optional[float] = None
    pace_change_dec: Optional[float] = None       # negative = faster (improvement)
    hr_change: Optional[float] = None             # negative = lower (improvement)
    cadence_change: Optional[float] = None
    ground_contact_change_ms: Optional[float] = None

    # Flags
    overreach_flag: bool = False
    recovery_debt_flag: bool = False

    # Aerobic adaptation signal: pace down AND hr stable/down
    aerobic_adaptation_signal: bool = False

    # Fatigue signal: pace up AND hr up
    fatigue_signal: bool = False


# ---------------------------------------------------------------------------
# Helper: compute stats for one DataFrame of runs
# ---------------------------------------------------------------------------

def _compute_week_stats(
    all_runs: pd.DataFrame,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
) -> RunWeekStats:
    """Compute running stats for all runs in the given window."""
    stats = RunWeekStats(week_start=week_start, week_end=week_end)

    if all_runs.empty:
        return stats

    window = all_runs[
        (all_runs["date"] >= week_start) & (all_runs["date"] <= week_end)
    ].copy()

    if window.empty:
        return stats

    stats.run_count = len(window)
    stats.total_miles = window["distance_mi"].sum(skipna=True)
    stats.total_elevation_gain_ft = window["total_ascent_ft"].sum(skipna=True)

    if "distance_mi" in window.columns:
        stats.longest_run_miles = window["distance_mi"].max()

    # Flat runs
    flat = window[window["is_trail"] == False].copy()  # noqa: E712
    stats.flat_run_count = len(flat)

    if not flat.empty:
        pace_vals = flat["avg_pace"].dropna()
        hr_vals = flat["avg_hr"].dropna()
        cad_vals = flat["avg_cadence"].dropna()
        te_vals = flat["aerobic_te"].dropna()
        gct_vals = flat["avg_ground_contact_ms"].dropna() if "avg_ground_contact_ms" in flat.columns else pd.Series(dtype=float)

        if len(pace_vals):
            stats.flat_avg_pace_dec = pace_vals.mean()
        if len(hr_vals):
            stats.flat_avg_hr = hr_vals.mean()
        if len(cad_vals):
            stats.flat_avg_cadence = cad_vals.mean()
        if len(te_vals):
            stats.flat_avg_aerobic_te = te_vals.mean()
        if len(gct_vals):
            stats.flat_avg_ground_contact_ms = gct_vals.mean()

        if stats.flat_avg_hr and stats.flat_avg_pace_dec and stats.flat_avg_pace_dec > 0:
            stats.hr_pace_efficiency = stats.flat_avg_hr / stats.flat_avg_pace_dec

    # Trail runs
    trail = window[window["is_trail"] == True].copy()  # noqa: E712
    stats.trail_run_count = len(trail)
    if not trail.empty:
        stats.trail_total_miles = trail["distance_mi"].sum(skipna=True)
        stats.trail_total_elevation_ft = trail["total_ascent_ft"].sum(skipna=True)

    # Body battery drain
    bbd_col = "body_battery_drain"
    if bbd_col in window.columns:
        bbd_vals = window[bbd_col].dropna()
        if len(bbd_vals):
            stats.avg_body_battery_drain = bbd_vals.mean()
            stats.max_body_battery_drain = bbd_vals.max()

    return stats


def _compute_rolling_avg_stats(
    all_runs: pd.DataFrame,
    week_start: pd.Timestamp,
    num_prior_weeks: int = 4,
) -> RunWeekStats:
    """Compute the average RunWeekStats across the prior N weeks."""
    prior_stats: List[RunWeekStats] = []
    for i in range(1, num_prior_weeks + 1):
        w_end = week_start - pd.Timedelta(days=1 + 7 * (i - 1))
        w_start = w_end - pd.Timedelta(days=6)
        s = _compute_week_stats(all_runs, w_start, w_end)
        prior_stats.append(s)

    # Average non-None fields
    def _avg(vals):
        clean = [v for v in vals if v is not None and not np.isnan(v)]
        return np.mean(clean) if clean else None

    avg = RunWeekStats(week_start=week_start, week_end=week_start)
    avg.total_miles = _avg([s.total_miles for s in prior_stats]) or 0.0
    avg.total_elevation_gain_ft = _avg([s.total_elevation_gain_ft for s in prior_stats]) or 0.0
    avg.run_count = round(_avg([s.run_count for s in prior_stats]) or 0)
    avg.flat_avg_pace_dec = _avg([s.flat_avg_pace_dec for s in prior_stats])
    avg.flat_avg_hr = _avg([s.flat_avg_hr for s in prior_stats])
    avg.flat_avg_cadence = _avg([s.flat_avg_cadence for s in prior_stats])
    avg.flat_avg_aerobic_te = _avg([s.flat_avg_aerobic_te for s in prior_stats])
    avg.flat_avg_ground_contact_ms = _avg([s.flat_avg_ground_contact_ms for s in prior_stats])
    avg.longest_run_miles = _avg([s.longest_run_miles for s in prior_stats]) or 0.0
    avg.trail_run_count = round(_avg([s.trail_run_count for s in prior_stats]) or 0)
    avg.avg_body_battery_drain = _avg([s.avg_body_battery_drain for s in prior_stats])
    return avg


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(
    garmin_data,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
) -> RunningAnalysis:
    """Run the full running analysis for the given week.

    Parameters
    ----------
    garmin_data : GarminData
        Parsed Garmin data.
    week_start, week_end : pd.Timestamp
        Mon–Sun boundaries of the analysis week.
    """
    all_runs = garmin_data.runs

    current = _compute_week_stats(all_runs, week_start, week_end)
    rolling = _compute_rolling_avg_stats(all_runs, week_start, num_prior_weeks=4)

    result = RunningAnalysis(current=current, rolling_4wk=rolling)

    # Mileage change %
    if rolling.total_miles and rolling.total_miles > 0:
        result.mileage_change_pct = (
            (current.total_miles - rolling.total_miles) / rolling.total_miles
        )
        result.overreach_flag = result.mileage_change_pct > MILEAGE_OVERREACH_PCT

    # Pace change (negative = improvement)
    if current.flat_avg_pace_dec and rolling.flat_avg_pace_dec:
        result.pace_change_dec = current.flat_avg_pace_dec - rolling.flat_avg_pace_dec

    # HR change
    if current.flat_avg_hr and rolling.flat_avg_hr:
        result.hr_change = current.flat_avg_hr - rolling.flat_avg_hr

    # Ground contact change
    if current.flat_avg_ground_contact_ms and rolling.flat_avg_ground_contact_ms:
        result.ground_contact_change_ms = (
            current.flat_avg_ground_contact_ms - rolling.flat_avg_ground_contact_ms
        )

    # Cadence change
    if current.flat_avg_cadence and rolling.flat_avg_cadence:
        result.cadence_change = current.flat_avg_cadence - rolling.flat_avg_cadence

    # Aerobic adaptation: pace improved (pace_change < 0) AND HR stable or lower
    if result.pace_change_dec is not None and result.hr_change is not None:
        if result.pace_change_dec < -0.05 and result.hr_change <= 2:
            result.aerobic_adaptation_signal = True

    # Fatigue signal: pace slower AND HR higher
    if result.pace_change_dec is not None and result.hr_change is not None:
        if result.pace_change_dec > 0.05 and result.hr_change > 2:
            result.fatigue_signal = True

    # Recovery debt
    bbd = current.avg_body_battery_drain
    if bbd is not None and bbd > BODY_BATTERY_DRAIN_CONCERN:
        result.recovery_debt_flag = True

    return result
