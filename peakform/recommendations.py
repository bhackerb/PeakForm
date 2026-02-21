"""PeakForm Smart Recommendations — 4-phase AI planning engine.

Phases
------
  0  Landing      — module overview, entry point
  1  Interview    — user fills subjective biofeedback + new MF targets
  2  Analysis     — AI synthesises Garmin + MF + biofeedback → performance assessment
  3  Proposal     — AI proposes nutrition pivot + training intensity; user approves
  4  Template     — AI generates finalised 7-day downloadable weekly plan
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class InterviewState:
    """All data collected across the 4-phase interview."""

    phase: int = 0

    # ── Phase 1 — Biofeedback ────────────────────────────────────────────────
    sleep_score: int = 5        # 1–10  (1 = terrible, 10 = perfect)
    hunger_score: int = 5       # 1–10  (1 = never hungry, 10 = ravenous)
    rpe_score: int = 5          # 1–10  (1 = very easy week, 10 = maximal)
    biofeedback_notes: str = ""

    # ── Phase 1 — Training context ───────────────────────────────────────────
    mesocycle_week: int = 1
    mesocycle_length: int = 8   # 4 / 8 / 12 / 16
    mesocycle_type: str = "Base Build"   # Base Build | Strength Block | Peak | Taper | Maintenance

    # ── Phase 1 — New MacroFactor targets (from strategy check-in) ───────────
    new_calories: float = 0.0
    new_protein_g: float = 0.0
    new_carbs_g: float = 0.0
    new_fat_g: float = 0.0

    # ── Phase 1 — Previous week's plan (pasted by user) ─────────────────────
    prev_plan_text: str = ""

    # ── Phase 2–4 outputs ────────────────────────────────────────────────────
    analysis_text: str = ""
    proposal_text: str = ""
    use_new_meals: bool = False
    week_template_md: str = ""


# ---------------------------------------------------------------------------
# Data-snapshot helpers  (build concise text blocks for AI prompts)
# ---------------------------------------------------------------------------

def _fmt_pace(dec_min: float) -> str:
    if dec_min <= 0:
        return "N/A"
    total_sec = round(dec_min * 60)
    return f"{total_sec // 60}:{total_sec % 60:02d}/mi"


def _running_ctx(ra) -> str:
    cur, avg = ra.current, ra.rolling_4wk
    lines = [
        f"- This week: **{cur.total_miles:.1f} mi** across {cur.run_count} run(s) "
        f"| +{cur.total_elevation_gain_ft:.0f} ft elevation",
    ]
    if avg.total_miles:
        lines.append(f"- 4-week average: {avg.total_miles:.1f} mi/wk")
        lines.append(f"- Mileage Δ vs avg: {ra.mileage_change_pct * 100:+.0f}%")
    if cur.flat_avg_pace_dec:
        lines.append(f"- Flat-run pace: {_fmt_pace(cur.flat_avg_pace_dec)}")
        if ra.pace_change_dec:
            direction = f"{abs(ra.pace_change_dec) * 60:.0f}s {'faster ✅' if ra.pace_change_dec < 0 else 'slower ⚠️'}"
            lines.append(f"- Pace Δ vs 4-wk avg: {direction}")
    if cur.flat_avg_hr:
        lines.append(f"- Avg HR: {cur.flat_avg_hr:.0f} bpm")
        if ra.hr_change:
            lines.append(f"- HR Δ vs avg: {ra.hr_change:+.0f} bpm")
    if cur.avg_body_battery_drain:
        lines.append(f"- Body Battery drain: {cur.avg_body_battery_drain:.1f} units/run")

    flags = []
    if ra.overreach_flag:             flags.append("⚠️ Mileage overreach (>10% above 4-wk avg)")
    if ra.recovery_debt_flag:         flags.append("⚠️ High body battery drain (avg >15 units/run)")
    if ra.aerobic_adaptation_signal:  flags.append("✅ Aerobic adaptation signal (pace ↓, HR stable)")
    if ra.fatigue_signal:             flags.append("⚠️ Fatigue signal (pace ↑ AND HR ↑ together)")
    if flags:
        lines.append("- Flags: " + " | ".join(flags))

    return "\n".join(lines)


def _nutrition_ctx(na) -> str:
    cur = na.current
    lines = [
        f"- Avg calories: **{cur.avg_calories:.0f} kcal** "
        f"(target {cur.target_calories:.0f} — {na.calories_pct_target * 100:.0f}% achieved)",
        f"- Avg protein: **{cur.avg_protein_g:.0f}g** "
        f"(target {cur.target_protein_g:.0f}g — hit on {na.protein_hit_rate * 100:.0f}% of days)",
        f"- Avg carbs: {cur.avg_carbs_g:.0f}g | avg fat: {cur.avg_fat_g:.0f}g",
        f"- Avg daily deficit vs TDEE: {na.avg_daily_deficit:.0f} kcal",
        f"- Logged days this week: {cur.logged_days}/7",
    ]
    flags = []
    if na.low_protein_flag:            flags.append("⚠️ Low protein (<140g daily avg)")
    if na.low_carb_underfuel_flag:     flags.append("⚠️ Carb underfuelling for mileage load")
    if na.high_calorie_variance_flag:  flags.append("⚠️ High calorie variance (std dev >300 kcal)")
    if na.incomplete_week_flag:        flags.append("⚠️ Incomplete logging week (<5 days)")
    if flags:
        lines.append("- Flags: " + " | ".join(flags))
    return "\n".join(lines)


def _body_comp_ctx(ba) -> str:
    lines = [
        f"- Trend weight: {ba.trend_weight_start:.1f} → **{ba.trend_weight_end:.1f} lbs** "
        f"({ba.trend_net_change_lbs:+.2f} lbs this week)",
        f"- Direction: **{ba.trend_direction}** | Rate: {ba.weekly_rate_lbs:.2f} lbs/wk",
        f"- To goal (160 lbs): {ba.pounds_to_goal:.1f} lbs remaining "
        f"(~{ba.weeks_to_goal:.0f} weeks at current rate)",
    ]
    if ba.trend_stalled:
        lines.append("- ⚠️ Trend stalled (<0.1 lb/wk change)")
    if ba.weight_rising_despite_deficit:
        lines.append("- ⚠️ Weight rising despite logged deficit — MacroFactor recalibrating")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Meal reference (used in template prompt)
# ---------------------------------------------------------------------------

_MEAL_ROTATION = """
| Meal | kcal | P (g) | C (g) | F (g) |
|------|------|-------|-------|-------|
| Yogurt PB Protein Bowl | 352 | 51 | 30 | 3 |
| Vegetarian Creole Jambalaya (1 srv) | 641 | 31 | 100 | 10 |
| Tofu Broccoli Parm (1 srv) | 474 | 35 | 60 | 12 |
| Pre-Run Snack (rice cake + PB + honey) | 175 | 4 | 20 | 9 |
| Banana Bread (1 slice) | 135 | 5 | 22 | 3 |
"""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_analysis_prompt(st_: InterviewState, ra, na, ba) -> str:
    return f"""You are Ben's elite AI performance coach at PeakForm. \
Synthesise the data below into a tight, actionable Performance-First Analysis \
before next week's planning session.

