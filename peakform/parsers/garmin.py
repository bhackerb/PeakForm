"""Garmin Connect CSV parser.

Handles:
- Comma-formatted numeric strings ("8,980" → 8980)
- Pace stored as "MM:SS" string → decimal minutes
- "--" sentinel → NaN
- Body Battery Drain stored as negative → absolute value
- Trail run classification (Total Ascent > 500 ft)
- Activity type filtering (running vs. strength)
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import numpy as np

from peakform.config import (
    RUNNING_ACTIVITY_TYPES,
    STRENGTH_ACTIVITY_TYPES,
    TRAIL_RUN_ASCENT_FT,
)


# ---------------------------------------------------------------------------
# Column name mapping — Garmin export header → internal snake_case name
# ---------------------------------------------------------------------------

_COL_MAP = {
    "Activity Type": "activity_type",
    "Date": "date",
    "Favorite": "favorite",
    "Title": "title",
    "Distance": "distance_mi",
    "Calories": "calories",
    "Time": "duration",
    "Avg HR": "avg_hr",
    "Max HR": "max_hr",
    "Aerobic TE": "aerobic_te",
    "Avg Run Cadence": "avg_cadence",
    "Max Run Cadence": "max_cadence",
    "Avg Pace": "avg_pace",
    "Best Pace": "best_pace",
    "Total Ascent": "total_ascent_ft",
    "Total Descent": "total_descent_ft",
    "Avg Stride Length": "avg_stride_length",
    "Avg Vertical Ratio": "avg_vertical_ratio",
    "Avg Vertical Oscillation": "avg_vertical_osc",
    "Avg Ground Contact Time": "avg_ground_contact_ms",
    "Avg GAP": "avg_gap",
    "Normalized Power": "normalized_power",
    "Avg Power": "avg_power",
    "Body Battery Drain": "body_battery_drain",
    "Moving Time": "moving_time",
    "Elapsed Time": "elapsed_time",
    "Min Elevation": "min_elevation_ft",
    "Max Elevation": "max_elevation_ft",
}

# Columns that must be converted from "MM:SS" pace string to decimal minutes
_PACE_COLS = {"avg_pace", "best_pace", "avg_gap"}

# Columns with comma-formatted integers
_COMMA_NUMERIC_COLS = {
    "calories",
    "total_ascent_ft",
    "total_descent_ft",
    "normalized_power",
    "avg_power",
}


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _strip_comma_numeric(value) -> Optional[float]:
    """Convert "8,980" → 8980.0; returns NaN for "--" or unparsable values."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    s = str(value).strip()
    if s in ("--", "", "nan"):
        return np.nan
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return np.nan


