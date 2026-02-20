"""PeakForm charts — Plotly figures for the Charts tab.

Eight interactive charts covering weight, mileage, calories, macros,
pace, strength volume, calorie balance, and plan adherence.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from peakform.config import (
    CALORIE_ADHERENCE_WINDOW_KCAL,
    GOAL_WEIGHT_LBS,
    MILESTONE_14ER_SEASON,
    MILESTONE_AESTHETIC,
    MILESTONE_EUROPE_TRIP_START,
    PRIORITY_MUSCLE_GROUPS,
    STRENGTH_ACTIVITY_TYPES,
)


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

_BG = "#0E1117"
_SURFACE = "#1A1D27"
_TEXT = "#FAFAFA"
_GRID = "#2A2D3A"
_PRIMARY = "#4F8BF9"
_SUCCESS = "#2ECC71"
_WARNING = "#F39C12"
_DANGER = "#E74C3C"
_MUTED = "#6C757D"

_BASE = dict(
    paper_bgcolor=_BG,
    plot_bgcolor=_SURFACE,
    font=dict(color=_TEXT, family="sans-serif", size=13),
    margin=dict(l=50, r=20, t=50, b=50),
    hovermode="x unified",
    xaxis=dict(gridcolor=_GRID, zeroline=False, showgrid=True),
    yaxis=dict(gridcolor=_GRID, zeroline=False, showgrid=True),
    legend=dict(
        orientation="h",
        y=-0.18,
        font=dict(size=12),
    ),
)


# ---------------------------------------------------------------------------
# Column-finding helper
# ---------------------------------------------------------------------------

def _col(df: pd.DataFrame, *keywords) -> Optional[str]:
    """Return the first column whose name contains any keyword (case-insensitive)."""
    for kw in keywords:
        for c in df.columns:
            if kw.lower() in c.lower():
                return c
    return None


def _empty_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color=_MUTED),
    )
    fig.update_layout(**_BASE, height=220)
    return fig


def _fmt_pace(decimal_minutes: float) -> str:
    """Convert decimal minutes/mile to MM:SS string."""
    if pd.isna(decimal_minutes):
        return "--"
    total_sec = round(decimal_minutes * 60)
    return f"{total_sec // 60}:{total_sec % 60:02d}/mi"


# ---------------------------------------------------------------------------
# 1. Weight Trend
# ---------------------------------------------------------------------------

def weight_trend_chart(mf_data) -> go.Figure:
    """Daily scale readings + smoothed MacroFactor trend line."""
    scale_df = mf_data.scale_weight
    trend_df = mf_data.weight_trend

    fig = go.Figure()

    if not scale_df.empty:
        w_col = _col(scale_df, "weight")
        if w_col:
            valid = scale_df.dropna(subset=[w_col])
            fig.add_trace(go.Scatter(
                x=valid["date"],
                y=valid[w_col],
                mode="markers",
                name="Scale reading",
                marker=dict(color=_MUTED, size=5, opacity=0.65),
                hovertemplate="%{x|%b %d}: %{y:.1f} lbs<extra></extra>",
            ))

    if not trend_df.empty:
        t_col = _col(trend_df, "trend", "weight")
        if t_col:
            valid = trend_df.dropna(subset=[t_col])
            fig.add_trace(go.Scatter(
                x=valid["date"],
                y=valid[t_col],
                mode="lines",
                name="Trend weight",
                line=dict(color=_PRIMARY, width=2.5),
                hovertemplate="%{x|%b %d}: %{y:.1f} lbs<extra></extra>",
            ))

    fig.add_hline(
        y=GOAL_WEIGHT_LBS,
        line_dash="dash",
        line_color=_SUCCESS,
        annotation_text=f"Goal — {GOAL_WEIGHT_LBS:.0f} lbs",
        annotation_position="bottom right",
        annotation_font=dict(color=_SUCCESS, size=11),
    )

    for m_date, label in [
        (MILESTONE_AESTHETIC, "Aesthetic goal"),
        (MILESTONE_EUROPE_TRIP_START, "Europe"),
        (MILESTONE_14ER_SEASON, "14er season"),
    ]:
        fig.add_vline(
            x=pd.Timestamp(m_date).value,
            line_dash="dot",
            line_color=_WARNING,
            annotation_text=label,
            annotation_position="top right",
            annotation_font=dict(color=_WARNING, size=10),
        )

    fig.update_layout(
        **_BASE,
        title="Weight over Time",
        yaxis_title="lbs",
    )
    return fig


# ---------------------------------------------------------------------------
# 2. Weekly Mileage
# ---------------------------------------------------------------------------

def weekly_mileage_chart(garmin_data) -> go.Figure:
    """Total running distance per week, stacked road vs trail."""
    runs = garmin_data.runs
    if runs.empty:
        return _empty_fig("No running data available")

    runs = runs.copy()
    runs["week"] = runs["date"].dt.to_period("W").dt.start_time

    flat = (
        runs[runs["is_trail"] == False]  # noqa: E712
        .groupby("week")["distance_mi"]
        .sum()
        .reset_index()
    )
    trail = (
        runs[runs["is_trail"] == True]  # noqa: E712
        .groupby("week")["distance_mi"]
        .sum()
        .reset_index()
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=flat["week"],
        y=flat["distance_mi"],
        name="Road / Treadmill",
        marker_color=_PRIMARY,
        hovertemplate="Week of %{x|%b %d}: %{y:.1f} mi<extra></extra>",
    ))
    if not trail.empty:
        fig.add_trace(go.Bar(
            x=trail["week"],
            y=trail["distance_mi"],
            name="Trail",
            marker_color=_WARNING,
            hovertemplate="Week of %{x|%b %d}: %{y:.1f} mi trail<extra></extra>",
        ))

    fig.update_layout(
        **_BASE,
        title="Weekly Mileage",
        yaxis_title="Miles",
        barmode="stack",
    )
    return fig


# ---------------------------------------------------------------------------
# 3. Daily Calories vs Target
# ---------------------------------------------------------------------------

def calories_vs_target_chart(mf_data, days: int = 60) -> go.Figure:
    """Bar chart: calories logged each day vs target and TDEE."""
    cm = mf_data.calories_macros
    if cm.empty:
        return _empty_fig("No calorie data available")

    cal_col = _col(cm, "calorie", "kcal", "energy")
    if not cal_col:
        return _empty_fig("Could not locate calorie column")

    cutoff = cm["date"].max() - pd.Timedelta(days=days)
    df = cm[cm["date"] >= cutoff][["date", cal_col]].dropna(subset=[cal_col]).copy()
    df = df.rename(columns={cal_col: "calories"})

    targets = mf_data.get_current_targets()
    target_cal = targets["calories"]
    expenditure_cal = targets["expenditure_kcal"]

    colors = []
    for c in df["calories"]:
        if abs(c - target_cal) <= CALORIE_ADHERENCE_WINDOW_KCAL:
            colors.append(_SUCCESS)
        elif c > expenditure_cal:
            colors.append(_DANGER)
        else:
            colors.append(_MUTED)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["date"],
        y=df["calories"],
        name="Calories logged",
        marker_color=colors,
        hovertemplate="%{x|%b %d}: %{y:.0f} kcal<extra></extra>",
    ))
    fig.add_hline(
        y=target_cal,
        line_dash="dash",
        line_color=_SUCCESS,
        annotation_text=f"Target {target_cal:.0f} kcal",
        annotation_position="top left",
        annotation_font=dict(color=_SUCCESS, size=11),
    )
    fig.add_hline(
        y=expenditure_cal,
        line_dash="dot",
        line_color=_WARNING,
        annotation_text=f"TDEE {expenditure_cal:.0f} kcal",
        annotation_position="top right",
        annotation_font=dict(color=_WARNING, size=11),
    )

    fig.update_layout(
        **_BASE,
        title=f"Daily Calories vs. Target — last {days} days",
        yaxis_title="kcal",
    )
    return fig


# ---------------------------------------------------------------------------
# 4. Weekly Calorie Balance (deficit / surplus)
# ---------------------------------------------------------------------------

def weekly_deficit_chart(mf_data) -> go.Figure:
    """Weekly average calorie balance vs TDEE — negative = deficit."""
    cm = mf_data.calories_macros
    if cm.empty:
        return _empty_fig("No calorie data available")

    cal_col = _col(cm, "calorie", "kcal", "energy")
    if not cal_col:
        return _empty_fig("Could not locate calorie column")

    df = cm[["date", cal_col]].dropna(subset=[cal_col]).copy()
    df["week"] = df["date"].dt.to_period("W").dt.start_time
    weekly_intake = df.groupby("week")[cal_col].mean()

    exp_df = mf_data.expenditure
    if not exp_df.empty:
        exp_col = _col(exp_df, "expenditure", "tdee", "total")
        if exp_col:
            edf = exp_df[["date", exp_col]].dropna(subset=[exp_col]).copy()
            edf["week"] = edf["date"].dt.to_period("W").dt.start_time
            weekly_exp = edf.groupby("week")[exp_col].mean()
            common = weekly_intake.index.intersection(weekly_exp.index)
            balance = (weekly_intake[common] - weekly_exp[common]).reset_index()
            balance.columns = ["week", "balance"]
        else:
            tdee = mf_data.get_current_targets()["expenditure_kcal"]
            balance = (weekly_intake - tdee).reset_index()
            balance.columns = ["week", "balance"]
    else:
        tdee = mf_data.get_current_targets()["expenditure_kcal"]
        balance = (weekly_intake - tdee).reset_index()
        balance.columns = ["week", "balance"]

    colors = [_DANGER if v > 0 else _SUCCESS for v in balance["balance"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=balance["week"],
        y=balance["balance"],
        name="Calorie balance",
        marker_color=colors,
        hovertemplate="Week of %{x|%b %d}: %{y:+.0f} kcal/day<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=_TEXT, line_width=1)

    fig.update_layout(
        **_BASE,
        title="Weekly Calorie Balance vs. TDEE  (deficit = negative = green)",
        yaxis_title="kcal/day above TDEE",
    )
    return fig


# ---------------------------------------------------------------------------
# 5. Daily Protein vs Target
# ---------------------------------------------------------------------------

def protein_adherence_chart(mf_data, days: int = 60) -> go.Figure:
    """Daily protein intake vs target — green = hit, red = missed."""
    cm = mf_data.calories_macros
    if cm.empty:
        return _empty_fig("No nutrition data available")

    prot_col = _col(cm, "protein")
    if not prot_col:
        return _empty_fig("Could not locate protein column")

    cutoff = cm["date"].max() - pd.Timedelta(days=days)
    df = cm[cm["date"] >= cutoff][["date", prot_col]].dropna(subset=[prot_col]).copy()
    df = df.rename(columns={prot_col: "protein_g"})

    target_prot = mf_data.get_current_targets()["protein_g"]
    colors = [_SUCCESS if p >= target_prot else _DANGER for p in df["protein_g"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["date"],
        y=df["protein_g"],
        name="Protein",
        marker_color=colors,
        hovertemplate="%{x|%b %d}: %{y:.0f}g<extra></extra>",
    ))
    fig.add_hline(
        y=target_prot,
        line_dash="dash",
        line_color=_SUCCESS,
        annotation_text=f"Target {target_prot:.0f}g",
        annotation_position="top left",
        annotation_font=dict(color=_SUCCESS, size=11),
    )

    fig.update_layout(
        **_BASE,
        title=f"Daily Protein vs. Target — last {days} days",
        yaxis_title="Protein (g)",
    )
    return fig


# ---------------------------------------------------------------------------
# 6. Flat-Run Pace Trend
# ---------------------------------------------------------------------------

def pace_trend_chart(garmin_data) -> go.Figure:
    """Flat-run pace per run with 4-run rolling average. Lower = faster."""
    flat = garmin_data.flat_runs
    if flat.empty or "avg_pace" not in flat.columns:
        return _empty_fig("No flat-run pace data available")

    df = flat[["date", "avg_pace", "distance_mi"]].dropna(subset=["avg_pace"]).copy()
    df = df.sort_values("date")
    df["rolling"] = df["avg_pace"].rolling(4, min_periods=2).mean()

    tick_vals = np.linspace(df["avg_pace"].min(), df["avg_pace"].max(), 8)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["avg_pace"],
        mode="markers",
        name="Per-run pace",
        marker=dict(color=_PRIMARY, size=7, opacity=0.75),
        customdata=[_fmt_pace(v) for v in df["avg_pace"]],
        hovertemplate="%{x|%b %d}: %{customdata}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["rolling"],
        mode="lines",
        name="4-run avg",
        line=dict(color=_WARNING, width=2.5),
        customdata=[_fmt_pace(v) for v in df["rolling"]],
        hovertemplate="%{x|%b %d}: %{customdata}<extra></extra>",
    ))

    y_min = df["avg_pace"].min()
    y_max = df["avg_pace"].max()
    pad = (y_max - y_min) * 0.12 if y_max > y_min else 0.5

    fig.update_layout(
        **_BASE,
        title="Flat-Run Pace Trend  (lower = faster)",
        yaxis=dict(
            title="min/mile",
            range=[y_max + pad, y_min - pad],
            gridcolor=_GRID,
            tickvals=tick_vals,
            ticktext=[_fmt_pace(v) for v in tick_vals],
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# 7. Strength — Sets by Muscle Group (current week)
# ---------------------------------------------------------------------------

def muscle_group_chart(
    mf_data,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
) -> go.Figure:
    """Horizontal bar: sets per muscle group for the analysis week."""
    mg = mf_data.muscle_groups
    if mg.empty:
        return _empty_fig("No muscle group data available")

    mask = (mg["date"] >= week_start) & (mg["date"] <= week_end)
    week_df = mg[mask]
    if week_df.empty:
        return _empty_fig("No strength data found for this week")

    muscle_cols = [c for c in week_df.columns if c != "date"]
    totals = week_df[muscle_cols].sum().dropna()
    totals = totals[totals > 0].sort_values(ascending=True)

    if totals.empty:
        return _empty_fig("No sets logged this week")

    colors = [
        _SUCCESS if name in PRIORITY_MUSCLE_GROUPS else _PRIMARY
        for name in totals.index
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=totals.values,
        y=totals.index,
        orientation="h",
        marker_color=colors,
        hovertemplate="%{y}: %{x:.0f} sets<extra></extra>",
    ))

    fig.update_layout(
        **_BASE,
        title="Sets by Muscle Group — this week  (green = priority)",
        xaxis_title="Sets",
        yaxis=dict(gridcolor=_GRID),
        height=max(280, len(totals) * 32 + 80),
        margin=dict(l=130, r=20, t=50, b=40),
    )
    return fig


# ---------------------------------------------------------------------------
# 8. Plan Adherence Scorecard
# ---------------------------------------------------------------------------

def adherence_scorecard(
    mf_data,
    garmin_data,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
) -> Tuple[go.Figure, dict]:
    """
    Four gauge indicators: calorie adherence, protein adherence,
    runs logged, and strength sessions.

    Returns (fig, raw_scores_dict).
    """
    targets = mf_data.get_current_targets()
    target_cal = targets["calories"]
    target_prot = targets["protein_g"]

    scores: dict = {}

    cm = mf_data.calories_macros
    if not cm.empty:
        mask = (cm["date"] >= week_start) & (cm["date"] <= week_end)
        week_cm = cm[mask].copy()

        cal_col = _col(week_cm, "calorie", "kcal", "energy")
        prot_col = _col(week_cm, "protein")

        if cal_col and not week_cm.empty:
            cal_vals = week_cm[cal_col].dropna()
            n_on = int(((cal_vals - target_cal).abs() <= CALORIE_ADHERENCE_WINDOW_KCAL).sum())
            scores["calorie_adherence"] = n_on / max(len(cal_vals), 1) * 100
            scores["calorie_label"] = f"{n_on}/{len(cal_vals)} days"
        else:
            scores["calorie_adherence"] = 0
            scores["calorie_label"] = "no data"

        if prot_col and not week_cm.empty:
            prot_vals = week_cm[prot_col].dropna()
            n_hit = int((prot_vals >= target_prot).sum())
            scores["protein_adherence"] = n_hit / max(len(prot_vals), 1) * 100
            scores["protein_label"] = f"{n_hit}/{len(prot_vals)} days"
        else:
            scores["protein_adherence"] = 0
            scores["protein_label"] = "no data"
    else:
        scores.update({
            "calorie_adherence": 0, "calorie_label": "no data",
            "protein_adherence": 0, "protein_label": "no data",
        })

    # Running sessions
    run_count = len(garmin_data.runs_in_window(week_start, week_end))
    scores["run_adherence"] = min(run_count / 3.0, 1.0) * 100
    scores["run_label"] = f"{run_count} run{'s' if run_count != 1 else ''}"

    # Strength sessions
    all_week = garmin_data.week_window(week_start, week_end)
    str_count = int(all_week["activity_type"].isin(STRENGTH_ACTIVITY_TYPES).sum())
    scores["strength_adherence"] = min(str_count / 2.0, 1.0) * 100
    scores["strength_label"] = f"{str_count} session{'s' if str_count != 1 else ''}"

    # Build 4-gauge figure
    metrics = [
        ("Calories on target", "calorie_adherence", "calorie_label"),
        ("Protein target", "protein_adherence", "protein_label"),
        ("Runs logged", "run_adherence", "run_label"),
        ("Strength sessions", "strength_adherence", "strength_label"),
    ]

    fig = go.Figure()
    for i, (label, score_key, label_key) in enumerate(metrics):
        pct = scores[score_key]
        sub = scores[label_key]
        bar_color = _SUCCESS if pct >= 80 else (_WARNING if pct >= 50 else _DANGER)
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=pct,
            number=dict(suffix="%", font=dict(color=_TEXT, size=22)),
            title=dict(
                text=f"<b>{label}</b><br><span style='font-size:0.75em;color:{_MUTED}'>{sub}</span>",
                font=dict(color=_TEXT, size=13),
            ),
            gauge=dict(
                axis=dict(range=[0, 100], tickcolor=_GRID, tickfont=dict(color=_MUTED)),
                bar=dict(color=bar_color),
                bgcolor=_SURFACE,
                bordercolor=_GRID,
                steps=[
                    dict(range=[0, 50], color="#1A0808"),
                    dict(range=[50, 80], color="#1A1200"),
                    dict(range=[80, 100], color="#081A08"),
                ],
            ),
            domain=dict(row=0, column=i),
        ))

    fig.update_layout(
        paper_bgcolor=_BG,
        font=dict(color=_TEXT, family="sans-serif"),
        title=dict(
            text="Plan Adherence — This Week",
            font=dict(color=_TEXT, size=15),
        ),
        grid=dict(rows=1, columns=4, pattern="independent"),
        height=260,
        margin=dict(l=10, r=10, t=55, b=10),
    )
    return fig, scores
