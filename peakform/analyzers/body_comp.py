"""Body composition analyzer.

Tracks scale weight, trend weight, deficit reality, and projected pace
to the 160 lb goal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from peakform.config import GOAL_WEIGHT_LBS, TRACKING_RESTART


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class BodyCompAnalysis:
    """Body composition analysis for a given week."""

    week_start: pd.Timestamp
    week_end: pd.Timestamp

    # Scale weight (raw daily readings)
    weight_start_lbs: Optional[float] = None   # first reading in the week
    weight_end_lbs: Optional[float] = None     # last reading in the week
    weight_avg_lbs: Optional[float] = None
    weight_net_change_lbs: Optional[float] = None
    body_fat_pct_latest: Optional[float] = None

    # Smoothed trend weight (MacroFactor trendline)
    trend_weight_start: Optional[float] = None
    trend_weight_end: Optional[float] = None
    trend_net_change_lbs: Optional[float] = None

    # Trend direction: "down", "flat", "up"
    trend_direction: str = "flat"

    # Goal projection
    pounds_to_goal: Optional[float] = None
    weekly_rate_lbs: Optional[float] = None    # based on trend change
    weeks_to_goal: Optional[float] = None
    projected_goal_date: Optional[date] = None

    # Flags
    weight_rising_despite_deficit: bool = False  # algorithm recalibrating
    trend_stalled: bool = False                  # <0.1 lb/week change

    # Contextual note
    algorithm_recalibrating: bool = False        # first 2-3 weeks post-restart


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_valid(series: pd.Series) -> Optional[float]:
    vals = series.dropna()
    return float(vals.iloc[0]) if len(vals) else None


def _last_valid(series: pd.Series) -> Optional[float]:
    vals = series.dropna()
    return float(vals.iloc[-1]) if len(vals) else None


def _week_slice(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return df[(df["date"] >= start) & (df["date"] <= end)].copy()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(
    mf_data,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
    avg_daily_deficit: Optional[float] = None,
) -> BodyCompAnalysis:
    """Run body composition analysis for the given week.

    Parameters
    ----------
    mf_data : MacroFactorData
    week_start, week_end : pd.Timestamp
    avg_daily_deficit : float, optional
        From nutrition analyzer — used to cross-check with weight trend.
    """
    result = BodyCompAnalysis(week_start=week_start, week_end=week_end)

    # ------------------------------------------------------------------
    # Scale weight
    # ------------------------------------------------------------------
    scale_df = mf_data.scale_weight
    if not scale_df.empty:
        week = _week_slice(scale_df, week_start, week_end)
        if not week.empty:
            weight_col = next(
                (c for c in week.columns if c not in ("date",) and "weight" in c.lower()),
                None,
            )
            fat_col = next(
                (c for c in week.columns if "fat" in c.lower() or "pct" in c.lower()),
                None,
            )
            if weight_col:
                w_series = week[weight_col].dropna()
                result.weight_start_lbs = _first_valid(w_series)
                result.weight_end_lbs = _last_valid(w_series)
                result.weight_avg_lbs = float(w_series.mean()) if len(w_series) else None
                if result.weight_start_lbs and result.weight_end_lbs:
                    result.weight_net_change_lbs = (
                        result.weight_end_lbs - result.weight_start_lbs
                    )
            if fat_col:
                fat_series = week[fat_col].dropna()
                result.body_fat_pct_latest = _last_valid(fat_series)

    # ------------------------------------------------------------------
    # Trend weight (MacroFactor smoothed trendline)
    # ------------------------------------------------------------------
    trend_df = mf_data.weight_trend
    if not trend_df.empty:
        week = _week_slice(trend_df, week_start, week_end)
        if not week.empty:
            trend_col = next(
                (c for c in week.columns if c not in ("date",) and "trend" in c.lower()),
                None,
            ) or next(
                (c for c in week.columns if c != "date"),
                None,
            )
            if trend_col:
                t_series = week[trend_col].dropna()
                result.trend_weight_start = _first_valid(t_series)
                result.trend_weight_end = _last_valid(t_series)
                if result.trend_weight_start and result.trend_weight_end:
                    result.trend_net_change_lbs = (
                        result.trend_weight_end - result.trend_weight_start
                    )

    # ------------------------------------------------------------------
    # Trend direction
    # ------------------------------------------------------------------
    if result.trend_net_change_lbs is not None:
        if result.trend_net_change_lbs < -0.1:
            result.trend_direction = "down"
        elif result.trend_net_change_lbs > 0.1:
            result.trend_direction = "up"
        else:
            result.trend_direction = "flat"
            result.trend_stalled = True

    # ------------------------------------------------------------------
    # Goal projection
    # ------------------------------------------------------------------
    current_weight = result.trend_weight_end or result.weight_end_lbs
    if current_weight:
        result.pounds_to_goal = current_weight - GOAL_WEIGHT_LBS

        # Use trend change as weekly rate (negative = losing weight)
        if result.trend_net_change_lbs and abs(result.trend_net_change_lbs) > 0.05:
            weekly_loss = -result.trend_net_change_lbs  # positive = losing
            result.weekly_rate_lbs = weekly_loss
            if weekly_loss > 0 and result.pounds_to_goal > 0:
                result.weeks_to_goal = result.pounds_to_goal / weekly_loss
                goal_days = int(result.weeks_to_goal * 7)
                result.projected_goal_date = (
                    week_end.date() + timedelta(days=goal_days)
                )
        elif avg_daily_deficit and avg_daily_deficit > 0:
            # Fallback: use deficit / 3500 calories per pound rule
            weekly_loss_from_deficit = avg_daily_deficit * 7 / 3500
            result.weekly_rate_lbs = weekly_loss_from_deficit
            if result.pounds_to_goal and result.pounds_to_goal > 0:
                result.weeks_to_goal = result.pounds_to_goal / weekly_loss_from_deficit
                goal_days = int(result.weeks_to_goal * 7)
                result.projected_goal_date = (
                    week_end.date() + timedelta(days=goal_days)
                )

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------
    # Weight rising despite reported deficit = algorithm recalibration
    if (
        avg_daily_deficit is not None
        and avg_daily_deficit > 0
        and result.trend_direction == "up"
    ):
        result.weight_rising_despite_deficit = True

    # Check if within first 2-3 weeks of tracking restart
    days_since_restart = (week_end.date() - TRACKING_RESTART).days
    if days_since_restart <= 21:
        result.algorithm_recalibrating = True

    return result
