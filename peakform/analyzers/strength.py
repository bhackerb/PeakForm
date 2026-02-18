"""Strength training analyzer.

Pulls sets-per-muscle-group and heaviest weight data from MacroFactor sheets,
checks progressive overload, and flags missed muscle groups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from peakform.config import PRIORITY_MUSCLE_GROUPS


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class StrengthWeekStats:
    """Strength metrics for a single week."""

    week_start: pd.Timestamp
    week_end: pd.Timestamp

    # Workouts logged (days with any exercise recorded)
    workout_days: int = 0

    # Sets per muscle group  {muscle_group: total_sets}
    sets_by_muscle: Dict[str, float] = field(default_factory=dict)

    # Heaviest weight per exercise  {exercise: max_weight_lbs}
    heaviest_by_exercise: Dict[str, float] = field(default_factory=dict)

    # Total volume per exercise  {exercise: total_lbs}
    volume_by_exercise: Dict[str, float] = field(default_factory=dict)


@dataclass
class StrengthAnalysis:
    """Output of the strength analyzer for a given week."""

    current: StrengthWeekStats
    prior_4wk_avg: Optional[StrengthWeekStats] = None

    # Progressive overload — exercises where this week's max > prior 4-wk max
    pr_exercises: List[str] = field(default_factory=list)

    # Exercises where this week's max regressed vs. prior best
    regression_exercises: List[str] = field(default_factory=list)

    # Muscle groups with 0 sets this week (potential missed day)
    missed_muscle_groups: List[str] = field(default_factory=list)

    # Muscle groups where volume dropped >25% vs. prior 4-wk avg
    volume_drop_flags: Dict[str, float] = field(default_factory=dict)  # {group: pct_drop}


# ---------------------------------------------------------------------------
# Helper: extract data for one week from MacroFactor sheets
# ---------------------------------------------------------------------------

def _week_sets(muscle_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> Dict[str, float]:
    if muscle_df.empty:
        return {}
    window = muscle_df[(muscle_df["date"] >= start) & (muscle_df["date"] <= end)]
    if window.empty:
        return {}
    numeric_cols = [c for c in window.columns if c != "date"]
    sums = window[numeric_cols].sum(skipna=True)
    return {col: float(sums[col]) for col in sums.index if sums[col] > 0}


def _week_heaviest(heaviest_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> Dict[str, float]:
    if heaviest_df.empty:
        return {}
    window = heaviest_df[(heaviest_df["date"] >= start) & (heaviest_df["date"] <= end)]
    if window.empty:
        return {}
    numeric_cols = [c for c in window.columns if c != "date"]
    maxes = window[numeric_cols].max(skipna=True)
    return {col: float(maxes[col]) for col in maxes.index if not np.isnan(maxes[col]) and maxes[col] > 0}


def _week_volume(volume_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> Dict[str, float]:
    if volume_df.empty:
        return {}
    window = volume_df[(volume_df["date"] >= start) & (volume_df["date"] <= end)]
    if window.empty:
        return {}
    numeric_cols = [c for c in window.columns if c != "date"]
    sums = window[numeric_cols].sum(skipna=True)
    return {col: float(sums[col]) for col in sums.index if sums[col] > 0}


def _workout_days(muscle_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Count days in the window that have at least one exercise set logged."""
    if muscle_df.empty:
        return 0
    window = muscle_df[(muscle_df["date"] >= start) & (muscle_df["date"] <= end)]
    if window.empty:
        return 0
    numeric_cols = [c for c in window.columns if c != "date"]
    row_has_data = window[numeric_cols].sum(axis=1) > 0
    return int(row_has_data.sum())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(
    mf_data,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
) -> StrengthAnalysis:
    """Run the full strength analysis for the given week.

    Parameters
    ----------
    mf_data : MacroFactorData
        Parsed MacroFactor XLSX data.
    week_start, week_end : pd.Timestamp
        Mon–Sun window.
    """
    muscle_df = mf_data.muscle_groups
    heaviest_df = mf_data.exercises_heaviest
    volume_df = mf_data.exercises_volume

    # Current week
    current = StrengthWeekStats(week_start=week_start, week_end=week_end)
    current.workout_days = _workout_days(muscle_df, week_start, week_end)
    current.sets_by_muscle = _week_sets(muscle_df, week_start, week_end)
    current.heaviest_by_exercise = _week_heaviest(heaviest_df, week_start, week_end)
    current.volume_by_exercise = _week_volume(volume_df, week_start, week_end)

    # Prior 4-week average
    prior_sets_list: List[Dict[str, float]] = []
    prior_heaviest_list: List[Dict[str, float]] = []
    for i in range(1, 5):
        w_end = week_start - pd.Timedelta(days=1 + 7 * (i - 1))
        w_start = w_end - pd.Timedelta(days=6)
        prior_sets_list.append(_week_sets(muscle_df, w_start, w_end))
        prior_heaviest_list.append(_week_heaviest(heaviest_df, w_start, w_end))

    # Build averaged prior stats
    prior_avg = StrengthWeekStats(week_start=week_start, week_end=week_end)
    all_muscle_groups = set()
    for d in prior_sets_list:
        all_muscle_groups.update(d.keys())
    for mg in all_muscle_groups:
        vals = [d[mg] for d in prior_sets_list if mg in d]
        if vals:
            prior_avg.sets_by_muscle[mg] = np.mean(vals)

    all_exercises = set()
    for d in prior_heaviest_list:
        all_exercises.update(d.keys())
    for ex in all_exercises:
        vals = [d[ex] for d in prior_heaviest_list if ex in d and d[ex] > 0]
        if vals:
            prior_avg.heaviest_by_exercise[ex] = max(vals)  # best prior max

    # Build analysis
    analysis = StrengthAnalysis(current=current, prior_4wk_avg=prior_avg)

    # Progressive overload / regression detection
    for ex, cur_max in current.heaviest_by_exercise.items():
        if ex in prior_avg.heaviest_by_exercise:
            prior_max = prior_avg.heaviest_by_exercise[ex]
            if cur_max > prior_max:
                analysis.pr_exercises.append(f"{ex}: {prior_max:.0f} → {cur_max:.0f} lbs")
            elif cur_max < prior_max * 0.95:  # >5% regression
                analysis.regression_exercises.append(f"{ex}: {prior_max:.0f} → {cur_max:.0f} lbs")

    # Missed muscle groups — flag priority groups with 0 sets
    for mg in PRIORITY_MUSCLE_GROUPS:
        # Fuzzy match against actual column names
        matched = False
        for col in current.sets_by_muscle:
            if mg.lower() in col.lower():
                matched = True
                break
        if not matched:
            analysis.missed_muscle_groups.append(mg)

    # Volume drop flags (>25% drop vs. 4-wk avg)
    for mg, avg_sets in prior_avg.sets_by_muscle.items():
        if avg_sets > 0:
            cur_sets = current.sets_by_muscle.get(mg, 0.0)
            drop_pct = (avg_sets - cur_sets) / avg_sets
            if drop_pct > 0.25:
                analysis.volume_drop_flags[mg] = round(drop_pct * 100, 1)

    return analysis
