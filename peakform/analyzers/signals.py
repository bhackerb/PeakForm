"""Trend signal detection.

Surfaces the key positive and warning signals defined in the agent spec.
Each signal has a severity ("✅" good, "⚠️" warning) and a message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from peakform.config import GROUND_CONTACT_CONCERN_MS
from peakform.analyzers.running import RunningAnalysis
from peakform.analyzers.strength import StrengthAnalysis
from peakform.analyzers.nutrition import NutritionAnalysis
from peakform.analyzers.body_comp import BodyCompAnalysis
from peakform.parsers.garmin import format_pace


@dataclass
class Signal:
    icon: str        # "✅" or "⚠️"
    category: str    # "Running", "Nutrition", "Body Comp", "Strength"
    message: str


def detect(
    running: RunningAnalysis,
    strength: StrengthAnalysis,
    nutrition: NutritionAnalysis,
    body_comp: BodyCompAnalysis,
) -> List[Signal]:
    """Detect and return all triggered trend signals."""
    signals: List[Signal] = []

    # ------------------------------------------------------------------
    # Running signals
    # ------------------------------------------------------------------

    # Aerobic adaptation
    if running.aerobic_adaptation_signal:
        cur_pace = format_pace(running.current.flat_avg_pace_dec)
        rolling_pace = format_pace(running.rolling_4wk.flat_avg_pace_dec)
        cur_hr = running.current.flat_avg_hr or 0
        signals.append(Signal(
            icon="✅",
            category="Running",
            message=(
                f"Pace improving ({rolling_pace} → {cur_pace}/mi) "
                f"with HR holding steady at {cur_hr:.0f} — aerobic adaptation confirmed."
            ),
        ))

    # Fatigue signal
    if running.fatigue_signal:
        cur_pace = format_pace(running.current.flat_avg_pace_dec)
        rolling_pace = format_pace(running.rolling_4wk.flat_avg_pace_dec)
        cur_hr = running.current.flat_avg_hr or 0
        roll_hr = running.rolling_4wk.flat_avg_hr or 0
        signals.append(Signal(
            icon="⚠️",
            category="Running",
            message=(
                f"Pace slower + HR higher than 4-week avg "
                f"({rolling_pace} → {cur_pace}/mi, HR {roll_hr:.0f} → {cur_hr:.0f}) — "
                "potential fatigue or overtraining."
            ),
        ))

    # Overreach flag
    if running.overreach_flag and running.mileage_change_pct is not None:
        pct = running.mileage_change_pct * 100
        signals.append(Signal(
            icon="⚠️",
            category="Running",
            message=(
                f"Weekly mileage is {pct:.0f}% above 4-week average "
                f"({running.rolling_4wk.total_miles:.1f} → "
                f"{running.current.total_miles:.1f} mi) — injury risk threshold exceeded."
            ),
        ))

    # Recovery debt
    if running.recovery_debt_flag:
        bbd = running.current.avg_body_battery_drain or 0
        signals.append(Signal(
            icon="⚠️",
            category="Running",
            message=(
                f"Average Body Battery drain per run is {bbd:.0f} "
                "(threshold: 15) — recovery debt accumulating."
            ),
        ))

    # Ground contact time trending up
    if (
        running.ground_contact_change_ms is not None
        and running.ground_contact_change_ms > GROUND_CONTACT_CONCERN_MS
    ):
        cur_gct = running.current.flat_avg_ground_contact_ms or 0
        roll_gct = running.rolling_4wk.flat_avg_ground_contact_ms or 0
        signals.append(Signal(
            icon="⚠️",
            category="Running",
            message=(
                f"Ground contact time rising ({roll_gct:.0f} → {cur_gct:.0f} ms, "
                f"+{running.ground_contact_change_ms:.0f} ms) — "
                "possible glute/hip fatigue or form breakdown."
            ),
        ))

    # Strength volume improvement
    if strength.pr_exercises:
        count = len(strength.pr_exercises)
        signals.append(Signal(
            icon="✅",
            category="Strength",
            message=f"Progressive overload confirmed: {count} exercise(s) hit new max weight this week.",
        ))

    # Missed muscle groups
    if strength.missed_muscle_groups:
        groups = ", ".join(strength.missed_muscle_groups)
        signals.append(Signal(
            icon="⚠️",
            category="Strength",
            message=f"Zero sets logged for priority muscle group(s): {groups}.",
        ))

    # Volume drops
    for mg, drop_pct in strength.volume_drop_flags.items():
        signals.append(Signal(
            icon="⚠️",
            category="Strength",
            message=f"{mg} volume dropped {drop_pct:.0f}% vs. 4-week average.",
        ))

    # ------------------------------------------------------------------
    # Nutrition signals
    # ------------------------------------------------------------------

    if nutrition.low_protein_flag:
        avg_p = nutrition.current.avg_protein_g or 0
        signals.append(Signal(
            icon="⚠️",
            category="Nutrition",
            message=(
                f"Avg daily protein {avg_p:.0f}g is below the 140g muscle-preservation "
                "threshold — risk of muscle loss during caloric deficit."
            ),
        ))

    if nutrition.low_carb_underfuel_flag:
        avg_c = nutrition.current.avg_carbs_g or 0
        miles = nutrition.weekly_mileage
        signals.append(Signal(
            icon="⚠️",
            category="Nutrition",
            message=(
                f"Avg carbs {avg_c:.0f}g/day while running {miles:.1f} mi/week — "
                "underfueling risk for performance and recovery."
            ),
        ))

    if nutrition.high_calorie_variance_flag:
        stdev = nutrition.current.calorie_stdev or 0
        signals.append(Signal(
            icon="⚠️",
            category="Nutrition",
            message=(
                f"Calorie intake std deviation is {stdev:.0f} kcal "
                "(threshold: 300) — inconsistent adherence may slow fat loss."
            ),
        ))

    # Micronutrient flags
    for nutrient, pct in nutrition.micronutrient_flags.items():
        display = nutrient.replace("_", " ").title()
        signals.append(Signal(
            icon="⚠️",
            category="Nutrition",
            message=f"{display} averaging {pct:.0f}% of daily target — consider food sources or supplementation.",
        ))

    # ------------------------------------------------------------------
    # Body composition signals
    # ------------------------------------------------------------------

    if body_comp.weight_rising_despite_deficit:
        signals.append(Signal(
            icon="⚠️",
            category="Body Comp",
            message=(
                "Trend weight rising despite a logged caloric deficit — "
                "MacroFactor is still recalibrating from the tracking gap. "
                "Maintain consistent logging; the algorithm needs 2–3 more weeks of data."
            ),
        ))

    if body_comp.algorithm_recalibrating:
        signals.append(Signal(
            icon="⚠️",
            category="Body Comp",
            message=(
                "Still within the first 3 weeks post-tracking restart. "
                "MacroFactor expenditure estimate (currently ~2,009 kcal) "
                "is likely underestimating true TDEE given run volume. "
                "Consistency now = faster recalibration."
            ),
        ))

    return signals
