"""PeakForm Agent — Main orchestrator.

Loads data from MacroFactor (XLSX) and Garmin (CSV), runs all analyzers
for the specified week, and returns the formatted weekly report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from peakform.parsers import macrofactor, garmin
from peakform.analyzers import running, strength, nutrition, body_comp, signals
from peakform.report import formatter


@dataclass
class RunResult:
    """Everything produced by a full analysis run."""
    report_md: str
    mf_data: macrofactor.MacroFactorData
    garmin_data: garmin.GarminData
    week_start: pd.Timestamp
    week_end: pd.Timestamp


# ---------------------------------------------------------------------------
# Week boundary helpers
# ---------------------------------------------------------------------------

def _current_week_bounds() -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return Mon–Sun bounds for the current calendar week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return pd.Timestamp(monday), pd.Timestamp(sunday)


def _week_bounds_for_date(target: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return the Mon–Sun week containing the given date."""
    monday = target - timedelta(days=target.weekday())
    sunday = monday + timedelta(days=6)
    return pd.Timestamp(monday), pd.Timestamp(sunday)


def _parse_week_arg(week_str: Optional[str]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Parse a user-supplied week string (YYYY-MM-DD) into Mon–Sun bounds.

    Accepts any date within the desired week (Mon–Sun). Defaults to current
    week if None.
    """
    if not week_str:
        return _current_week_bounds()
    try:
        target = date.fromisoformat(week_str)
        return _week_bounds_for_date(target)
    except ValueError:
        raise ValueError(
            f"Invalid --week value '{week_str}'. Expected ISO date format: YYYY-MM-DD"
        )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_data_coverage(
    mf_data: macrofactor.MacroFactorData,
    garmin_data: garmin.GarminData,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
) -> list[str]:
    """Return a list of validation warnings for the analysis window."""
    warnings: list[str] = []

    # MacroFactor: logged days
    cm_df = mf_data.calories_macros
    if not cm_df.empty:
        week_cm = cm_df[(cm_df["date"] >= week_start) & (cm_df["date"] <= week_end)]
        logged_days = len(week_cm)
        if logged_days < 5:
            warnings.append(
                f"MacroFactor: only {logged_days} logged day(s) in the analysis window "
                "(need ≥5 for complete analysis). Metrics will be partial."
            )
    else:
        warnings.append("MacroFactor: Calories & Macros sheet is empty or missing.")

    # Garmin: gap detection
    runs = garmin_data.runs_in_window(week_start, week_end)
    if not runs.empty:
        dates = runs["date"].dt.date.tolist()
        dates_sorted = sorted(set(dates))
        max_gap = 0
        for i in range(1, len(dates_sorted)):
            gap = (dates_sorted[i] - dates_sorted[i - 1]).days
            max_gap = max(max_gap, gap)
        if max_gap > 2:
            warnings.append(
                f"Garmin: gap of {max_gap} days between run activities — "
                "possible sync issue or intentional rest block."
            )
    else:
        warnings.append("Garmin: no running activities found in the analysis window.")

    # Anomaly checks
    if not cm_df.empty and not runs.empty:
        # Single-day calorie spike >3000
        week_cm_all = cm_df[(cm_df["date"] >= week_start) & (cm_df["date"] <= week_end)]
        cal_col = next(
            (c for c in week_cm_all.columns if "calorie" in c.lower() or "kcal" in c.lower()),
            None,
        )
        if cal_col:
            spikes = week_cm_all[week_cm_all[cal_col] > 3000]
            for _, row in spikes.iterrows():
                warnings.append(
                    f"⚠️ Calorie spike: {row[cal_col]:.0f} kcal on "
                    f"{row['date'].strftime('%a %b %d')} (>3,000 kcal threshold)."
                )

        # Single run >15 mi
        long_runs = runs[runs["distance_mi"] > 15]
        for _, row in long_runs.iterrows():
            warnings.append(
                f"⚠️ Long run: {row['distance_mi']:.1f} mi on "
                f"{row['date'].strftime('%a %b %d')} (>15 mi threshold)."
            )

    return warnings


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run_full(
    mf_filepath: str,
    garmin_filepath: str,
    week: Optional[str] = None,
    verbose: bool = False,
) -> RunResult:
    """Run the full weekly analysis and return a RunResult with report + data objects.

    Parameters
    ----------
    mf_filepath : str
        Path to MacroFactor XLSX export.
    garmin_filepath : str
        Path to Garmin Connect CSV export.
    week : str, optional
        Any ISO date (YYYY-MM-DD) within the target week. Defaults to current week.
    verbose : bool
        Print progress messages to stderr.
    """
    import sys

    def _log(msg: str):
        if verbose:
            print(f"[peakform] {msg}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Parse week bounds
    # ------------------------------------------------------------------
    week_start, week_end = _parse_week_arg(week)
    _log(
        f"Analysis window: {week_start.strftime('%Y-%m-%d')} – "
        f"{week_end.strftime('%Y-%m-%d')}"
    )

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    _log(f"Loading MacroFactor data from: {mf_filepath}")
    mf_data = macrofactor.load(mf_filepath)

    _log(f"Loading Garmin data from: {garmin_filepath}")
    garmin_data = garmin.load(garmin_filepath)

    # ------------------------------------------------------------------
    # Validate coverage
    # ------------------------------------------------------------------
    coverage_warnings = _validate_data_coverage(
        mf_data, garmin_data, week_start, week_end
    )
    if coverage_warnings:
        for w in coverage_warnings:
            _log(f"COVERAGE WARNING: {w}")

    # ------------------------------------------------------------------
    # Run analyzers
    # ------------------------------------------------------------------
    _log("Running analysis: running metrics...")
    running_analysis = running.analyze(garmin_data, week_start, week_end)

    _log("Running analysis: strength training...")
    strength_analysis = strength.analyze(mf_data, week_start, week_end)

    _log("Running analysis: nutrition...")
    nutrition_analysis = nutrition.analyze(
        mf_data,
        week_start,
        week_end,
        weekly_mileage=running_analysis.current.total_miles,
    )

    _log("Running analysis: body composition...")
    body_comp_analysis = body_comp.analyze(
        mf_data,
        week_start,
        week_end,
        avg_daily_deficit=nutrition_analysis.avg_daily_deficit,
    )

    _log("Detecting trend signals...")
    detected_signals = signals.detect(
        running_analysis,
        strength_analysis,
        nutrition_analysis,
        body_comp_analysis,
    )

    # ------------------------------------------------------------------
    # Build report
    # ------------------------------------------------------------------
    _log("Generating report...")
    report_md = formatter.build(
        running=running_analysis,
        strength=strength_analysis,
        nutrition=nutrition_analysis,
        body_comp=body_comp_analysis,
        signals=detected_signals,
    )

    # Prepend any coverage warnings
    if coverage_warnings:
        warn_block = "\n".join(f"> ⚠️ {w}" for w in coverage_warnings)
        report_md = f"---\n**Data Coverage Warnings:**\n{warn_block}\n\n---\n\n" + report_md

    _log("Done.")
    return RunResult(
        report_md=report_md,
        mf_data=mf_data,
        garmin_data=garmin_data,
        week_start=week_start,
        week_end=week_end,
    )


def run(
    mf_filepath: str,
    garmin_filepath: str,
    week: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """Backward-compatible wrapper — returns just the Markdown report string."""
    return run_full(mf_filepath, garmin_filepath, week=week, verbose=verbose).report_md
