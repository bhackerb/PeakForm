"""Nutrition analyzer.

Computes weekly macro averages, adherence rates, calorie variance,
and micronutrient flags vs. MacroFactor targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from peakform.config import (
    CALORIE_ADHERENCE_WINDOW_KCAL,
    CALORIE_VARIANCE_CONCERN_STDEV,
    CARBS_UNDERFUEL_MIN_G,
    FIBER_TARGET_G,
    PROTEIN_PRESERVATION_MIN_G,
)


# ---------------------------------------------------------------------------
# Key micronutrients to monitor for endurance athletes
# ---------------------------------------------------------------------------

MICRONUTRIENT_TARGETS = {
    "fiber": FIBER_TARGET_G,          # grams
    "iron": 18.0,                      # mg (daily reference for active males)
    "vitamin_d": 15.0,                 # mcg
    "potassium": 3400.0,               # mg
    "magnesium": 420.0,                # mg
    "sodium": 2300.0,                  # mg (min for endurance — higher is ok)
    "calcium": 1000.0,                 # mg
    "vitamin_b12": 2.4,               # mcg
    "zinc": 11.0,                      # mg
}

# Electrolytes especially important for high run volume
ELECTROLYTE_KEYS = {"potassium", "magnesium", "sodium", "calcium"}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class NutritionWeekStats:
    """Nutrition statistics for a single week."""

    week_start: pd.Timestamp
    week_end: pd.Timestamp

    logged_days: int = 0

    # Daily averages
    avg_calories: Optional[float] = None
    avg_protein_g: Optional[float] = None
    avg_carbs_g: Optional[float] = None
    avg_fat_g: Optional[float] = None
    avg_fiber_g: Optional[float] = None

    # Calorie statistics
    calorie_stdev: Optional[float] = None

    # Avg expenditure (from MacroFactor TDEE estimate)
    avg_expenditure: Optional[float] = None

    # Active MacroFactor targets for this week
    target_calories: Optional[float] = None
    target_protein_g: Optional[float] = None
    target_carbs_g: Optional[float] = None
    target_fat_g: Optional[float] = None

    # Adherence counts
    protein_hit_days: int = 0          # days >= target protein (or 153g fallback)
    calorie_target_days: int = 0       # days within ±100 kcal of target

    # Micronutrients: {nutrient_key: avg_daily_value}
    avg_micronutrients: Dict[str, float] = field(default_factory=dict)


@dataclass
class NutritionAnalysis:
    """Output of the nutrition analyzer."""

    current: NutritionWeekStats

    # Derived metrics
    avg_daily_deficit: Optional[float] = None   # positive = deficit
    deficit_vs_target: Optional[float] = None   # actual - target deficit (negative = larger)

    # % of macro targets achieved
    protein_pct_target: Optional[float] = None
    carbs_pct_target: Optional[float] = None
    fat_pct_target: Optional[float] = None
    calories_pct_target: Optional[float] = None

    # Adherence rates (0.0–1.0)
    protein_hit_rate: Optional[float] = None
    calorie_target_rate: Optional[float] = None

    # Flags
    low_protein_flag: bool = False
    low_carb_underfuel_flag: bool = False      # low carbs + high mileage
    high_calorie_variance_flag: bool = False
    incomplete_week_flag: bool = False         # <5 logged days

    # Micronutrient flags: {nutrient: pct_of_target}
    micronutrient_flags: Dict[str, float] = field(default_factory=dict)

    # Weekly mileage (injected by agent — needed for underfuel check)
    weekly_mileage: float = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_col(df: pd.DataFrame, *candidates) -> Optional[str]:
    """Find the first column that contains any of the candidate strings."""
    for c in candidates:
        for col in df.columns:
            if c.lower() in col.lower():
                return col
    return None


def _week_slice(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return df[(df["date"] >= start) & (df["date"] <= end)].copy()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(
    mf_data,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
    weekly_mileage: float = 0.0,
) -> NutritionAnalysis:
    """Run the full nutrition analysis for the given week.

    Parameters
    ----------
    mf_data : MacroFactorData
        Parsed MacroFactor data.
    week_start, week_end : pd.Timestamp
        Mon–Sun window.
    weekly_mileage : float
        Total running miles for the week (for underfuel check).
    """
    # ------------------------------------------------------------------
    # Get live targets from MacroFactor
    # ------------------------------------------------------------------
    targets = mf_data.get_current_targets()

    # ------------------------------------------------------------------
    # Calories & Macros sheet
    # ------------------------------------------------------------------
    cm_df = mf_data.calories_macros
    cm_week = _week_slice(cm_df, week_start, week_end) if not cm_df.empty else pd.DataFrame()

    stats = NutritionWeekStats(week_start=week_start, week_end=week_end)
    stats.target_calories = targets["calories"]
    stats.target_protein_g = targets["protein_g"]
    stats.target_carbs_g = targets["carbs_g"]
    stats.target_fat_g = targets["fat_g"]

    if not cm_week.empty:
        stats.logged_days = len(cm_week)

        cal_col = _find_col(cm_week, "calorie", "kcal", "energy")
        prot_col = _find_col(cm_week, "protein")
        carb_col = _find_col(cm_week, "carb")
        fat_col = _find_col(cm_week, "fat")

        if cal_col:
            cal_vals = cm_week[cal_col].dropna()
            if len(cal_vals):
                stats.avg_calories = cal_vals.mean()
                stats.calorie_stdev = cal_vals.std()
        if prot_col:
            prot_vals = cm_week[prot_col].dropna()
            if len(prot_vals):
                stats.avg_protein_g = prot_vals.mean()
                # Protein hit days
                protein_target = stats.target_protein_g or PROTEIN_PRESERVATION_MIN_G
                stats.protein_hit_days = int((prot_vals >= protein_target).sum())
        if carb_col:
            carb_vals = cm_week[carb_col].dropna()
            if len(carb_vals):
                stats.avg_carbs_g = carb_vals.mean()
        if fat_col:
            fat_vals = cm_week[fat_col].dropna()
            if len(fat_vals):
                stats.avg_fat_g = fat_vals.mean()

        # Calorie adherence days
        if cal_col and stats.target_calories:
            cal_vals = cm_week[cal_col].dropna()
            stats.calorie_target_days = int(
                (abs(cal_vals - stats.target_calories) <= CALORIE_ADHERENCE_WINDOW_KCAL).sum()
            )

    # ------------------------------------------------------------------
    # Expenditure sheet
    # ------------------------------------------------------------------
    exp_df = mf_data.expenditure
    if not exp_df.empty:
        exp_week = _week_slice(exp_df, week_start, week_end)
        exp_col = _find_col(exp_week, "expenditure", "tdee", "total")
        if exp_col and not exp_week.empty:
            exp_vals = exp_week[exp_col].dropna()
            if len(exp_vals):
                stats.avg_expenditure = exp_vals.mean()

    # ------------------------------------------------------------------
    # Micronutrients sheet
    # ------------------------------------------------------------------
    micro_df = mf_data.micronutrients
    if not micro_df.empty:
        micro_week = _week_slice(micro_df, week_start, week_end)
        if not micro_week.empty:
            # Fiber — check for column name variations
            for fiber_key in ("fiber", "dietary_fiber", "fibre"):
                fiber_col = _find_col(micro_week, fiber_key)
                if fiber_col:
                    vals = micro_week[fiber_col].dropna()
                    if len(vals):
                        stats.avg_fiber_g = vals.mean()
                        stats.avg_micronutrients["fiber"] = stats.avg_fiber_g
                    break

            # Other tracked micronutrients
            for key in MICRONUTRIENT_TARGETS:
                if key == "fiber":
                    continue
                col = _find_col(micro_week, key)
                if col:
                    vals = micro_week[col].dropna()
                    if len(vals):
                        stats.avg_micronutrients[key] = vals.mean()

    # ------------------------------------------------------------------
    # Build analysis
    # ------------------------------------------------------------------
    analysis = NutritionAnalysis(current=stats, weekly_mileage=weekly_mileage)

    # Deficit
    if stats.avg_calories and stats.avg_expenditure:
        analysis.avg_daily_deficit = stats.avg_expenditure - stats.avg_calories
        # Target deficit = expenditure - calorie target
        if stats.target_calories and stats.avg_expenditure:
            target_deficit = stats.avg_expenditure - stats.target_calories
            if target_deficit != 0:
                analysis.deficit_vs_target = analysis.avg_daily_deficit - target_deficit

    # % of targets
    if stats.avg_calories and stats.target_calories:
        analysis.calories_pct_target = stats.avg_calories / stats.target_calories * 100
    if stats.avg_protein_g and stats.target_protein_g:
        analysis.protein_pct_target = stats.avg_protein_g / stats.target_protein_g * 100
    if stats.avg_carbs_g and stats.target_carbs_g:
        analysis.carbs_pct_target = stats.avg_carbs_g / stats.target_carbs_g * 100
    if stats.avg_fat_g and stats.target_fat_g:
        analysis.fat_pct_target = stats.avg_fat_g / stats.target_fat_g * 100

    # Adherence rates
    if stats.logged_days > 0:
        analysis.protein_hit_rate = stats.protein_hit_days / stats.logged_days
        analysis.calorie_target_rate = stats.calorie_target_days / stats.logged_days

    # Flags
    if stats.avg_protein_g and stats.avg_protein_g < PROTEIN_PRESERVATION_MIN_G:
        analysis.low_protein_flag = True

    if (
        stats.avg_carbs_g is not None
        and stats.avg_carbs_g < CARBS_UNDERFUEL_MIN_G
        and weekly_mileage > 30
    ):
        analysis.low_carb_underfuel_flag = True

    if stats.calorie_stdev and stats.calorie_stdev > CALORIE_VARIANCE_CONCERN_STDEV:
        analysis.high_calorie_variance_flag = True

    if stats.logged_days < 5:
        analysis.incomplete_week_flag = True

    # Micronutrient flags (below 80% of target)
    for nutrient, target in MICRONUTRIENT_TARGETS.items():
        if nutrient in stats.avg_micronutrients:
            pct = stats.avg_micronutrients[nutrient] / target * 100
            if pct < 80:
                analysis.micronutrient_flags[nutrient] = round(pct, 1)

    return analysis
