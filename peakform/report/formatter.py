"""Weekly report formatter.

Produces a structured Markdown report from the analysis results.
Renders to the terminal using `rich` if available, otherwise plain text.
"""

from __future__ import annotations

import math
from typing import List, Optional

from peakform.analyzers.running import RunningAnalysis
from peakform.analyzers.strength import StrengthAnalysis
from peakform.analyzers.nutrition import NutritionAnalysis
from peakform.analyzers.body_comp import BodyCompAnalysis
from peakform.analyzers.signals import Signal
from peakform.config import MEAL_ROTATION, MealEntry
from peakform.parsers.garmin import format_pace


# ---------------------------------------------------------------------------
# Directional arrow helpers
# ---------------------------------------------------------------------------

def _arrow(current, baseline, lower_is_better: bool = False) -> str:
    """Return ↑ ↓ → based on direction of change."""
    if current is None or baseline is None:
        return "→"
    diff = current - baseline
    if abs(diff) < 0.5:
        return "→"
    improving = diff < 0 if lower_is_better else diff > 0
    return "↑" if (diff > 0 and not lower_is_better) or (diff < 0 and lower_is_better) else "↓"


def _pct_str(val: Optional[float], target: Optional[float]) -> str:
    if val is None or target is None or target == 0:
        return "N/A"
    return f"{val / target * 100:.0f}%"


def _na(val, fmt: str = ".1f") -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/A"
    return format(val, fmt)


def _na0(val) -> str:
    return _na(val, ".0f")


# ---------------------------------------------------------------------------
# Meal prep recommendation logic
# ---------------------------------------------------------------------------