def _pace_to_decimal_minutes(value) -> Optional[float]:
    """Convert "MM:SS" pace string to decimal minutes.

    Examples:
        "8:15"  → 8.25
        "10:00" → 10.0
        "--"    → NaN
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    s = str(value).strip()
    if s in ("--", "", "nan"):
        return np.nan
    m = re.match(r"^(\d+):(\d{2})$", s)
    if m:
        minutes = int(m.group(1))
        seconds = int(m.group(2))
        return minutes + seconds / 60.0
    try:
        return float(s)
    except ValueError:
        return np.nan


def _decimal_minutes_to_mmss(decimal_minutes: float) -> str:
    """Convert decimal minutes back to MM:SS string for display."""
    if pd.isna(decimal_minutes):
        return "--"
    total_seconds = round(decimal_minutes * 60)
    m = total_seconds // 60
    s = total_seconds % 60
    return f"{m}:{s:02d}"


def _clean_generic(value) -> Optional[float]:
    """Convert a generic cell (possibly "--") to float."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    s = str(value).strip()
    if s in ("--", "", "nan"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def _parse_duration(value) -> Optional[float]:
    """Parse duration HH:MM:SS → total seconds."""
    if value is None:
        return np.nan
    s = str(value).strip()
    if s in ("--", "", "nan"):
        return np.nan
    parts = s.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(s)
    except ValueError:
        return np.nan


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

class GarminData:
    """Container for parsed Garmin CSV activity data."""

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._raw: pd.DataFrame = self._load(filepath)

    def _load(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath, low_memory=False)

        # Rename columns to internal names
        rename = {k: v for k, v in _COL_MAP.items() if k in df.columns}
        df = df.rename(columns=rename)

        # Date parsing
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Clean pace columns
        for col in _PACE_COLS:
            if col in df.columns:
                df[col] = df[col].apply(_pace_to_decimal_minutes)

        # Clean comma-formatted numeric columns
        for col in _COMMA_NUMERIC_COLS:
            if col in df.columns:
                df[col] = df[col].apply(_strip_comma_numeric)

        # All remaining non-date / non-string columns: clean "--"
        skip = {"activity_type", "date", "title", "favorite", "duration",
                 "moving_time", "elapsed_time"} | _PACE_COLS | _COMMA_NUMERIC_COLS
        for col in df.columns:
            if col not in skip:
                df[col] = df[col].apply(_clean_generic)

        # Duration → seconds
        for col in ("duration", "moving_time", "elapsed_time"):
            if col in df.columns:
                df[col] = df[col].apply(_parse_duration)

        # Body Battery Drain: use absolute value (stored as negative integer)
        if "body_battery_drain" in df.columns:
            df["body_battery_drain"] = df["body_battery_drain"].abs()

        # Ground contact time: may be stored as "250ms" string
        if "avg_ground_contact_ms" in df.columns:
            df["avg_ground_contact_ms"] = (
                df["avg_ground_contact_ms"]
                .astype(str)
                .str.replace("ms", "", regex=False)
                .str.strip()
                .apply(_clean_generic)
            )

        # Trail run flag
        if "total_ascent_ft" in df.columns:
            df["is_trail"] = df["total_ascent_ft"] > TRAIL_RUN_ASCENT_FT
        else:
            df["is_trail"] = False

        df = df.sort_values("date").reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Filtered views
    # ------------------------------------------------------------------

    @property
    def all_activities(self) -> pd.DataFrame:
        return self._raw.copy()

    @property
    def runs(self) -> pd.DataFrame:
        """All running activities (road + trail + treadmill)."""
        mask = self._raw["activity_type"].isin(RUNNING_ACTIVITY_TYPES)
        return self._raw[mask].copy()

    @property
    def flat_runs(self) -> pd.DataFrame:
        """Runs where total ascent < 500 ft (excludes trail/mountain runs)."""
        runs = self.runs
        mask = (runs["is_trail"] == False)  # noqa: E712
        return runs[mask].copy()

    @property
    def trail_runs(self) -> pd.DataFrame:
        """Runs where total ascent >= 500 ft."""
        runs = self.runs
        return runs[runs["is_trail"] == True].copy()  # noqa: E712

    @property
    def strength_sessions(self) -> pd.DataFrame:
        mask = self._raw["activity_type"].isin(STRENGTH_ACTIVITY_TYPES)
        return self._raw[mask].copy()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def week_window(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Filter all activities to a Mon–Sun window (inclusive)."""
        mask = (self._raw["date"] >= start) & (self._raw["date"] <= end)
        return self._raw[mask].copy()

    def runs_in_window(
        self, start: pd.Timestamp, end: pd.Timestamp, trail_only: bool = False
    ) -> pd.DataFrame:
        df = self.runs
        mask = (df["date"] >= start) & (df["date"] <= end)
        df = df[mask].copy()
        if trail_only:
            df = df[df["is_trail"] == True]  # noqa: E712
        return df


def load(filepath: str) -> GarminData:
    """Load and parse a Garmin Connect CSV export."""
    return GarminData(filepath)


# ---------------------------------------------------------------------------
# Pace display helper (used by report formatter)
# ---------------------------------------------------------------------------

def format_pace(decimal_minutes: float) -> str:
    """Return a human-readable MM:SS pace string."""
    return _decimal_minutes_to_mmss(decimal_minutes)