---
## Garmin Running — Last Week
{_running_ctx(ra)}

## MacroFactor Nutrition — Last Week
{_nutrition_ctx(na)}

## Body Composition — Last Week
{_body_comp_ctx(ba)}

## Subjective Biofeedback
| Metric | Score | Context |
|--------|-------|---------|
| Sleep quality | {st_.sleep_score}/10 | 1 = terrible, 10 = perfect |
| Hunger level | {st_.hunger_score}/10 | 1 = never hungry, 10 = ravenous all day |
| Overall weekly RPE | {st_.rpe_score}/10 | 1 = very easy, 10 = maximal effort |
| Notes | {st_.biofeedback_notes or "None provided"} | |

## Training Context
- Mesocycle: **Week {st_.mesocycle_week} of {st_.mesocycle_length}** — {st_.mesocycle_type}

## New MacroFactor Targets (just updated via strategy check-in)
| Calories | Protein | Carbs | Fat |
|----------|---------|-------|-----|
| **{st_.new_calories:.0f} kcal** | **{st_.new_protein_g:.0f}g** | **{st_.new_carbs_g:.0f}g** | **{st_.new_fat_g:.0f}g** |

## Previous Week's Plan (reference)
{st_.prev_plan_text or "_Not provided._"}

---
Deliver the analysis in these exact sections (3–5 bullet points each, \
bold critical risks):