def _meal_prep_plan(
    nutrition: NutritionAnalysis,
    running: RunningAnalysis,
) -> str:
    """Generate Sunday meal prep plan based on current macro targets."""
    targets = nutrition.current
    cal_target = targets.target_calories or 1377
    prot_target = targets.target_protein_g or 153
    carb_target = targets.target_carbs_g or 87

    lines: List[str] = []
    lines.append("**Sunday Meal Prep Plan**\n")
    lines.append(
        f"MacroFactor targets: **{cal_target:.0f} kcal | "
        f"{prot_target:.0f}g protein | {carb_target:.0f}g carbs**\n"
    )

    # Recommend primary batch-cook recipe
    # If carbs target shifted low → Tofu Broccoli Parm is better macro fit
    # If high mileage week → Jambalaya for extra carbs
    high_mileage = running.current.total_miles > 35
    if high_mileage or (carb_target and carb_target > 90):
        primary = next(m for m in MEAL_ROTATION if "Jambalaya" in m.name)
        secondary = next(m for m in MEAL_ROTATION if "Tofu" in m.name)
        note = "Higher-carb recipe chosen given elevated run volume."
    else:
        primary = next(m for m in MEAL_ROTATION if "Tofu" in m.name)
        secondary = next(m for m in MEAL_ROTATION if "Jambalaya" in m.name)
        note = "Balanced recipe chosen to hit protein + moderate carb targets."

    lines.append(f"*{note}*\n")
    lines.append(f"**Primary batch (7 servings):** {primary.name}")
    lines.append(
        f"Per serving: {primary.kcal:.0f} kcal | "
        f"{primary.protein_g:.0f}g P | {primary.carbs_g:.0f}g C | {primary.fat_g:.0f}g F"
    )
    lines.append("Use: Mon–Sun dinner\n")

    lines.append("**Breakfast/Snack:** Yogurt PB Protein Bowl (daily)")
    yogurt = next(m for m in MEAL_ROTATION if "Yogurt" in m.name)
    lines.append(
        f"Per serving: {yogurt.kcal:.0f} kcal | "
        f"{yogurt.protein_g:.0f}g P | {yogurt.carbs_g:.0f}g C | {yogurt.fat_g:.0f}g F\n"
    )

    lines.append("**Pre-run:** Rice cake + PB + honey (before each morning run)")
    prerun = next(m for m in MEAL_ROTATION if "rice cake" in m.name.lower())
    lines.append(
        f"Per serving: {prerun.kcal:.0f} kcal | "
        f"{prerun.protein_g:.0f}g P | {prerun.carbs_g:.0f}g C | {prerun.fat_g:.0f}g F\n"
    )

    # Daily macro estimate (primary dinner + yogurt bowl + pre-run)
    day_cal = primary.kcal + yogurt.kcal + prerun.kcal
    day_prot = primary.protein_g + yogurt.protein_g + prerun.protein_g
    day_carb = primary.carbs_g + yogurt.carbs_g + prerun.carbs_g
    day_fat = primary.fat_g + yogurt.fat_g + prerun.fat_g

    lines.append("**Estimated daily template (dinner + breakfast bowl + pre-run):**")
    lines.append(
        f"{day_cal:.0f} kcal | {day_prot:.0f}g P | {day_carb:.0f}g C | {day_fat:.0f}g F"
    )
    remaining_cal = cal_target - day_cal
    remaining_prot = prot_target - day_prot
    lines.append(
        f"Remaining after template: ~{remaining_cal:.0f} kcal / "
        f"~{remaining_prot:.0f}g protein to fill with additional snacks/meals.\n"
    )

    # Grocery list
    lines.append("**Grocery list**\n")
    lines.append(f"*{primary.name} — 7-serving batch (Mon–Sun dinner):*")
    if "Jambalaya" in primary.name:
        lines.append("- Canned tomatoes (28 oz) × 2")
        lines.append("- Vegetable broth (32 oz) × 1")
        lines.append("- Brown rice, 2 cups dry")
        lines.append("- Black beans, canned (15 oz) × 2")
        lines.append("- Red/green bell peppers × 3")
        lines.append("- Celery × 4 stalks")
        lines.append("- Yellow onion × 1")
        lines.append("- Garlic, 6 cloves")
        lines.append("- Cajun seasoning, smoked paprika, thyme")
        lines.append("- Andouille-style veggie sausage (optional)\n")
    else:
        lines.append("- Extra-firm tofu (14 oz) × 2 blocks")
        lines.append("- Broccoli florets, 2 lbs")
        lines.append("- Marinara sauce (24 oz) × 1")
        lines.append("- Whole-wheat breadcrumbs, 1/2 cup")
        lines.append("- Parmesan or nutritional yeast, 1/2 cup")
        lines.append("- Garlic, 4 cloves")
        lines.append("- Olive oil, Italian seasoning\n")

    lines.append("*Breakfast bowls (7 days):*")
    lines.append("- Greek yogurt (plain, 2% or non-fat), 5–6 cups")
    lines.append("- Peanut butter, 7 tbsp")
    lines.append("- Protein powder (optional top-up)")
    lines.append("- Berries / banana (optional)\n")

    lines.append("*Pre-run (7 mornings):*")
    lines.append("- Rice cakes × 1 pack")
    lines.append("- Peanut butter (shared with bowl supply)")
    lines.append("- Honey × 1 small jar")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main report builder
# ---------------------------------------------------------------------------