### 1. Strategy Alignment Check
Does the new MacroFactor calorie/carb target make sense given Garmin training stress? \
Call out conflicts explicitly (e.g. aggressive cut during rising mileage, \
low carbs on a high-volume run week).

### 2. Performance Trend
Is running trending **UP / PLATEAUING / DECLINING**? \
Cite pace, HR, and body battery numbers. Compare to 4-week baseline.

### 3. Recovery Status
Verdict (pick one): **Recovered | Mildly Fatigued | Significantly Fatigued** \
Synthesise body battery, RPE ({st_.rpe_score}/10), sleep ({st_.sleep_score}/10), \
and hunger ({st_.hunger_score}/10) into a 2–3 sentence explanation.

### 4. Injury & Overtraining Risk
Rate: **Low | Moderate | High** \
Factor mileage trend, body battery drain, cycle week ({st_.mesocycle_week}/{st_.mesocycle_length}), \
and subjective RPE.

### 5. Nutrition–Performance Link
Identify 1–3 specific timing adjustments to optimise run performance next week \
(e.g. "Add 40g carbs Thursday evening to fuel Friday long run").
"""


def build_proposal_prompt(analysis: str, st_: InterviewState) -> str:
    return f"""Based on this performance analysis:

{analysis}

Generate a concise **Strategy Proposal** for next week. \
A coach must be able to read it in 90 seconds. Use this exact structure:

---
## Nutritional Pivot
Current MacroFactor targets: \
**{st_.new_calories:.0f} kcal / {st_.new_protein_g:.0f}g P / \
{st_.new_carbs_g:.0f}g C / {st_.new_fat_g:.0f}g F**

Propose day-type adjustments (weekly average must still align with MF strategy):
- **Rest days:** [kcal] | [P]g P / [C]g C / [F]g F — [1-line rationale]
- **Easy run days:** [kcal] | [P]g P / [C]g C / [F]g F — [timing note]
- **Long / hard run days:** [kcal] | [P]g P / [C]g C / [F]g F — [pre/during/post note]
- **Strength-only days:** [kcal] | [P]g P / [C]g C / [F]g F — [protein timing]

## Workout Intensity Verdict
**→ [Stay the Course | Slight Deload (−10–15% volume) | Full Deload | Push Week (+5–10%)]**
Reason: [2 sentences]

## Suggested Training Schedule (Mon–Sun)
| Day | Training |
|-----|----------|
| Mon | |
| Tue | |
| Wed | |
| Thu | |
| Fri | |
| Sat | |
| Sun | |

## ⚠️ Watch Item This Week
[Single most important thing that could derail progress — be specific]
"""


def build_template_prompt(st_: InterviewState, meal_instruction: str) -> str:
    return f"""Generate a complete, finalized **7-day PeakForm Weekly Plan** as clean Markdown.

## Approved Strategy
{st_.proposal_text}

## Hard Macro Constraints
Every single day MUST hit these targets within the tolerances shown:
| Macro | Target | Tolerance |
|-------|--------|-----------|
| Calories | {st_.new_calories:.0f} kcal | ±50 kcal |
| Protein | {st_.new_protein_g:.0f}g | ±5g |
| Carbs | {st_.new_carbs_g:.0f}g | ±10g |
| Fat | {st_.new_fat_g:.0f}g | ±5g |

## Meal Options (use exact macro values)
{_MEAL_ROTATION}

## Meal Approach
{meal_instruction}

---
## Required Output Format

Start with this header block:
```
# 📋 PeakForm Weekly Plan
**Mesocycle:** Week {st_.mesocycle_week} of {st_.mesocycle_length} — {st_.mesocycle_type}
**Daily Targets:** {st_.new_calories:.0f} kcal · {st_.new_protein_g:.0f}g P · \
{st_.new_carbs_g:.0f}g C · {st_.new_fat_g:.0f}g F
```

Then repeat this block for each day, Monday through Sunday:
```
### [Day Name]
**Training:** [from approved schedule]
**Calorie Target:** [X] kcal

| Meal | kcal | P (g) | C (g) | F (g) |
|------|------|-------|-------|-------|
| Breakfast | | | | |
| [Mid-morning snack if needed] | | | | |
| Lunch | | | | |
| [Pre-run / pre-workout if needed] | | | | |
| Dinner | | | | |
| [Evening snack if needed] | | | | |
| **DAILY TOTAL** | **[X]** | **[X]** | **[X]** | **[X]** |

> **Timing note:** [1–2 sentences on meal timing around training]

---
```

After all 7 days, append:
```
## 🛒 Grocery List
**Produce:** ...
**Proteins/Dairy:** ...
**Pantry:** ...
Only items needed beyond standard pantry staples.

## 🍳 Sunday Batch Prep
**Primary batch:** [recipe name]
**Steps:**
1. ...
2. ...
**Estimated prep time:** [X min]
```

CRITICAL: Verify every DAILY TOTAL row yourself before outputting it. \
Protein must be ≥{st_.new_protein_g - 5:.0f}g and ≤{st_.new_protein_g + 5:.0f}g. \
Calories must be ≥{st_.new_calories - 50:.0f} and ≤{st_.new_calories + 50:.0f}. \
Do not round in a way that causes a day to miss the target.
"""


# ---------------------------------------------------------------------------
# Claude API calls
# ---------------------------------------------------------------------------

_MODEL_ANALYSIS  = "claude-sonnet-4-5-20250929"   # strong reasoning for analysis/proposal
_MODEL_TEMPLATE  = "claude-sonnet-4-5-20250929"    # long structured output for template


def _call(prompt: str, api_key: str, model: str, max_tokens: int = 4096) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def run_analysis(
    state: InterviewState,
    mf_data,
    garmin_data,
    week_start,
    week_end,
    api_key: str,
) -> str:
    from peakform.analyzers import running as _r, nutrition as _n, body_comp as _b

    ra = _r.analyze(garmin_data, week_start, week_end)
    na = _n.analyze(mf_data, week_start, week_end, weekly_mileage=ra.current.total_miles)
    ba = _b.analyze(mf_data, week_start, week_end, avg_daily_deficit=na.avg_daily_deficit)

    return _call(build_analysis_prompt(state, ra, na, ba), api_key, _MODEL_ANALYSIS)


def run_proposal(state: InterviewState, api_key: str) -> str:
    return _call(
        build_proposal_prompt(state.analysis_text, state),
        api_key,
        _MODEL_ANALYSIS,
    )


def run_template(state: InterviewState, api_key: str) -> str:
    if state.use_new_meals:
        meal_instruction = (
            "Suggest new high-protein, vegetarian-friendly meals beyond the standard rotation. "
            "Include rotation options where they fit. All new meals must have verified macro values."
        )
    else:
        meal_instruction = (
            "Use Ben's existing meal rotation only. Adjust portion sizes where needed to hit daily targets. "
            "Do not introduce new meals."
        )
    return _call(
        build_template_prompt(state, meal_instruction),
        api_key,
        _MODEL_TEMPLATE,
        max_tokens=8000,
    )