def build(
    running: RunningAnalysis,
    strength: StrengthAnalysis,
    nutrition: NutritionAnalysis,
    body_comp: BodyCompAnalysis,
    signals: List[Signal],
) -> str:
    """Assemble the full weekly Markdown report."""
    week_start = running.current.week_start
    week_end = running.current.week_end
    week_label = (
        f"{week_start.strftime('%b %d')}–{week_end.strftime('%b %d, %Y')}"
    )

    cur_r = running.current
    roll_r = running.rolling_4wk
    cur_n = nutrition.current
    cur_bc = body_comp

    lines: List[str] = []

    # ==================================================================
    # HEADER
    # ==================================================================
    trend_start = _na(cur_bc.trend_weight_start)
    trend_end = _na(cur_bc.trend_weight_end)
    trend_net = (
        f"+{cur_bc.trend_net_change_lbs:.1f}"
        if cur_bc.trend_net_change_lbs and cur_bc.trend_net_change_lbs > 0
        else _na(cur_bc.trend_net_change_lbs)
    )
    avg_cal = _na0(cur_n.avg_calories)
    avg_prot = _na0(cur_n.avg_protein_g)

    lines.append(
        f"# Weekly Report — {week_label}\n"
        f"**Trend Weight:** {trend_start} → {trend_end} lbs ({trend_net} lbs) | "
        f"**Running:** {cur_r.total_miles:.1f} mi | "
        f"**Avg Pace:** {cur_r.flat_avg_pace_mmss}/mi | "
        f"**Calories:** {avg_cal} avg | "
        f"**Protein:** {avg_prot}g avg"
    )
    lines.append("")

    # ==================================================================
    # RUNNING
    # ==================================================================
    lines.append("---\n## 🏃 Running This Week\n")

    m_arrow = _arrow(cur_r.total_miles, roll_r.total_miles)
    p_arrow = _arrow(
        running.current.flat_avg_pace_dec,
        running.rolling_4wk.flat_avg_pace_dec,
        lower_is_better=True,
    )
    hr_arrow = _arrow(cur_r.flat_avg_hr, roll_r.flat_avg_hr, lower_is_better=True)
    cad_arrow = _arrow(cur_r.flat_avg_cadence, roll_r.flat_avg_cadence)
    elev_arrow = _arrow(cur_r.total_elevation_gain_ft, roll_r.total_elevation_gain_ft)

    roll_pace_str = format_pace(roll_r.flat_avg_pace_dec) if roll_r.flat_avg_pace_dec else "N/A"
    roll_hr_str = _na0(roll_r.flat_avg_hr)
    roll_cad_str = _na0(roll_r.flat_avg_cadence)
    roll_miles_str = f"{roll_r.total_miles:.1f}" if roll_r.total_miles else "N/A"

    lines.append(
        "| Metric | This Week | 4-Wk Avg | Trend |\n"
        "|---|---|---|---|\n"
        f"| Total Mileage | {cur_r.total_miles:.1f} mi | {roll_miles_str} mi | {m_arrow} |\n"
        f"| Elevation Gain | {cur_r.total_elevation_gain_ft:.0f} ft | "
        f"{roll_r.total_elevation_gain_ft:.0f} ft | {elev_arrow} |\n"
        f"| Avg Pace (flat) | {cur_r.flat_avg_pace_mmss}/mi | {roll_pace_str}/mi | {p_arrow} |\n"
        f"| Avg HR (flat) | {cur_r.flat_avg_hr_display} bpm | {roll_hr_str} bpm | {hr_arrow} |\n"
        f"| Avg Cadence | {cur_r.flat_avg_cadence_display} spm | {roll_cad_str} spm | {cad_arrow} |\n"
        f"| Aerobic TE | {_na(cur_r.flat_avg_aerobic_te)} | {_na(roll_r.flat_avg_aerobic_te)} | → |\n"
        f"| Longest Run | {cur_r.longest_run_miles:.1f} mi | {roll_r.longest_run_miles:.1f} mi | → |\n"
        f"| Run Count | {cur_r.run_count} | {roll_r.run_count} | → |"
    )

    if cur_r.trail_run_count > 0:
        lines.append(
            f"\n**Trail / Mountain Runs:** {cur_r.trail_run_count} run(s) | "
            f"{cur_r.trail_total_miles:.1f} mi | "
            f"{cur_r.trail_total_elevation_ft:.0f} ft elevation gain"
        )

    if cur_r.flat_avg_hr and cur_r.flat_avg_pace_dec:
        eff = cur_r.flat_avg_hr / cur_r.flat_avg_pace_dec
        lines.append(f"\n**HR:Pace Efficiency:** {eff:.1f} bpm per min/mile")

    if cur_r.avg_body_battery_drain is not None:
        lines.append(
            f"\n**Avg Body Battery Drain:** {cur_r.avg_body_battery_drain:.0f} "
            f"(max: {cur_r.max_body_battery_drain:.0f})"
        )

    lines.append("")

    # ==================================================================
    # STRENGTH
    # ==================================================================
    lines.append("---\n## 💪 Strength Training\n")

    cur_s = strength.current
    lines.append(f"**Workout days logged:** {cur_s.workout_days}")

    if cur_s.sets_by_muscle:
        lines.append("\n**Sets by Muscle Group:**")
        lines.append("| Muscle Group | Sets This Week |")
        lines.append("|---|---|")
        for mg, sets in sorted(cur_s.sets_by_muscle.items(), key=lambda x: -x[1]):
            lines.append(f"| {mg} | {sets:.0f} |")
    else:
        lines.append("\n*No muscle group data found for this week.*")

    if strength.pr_exercises:
        lines.append(f"\n**PRs / New Maxes ({len(strength.pr_exercises)}):**")
        for pr in strength.pr_exercises:
            lines.append(f"  - {pr}")

    if strength.regression_exercises:
        lines.append(f"\n**Regressions ({len(strength.regression_exercises)}):**")
        for reg in strength.regression_exercises:
            lines.append(f"  - {reg}")

    if strength.missed_muscle_groups:
        missed = ", ".join(strength.missed_muscle_groups)
        lines.append(f"\n⚠️ **Missed priority muscle groups:** {missed}")

    if strength.volume_drop_flags:
        lines.append("\n**Volume drops vs. 4-wk avg:**")
        for mg, pct in strength.volume_drop_flags.items():
            lines.append(f"  - {mg}: −{pct:.0f}%")

    lines.append("")

    # ==================================================================
    # NUTRITION
    # ==================================================================
    lines.append("---\n## 🥗 Nutrition\n")

    cal_tgt = cur_n.target_calories
    prot_tgt = cur_n.target_protein_g
    carb_tgt = cur_n.target_carbs_g
    fat_tgt = cur_n.target_fat_g

    lines.append(
        f"**MacroFactor Target:** {_na0(cal_tgt)} kcal | "
        f"{_na0(prot_tgt)}g protein | {_na0(carb_tgt)}g carbs | {_na0(fat_tgt)}g fat\n"
    )

    if nutrition.incomplete_week_flag:
        lines.append(
            f"⚠️ **Incomplete week:** only {cur_n.logged_days} days logged "
            "(need ≥5 for full analysis). Metrics below are partial.\n"
        )

    lines.append(
        "| Metric | Avg/Day | Target | % of Target |\n"
        "|---|---|---|---|\n"
        f"| Calories | {_na0(cur_n.avg_calories)} kcal | {_na0(cal_tgt)} kcal | "
        f"{_pct_str(cur_n.avg_calories, cal_tgt)} |\n"
        f"| Protein | {_na0(cur_n.avg_protein_g)}g | {_na0(prot_tgt)}g | "
        f"{_pct_str(cur_n.avg_protein_g, prot_tgt)} |\n"
        f"| Carbs | {_na0(cur_n.avg_carbs_g)}g | {_na0(carb_tgt)}g | "
        f"{_pct_str(cur_n.avg_carbs_g, carb_tgt)} |\n"
        f"| Fat | {_na0(cur_n.avg_fat_g)}g | {_na0(fat_tgt)}g | "
        f"{_pct_str(cur_n.avg_fat_g, fat_tgt)} |\n"
        f"| Fiber | {_na(cur_n.avg_fiber_g)}g | 25g | "
        f"{_pct_str(cur_n.avg_fiber_g, 25)} |"
    )

    if nutrition.protein_hit_rate is not None:
        lines.append(
            f"\n**Protein hit rate:** {cur_n.protein_hit_days}/{cur_n.logged_days} days "
            f"≥ {_na0(prot_tgt)}g ({nutrition.protein_hit_rate * 100:.0f}%)"
        )
    if nutrition.calorie_target_rate is not None:
        lines.append(
            f"**Calorie target days:** {cur_n.calorie_target_days}/{cur_n.logged_days} "
            f"within ±100 kcal ({nutrition.calorie_target_rate * 100:.0f}%)"
        )
    if cur_n.calorie_stdev is not None:
        lines.append(f"**Calorie variance (std dev):** {cur_n.calorie_stdev:.0f} kcal/day")

    # Deficit math
    lines.append("\n**Deficit:**")
    if cur_n.avg_calories and cur_n.avg_expenditure:
        deficit = cur_n.avg_expenditure - cur_n.avg_calories
        lines.append(
            f"  Avg intake {_na0(cur_n.avg_calories)} kcal vs. "
            f"expenditure {_na0(cur_n.avg_expenditure)} kcal "
            f"= **{deficit:.0f} kcal/day deficit**"
        )
        if nutrition.deficit_vs_target is not None:
            direction = "larger" if nutrition.deficit_vs_target > 0 else "smaller"
            lines.append(
                f"  ({abs(nutrition.deficit_vs_target):.0f} kcal {direction} than target deficit)"
            )
    else:
        lines.append("  Insufficient data for deficit calculation.")

    # Micronutrient flags
    if nutrition.micronutrient_flags:
        lines.append("\n**⚠️ Micronutrient flags (below 80% of daily target):**")
        for nutrient, pct in nutrition.micronutrient_flags.items():
            display = nutrient.replace("_", " ").title()
            lines.append(f"  - {display}: {pct:.0f}% of target")
    elif cur_n.avg_micronutrients:
        lines.append("\n*All tracked micronutrients within range.*")

    lines.append("")

    # ==================================================================
    # BODY COMPOSITION
    # ==================================================================
    lines.append("---\n## ⚖️ Body Composition\n")

    w_start = _na(cur_bc.weight_start_lbs)
    w_end = _na(cur_bc.weight_end_lbs)
    w_change = cur_bc.weight_net_change_lbs
    w_change_str = (
        f"+{w_change:.1f}" if w_change and w_change > 0 else _na(w_change)
    )
    trend_dir_icon = {"down": "📉", "up": "📈", "flat": "→"}.get(
        cur_bc.trend_direction, "→"
    )

    lines.append(f"**Scale weight:** {w_start} → {w_end} lbs ({w_change_str} lbs)")
    lines.append(
        f"**Trend weight:** {_na(cur_bc.trend_weight_start)} → "
        f"{_na(cur_bc.trend_weight_end)} lbs "
        f"({trend_dir_icon} {cur_bc.trend_direction})"
    )
    if cur_bc.body_fat_pct_latest:
        lines.append(f"**Body fat %:** {cur_bc.body_fat_pct_latest:.1f}% (latest reading)")

    # Goal projection
    if cur_bc.pounds_to_goal:
        lines.append(f"\n**To goal (160 lbs):** {cur_bc.pounds_to_goal:.1f} lbs remaining")
    if cur_bc.weekly_rate_lbs and cur_bc.weekly_rate_lbs > 0:
        lines.append(
            f"**Current rate:** {cur_bc.weekly_rate_lbs:.2f} lbs/week "
            f"({'loss' if cur_bc.weekly_rate_lbs > 0 else 'gain'})"
        )
    if cur_bc.weeks_to_goal:
        weeks = cur_bc.weeks_to_goal
        if cur_bc.projected_goal_date:
            lines.append(
                f"**Projected 160 lbs:** {cur_bc.projected_goal_date.strftime('%b %d, %Y')} "
                f"({weeks:.0f} weeks at current rate)"
            )

    if cur_bc.weight_rising_despite_deficit or cur_bc.algorithm_recalibrating:
        lines.append(
            "\n> **Note:** MacroFactor is still recalibrating after the Nov 2025–Feb 2026 "
            "tracking gap. A rising trend weight in the first 1–3 weeks post-restart is "
            "normal — the algorithm needs consistent data to re-anchor the TDEE estimate. "
            "True expenditure is likely higher than the current 2,009 kcal estimate given "
            "~35+ mi/week run volume. Maintain tight logging and let the algorithm adapt."
        )

    lines.append("")

    # ==================================================================
    # KEY OBSERVATIONS
    # ==================================================================
    lines.append("---\n## 📊 Key Observations\n")

    observations = _build_observations(running, strength, nutrition, body_comp, signals)
    for obs in observations:
        lines.append(f"- {obs}")

    lines.append("")

    # ==================================================================
    # SIGNALS (full list)
    # ==================================================================
    if signals:
        lines.append("---\n## 🚦 Trend Signals\n")
        for sig in signals:
            lines.append(f"{sig.icon} **[{sig.category}]** {sig.message}\n")
        lines.append("")

    # ==================================================================
    # RECOMMENDATIONS
    # ==================================================================
    lines.append("---\n## 🎯 Recommendations\n")
    lines.append("### Training\n")
    training_recs = _training_recommendations(running, strength)
    for rec in training_recs:
        lines.append(f"- {rec}")

    lines.append("\n### Nutrition\n")
    nutrition_recs = _nutrition_recommendations(nutrition, running)
    for rec in nutrition_recs:
        lines.append(f"- {rec}")

    lines.append("\n### Meal Prep (Sunday Plan)\n")
    lines.append(_meal_prep_plan(nutrition, running))

    lines.append("")

    # ==================================================================
    # FOCUS FOR NEXT WEEK
    # ==================================================================
    lines.append("---\n## 🏁 Focus for Next Week\n")
    train_focus, nutrition_focus = _next_week_focus(running, nutrition, body_comp)
    lines.append(f"- **Training priority:** {train_focus}")
    lines.append(f"- **Nutrition priority:** {nutrition_focus}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Observations builder
# ---------------------------------------------------------------------------

def _build_observations(
    running: RunningAnalysis,
    strength: StrengthAnalysis,
    nutrition: NutritionAnalysis,
    body_comp: BodyCompAnalysis,
    signals: List[Signal],
) -> List[str]:
    obs: List[str] = []

    # Running
    if running.aerobic_adaptation_signal:
        cur_p = format_pace(running.current.flat_avg_pace_dec)
        roll_p = format_pace(running.rolling_4wk.flat_avg_pace_dec)
        hr = running.current.flat_avg_hr or 0
        pace_diff_sec = abs(
            (running.rolling_4wk.flat_avg_pace_dec or 0)
            - (running.current.flat_avg_pace_dec or 0)
        ) * 60
        obs.append(
            f"Avg flat-run pace improved {pace_diff_sec:.0f} sec/mile this week "
            f"({roll_p} → {cur_p}) with HR holding at {hr:.0f} bpm — "
            "clear aerobic fitness signal."
        )

    if running.overreach_flag and running.mileage_change_pct is not None:
        obs.append(
            f"Weekly mileage ({running.current.total_miles:.1f} mi) is "
            f"{running.mileage_change_pct * 100:.0f}% above 4-week average "
            f"({running.rolling_4wk.total_miles:.1f} mi) — monitor for overreach."
        )

    # Strength
    if strength.pr_exercises:
        obs.append(
            f"Hit new maxes on {len(strength.pr_exercises)} exercise(s) this week — "
            "progressive overload on track."
        )

    if strength.current.workout_days == 0:
        obs.append("No strength workouts logged this week — check data sync or schedule.")

    # Nutrition
    if nutrition.current.avg_protein_g:
        prot_tgt = nutrition.current.target_protein_g or 153
        if nutrition.current.avg_protein_g >= prot_tgt:
            obs.append(
                f"Protein target hit: averaged {nutrition.current.avg_protein_g:.0f}g/day "
                f"vs. {prot_tgt:.0f}g target."
            )
        else:
            obs.append(
                f"Protein averaged {nutrition.current.avg_protein_g:.0f}g/day "
                f"(target {prot_tgt:.0f}g) — {prot_tgt - nutrition.current.avg_protein_g:.0f}g gap."
            )

    # Body comp
    if body_comp.trend_net_change_lbs and body_comp.trend_net_change_lbs < -0.2:
        obs.append(
            f"Trend weight declined {abs(body_comp.trend_net_change_lbs):.2f} lbs this week — "
            "fat loss trajectory on track."
        )
    elif body_comp.weight_rising_despite_deficit:
        obs.append(
            "Trend weight rising despite a logged deficit — algorithm recalibration in progress. "
            "Not a cause for concern at this stage."
        )

    # Cap at 5 observations
    return obs[:5]


# ---------------------------------------------------------------------------
# Training recommendations
# ---------------------------------------------------------------------------

def _training_recommendations(
    running: RunningAnalysis,
    strength: StrengthAnalysis,
) -> List[str]:
    recs: List[str] = []

    # Mileage management
    if running.overreach_flag and running.mileage_change_pct is not None:
        target_mi = running.rolling_4wk.total_miles * 1.10
        recs.append(
            f"Mileage is {running.mileage_change_pct * 100:.0f}% above 4-week avg — "
            f"cap next week at ≤{target_mi:.0f} mi to stay within the 10% rule."
        )
    else:
        recs.append(
            f"Mileage ({running.current.total_miles:.1f} mi) is within safe progression range. "
            "Continue current volume or add ≤10% if feeling strong."
        )

    # Recovery
    if running.recovery_debt_flag:
        bbd = running.current.avg_body_battery_drain or 0
        recs.append(
            f"Body Battery drain is averaging {bbd:.0f}/run — consider adding a full rest day "
            "or easy 20-min recovery jog mid-week."
        )

    # Trail prep for 14ers / Europe
    if running.current.trail_run_count == 0:
        recs.append(
            "No trail/mountain runs logged this week — schedule at least one "
            "elevation-focused run (500+ ft gain) per week to build 14er readiness."
        )
    else:
        recs.append(
            f"Trail work on track ({running.current.trail_run_count} run(s), "
            f"{running.current.trail_total_elevation_ft:.0f} ft gain). "
            "Progressively increase vertical gain each week toward June 14er season."
        )

    # Strength — Feb 2026 program adherence
    if strength.current.workout_days < 2:
        recs.append(
            f"Only {strength.current.workout_days} strength session(s) this week. "
            "Feb 2026 Plan requires 2 sessions (Lower Body + Core, Upper Body + Core). "
            "Prioritize Lower Body day to protect running biomechanics."
        )
    else:
        recs.append(
            f"Strength sessions: {strength.current.workout_days} completed. "
            "Continue Feb 2026 Plan progression — 7 cycles scheduled."
        )

    # Glute/hip volume flag
    glute_flag = False
    for mg, drop in strength.volume_drop_flags.items():
        if "glute" in mg.lower() or "hip" in mg.lower():
            glute_flag = True
            prior_sets = (strength.prior_4wk_avg.sets_by_muscle.get(mg, 0) if strength.prior_4wk_avg else 0)
            cur_sets = strength.current.sets_by_muscle.get(mg, 0)
            recs.append(
                f"Glute/hip sets dropped ({prior_sets:.0f} → {cur_sets:.0f} this week) — "
                "prioritize Goblet Squat, RDL, Banded Clamshell, and Glute Bridge before "
                "the weekend long run."
            )
    if not glute_flag and "Glutes" in strength.missed_muscle_groups:
        recs.append(
            "No glute sets recorded — prioritize Lower Body day. "
            "Glute strength is the single highest-leverage running injury prevention factor."
        )

    # Ground contact time
    if running.ground_contact_change_ms and running.ground_contact_change_ms > 5:
        recs.append(
            f"Ground contact time up {running.ground_contact_change_ms:.0f} ms vs. avg — "
            "cue: quick turnover, light foot strike. Add Dead Bug + Pallof Press to core work."
        )

    return recs


# ---------------------------------------------------------------------------
# Nutrition recommendations
# ---------------------------------------------------------------------------

def _nutrition_recommendations(
    nutrition: NutritionAnalysis,
    running: RunningAnalysis,
) -> List[str]:
    recs: List[str] = []
    cur = nutrition.current
    tgt_cal = cur.target_calories or 1377
    tgt_prot = cur.target_protein_g or 153
    tgt_carb = cur.target_carbs_g or 87

    # Always open with current MF target
    recs.append(
        f"MacroFactor current target: {tgt_cal:.0f} kcal | {tgt_prot:.0f}g protein | "
        f"{tgt_carb:.0f}g carbs | {cur.target_fat_g or 45:.0f}g fat. "
        f"{'✅ Week hit calorie target.' if (nutrition.calorie_target_rate or 0) >= 0.7 else '⚠️ Calorie target adherence below 70%.'}"
    )

    # Carb adequacy for run volume
    miles = running.current.total_miles
    if cur.avg_carbs_g is not None and cur.avg_carbs_g < tgt_carb:
        recs.append(
            f"Carbs averaged {cur.avg_carbs_g:.0f}g vs. {tgt_carb:.0f}g target "
            f"while running {miles:.1f} mi. "
            "Prioritize pre-run rice cake + honey and post-run banana to fuel glycogen replenishment."
        )
    if nutrition.low_carb_underfuel_flag:
        recs.append(
            f"⚠️ Critical: {miles:.0f} mi/week on {cur.avg_carbs_g or 0:.0f}g carbs/day risks "
            "workout degradation, muscle breakdown, and fatigue. Even within current low-calorie "
            "target, shift calories toward carbs by reducing fat slightly."
        )

    # Protein
    if nutrition.low_protein_flag:
        recs.append(
            f"Protein ({cur.avg_protein_g or 0:.0f}g avg) below muscle preservation floor (140g). "
            "Add a Greek yogurt bowl, cottage cheese, or protein shake to each day. "
            "Protein is non-negotiable during a caloric deficit."
        )
    else:
        recs.append(
            f"Protein ({cur.avg_protein_g or 0:.0f}g avg) is {('above' if (cur.avg_protein_g or 0) >= tgt_prot else 'near')} "
            f"the {tgt_prot:.0f}g target — keep this up."
        )

    # Calorie variance
    if nutrition.high_calorie_variance_flag:
        recs.append(
            f"Calorie variance (std dev {cur.calorie_stdev:.0f} kcal) is high. "
            "Batch-cooking and consistent meal prepping are the most effective fix. "
            "Aim to log every meal the same day it's eaten."
        )

    # Electrolytes for endurance
    elec_flags = {k: v for k, v in nutrition.micronutrient_flags.items()
                  if k in ("potassium", "sodium", "magnesium")}
    if elec_flags:
        names = ", ".join(k.replace("_", " ").title() for k in elec_flags)
        recs.append(
            f"Electrolyte gaps detected ({names}) — running {miles:.0f} mi/week "
            "requires above-average replenishment. Add electrolyte drink on long run days; "
            "include spinach, beans, bananas, and nuts in daily meals."
        )

    # Late-night hunger
    recs.append(
        "Evening hunger (known pattern): save 150–200 kcal for after dinner. "
        "Greek yogurt (150 kcal, 15g protein) is the optimal late-night buffer."
    )

    return recs


# ---------------------------------------------------------------------------
# Next week focus lines
# ---------------------------------------------------------------------------

def _next_week_focus(
    running: RunningAnalysis,
    nutrition: NutritionAnalysis,
    body_comp: BodyCompAnalysis,
) -> tuple[str, str]:
    # Training
    if running.overreach_flag:
        train = (
            f"Cap mileage at {running.rolling_4wk.total_miles * 1.10:.0f} mi and "
            "prioritize one full Lower Body + Core strength session."
        )
    elif running.fatigue_signal:
        train = (
            "Reduce intensity — swap one easy run for a full rest day and focus "
            "on strength quality over run volume."
        )
    elif running.current.trail_run_count == 0:
        train = (
            "Add one trail/mountain run with ≥500 ft gain to build elevation capacity "
            "for June Europe hiking and 14er season."
        )
    else:
        train = (
            f"Maintain current run volume ({running.current.total_miles:.0f} mi) "
            "and complete both Feb 2026 strength sessions."
        )

    # Nutrition
    if body_comp.algorithm_recalibrating:
        nutrition_focus = (
            "Log every meal every day — MacroFactor needs consistent data to "
            "recalibrate TDEE. Hit protein target (153g) daily above all else."
        )
    elif nutrition.low_protein_flag:
        nutrition_focus = (
            f"Close the protein gap: target {nutrition.current.target_protein_g or 153:.0f}g/day "
            "using Greek yogurt, tofu, and eggs as primary sources."
        )
    elif nutrition.low_carb_underfuel_flag:
        nutrition_focus = (
            "Raise daily carbs above 80g to support run performance — "
            "add rice/oats pre-run and banana post-run without exceeding calorie target."
        )
    else:
        nutrition_focus = (
            f"Hit calorie target ({nutrition.current.target_calories or 1377:.0f} kcal) "
            "within ±100 kcal on ≥5 of 7 days and maintain protein ≥153g."
        )

    return train, nutrition_focus
