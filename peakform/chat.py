"""PeakForm interactive Q&A agent.

Wraps the Anthropic Messages API with a stateful conversation pre-loaded
with the user's weekly report and raw data tables so the model can answer
specific, data-backed questions about their training and nutrition.
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class PeakFormAgent:
    """Stateful Q&A agent grounded in the user's fitness & nutrition data.

    Parameters
    ----------
    report_md : str
        The formatted weekly Markdown report produced by agent.run_full().
    mf_data : MacroFactorData
        Parsed MacroFactor object (provides raw nutrition / weight tables).
    garmin_data : GarminData
        Parsed Garmin object (provides raw activity log).
    week_start, week_end : pd.Timestamp
        The analysis window used to generate the report.
    api_key : str, optional
        Anthropic API key.  Falls back to the ANTHROPIC_API_KEY env var.
    model : str
        Anthropic model ID.  Defaults to claude-haiku-4-5 for low latency.
    """

    def __init__(
        self,
        report_md: str,
        mf_data,
        garmin_data,
        week_start: pd.Timestamp,
        week_end: pd.Timestamp,
        api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
    ):
        self._model = model
        self._history: list[dict] = []

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "No Anthropic API key found.\n"
                "Add ANTHROPIC_API_KEY to Colab Secrets (🔑 sidebar) and toggle "
                "'Notebook access' ON, then re-run the setup cell."
            )

        import anthropic
        self._client = anthropic.Anthropic(api_key=key)
        self._system = self._build_system(
            report_md, mf_data, garmin_data, week_start, week_end
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, message: str) -> str:
        """Send a user message and return the model's response."""
        self._history.append({"role": "user", "content": message})
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=self._system,
            messages=self._history,
        )
        reply = response.content[0].text
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def reset(self):
        """Clear conversation history while keeping the data context."""
        self._history = []

    # ------------------------------------------------------------------
    # System prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_system(
        report_md: str,
        mf_data,
        garmin_data,
        week_start: pd.Timestamp,
        week_end: pd.Timestamp,
    ) -> str:
        parts = [
            "You are PeakForm, a personal fitness and nutrition coach with full access "
            "to the user's training data. Answer questions directly using their actual "
            "numbers. Be concise, specific, and actionable. Cite exact values (dates, "
            "distances, calories, weights) when available. If data is missing or "
            "incomplete say so clearly. Format responses in Markdown.",
            "",
            f"## Weekly Report  "
            f"({week_start.strftime('%Y-%m-%d')} – {week_end.strftime('%Y-%m-%d')})",
            "",
            report_md,
            "",
            "## Raw Data (last 30 days)",
            "",
            PeakFormAgent._nutrition_table(mf_data, week_end),
            "",
            PeakFormAgent._weight_table(mf_data, week_end),
            "",
            PeakFormAgent._activities_table(garmin_data, week_end),
        ]
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Data serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _nutrition_table(mf_data, week_end: pd.Timestamp) -> str:
        try:
            df = mf_data.calories_macros
            if df.empty:
                return "### Nutrition: no data available"

            cutoff = week_end - pd.Timedelta(days=30)
            df = df[df["date"] >= cutoff].copy()

            cal_col = next(
                (c for c in df.columns if "calorie" in c.lower() or "kcal" in c.lower()),
                None,
            )
            prot_col = next(
                (c for c in df.columns if "protein" in c.lower()), None
            )
            carb_col = next(
                (c for c in df.columns if "carb" in c.lower()), None
            )
            fat_col = next(
                (c for c in df.columns if "fat" in c.lower() and "pct" not in c.lower()),
                None,
            )

            def _v(row, col):
                if col and col in row.index and pd.notna(row[col]):
                    return f"{float(row[col]):.0f}"
                return "—"

            lines = [
                "### Nutrition log (last 30 days)",
                "Date | Calories | Protein (g) | Carbs (g) | Fat (g)",
                "--- | --- | --- | --- | ---",
            ]
            for _, row in df.iterrows():
                lines.append(
                    f"{row['date'].strftime('%Y-%m-%d')} | "
                    f"{_v(row, cal_col)} | {_v(row, prot_col)} | "
                    f"{_v(row, carb_col)} | {_v(row, fat_col)}"
                )
            return "\n".join(lines)
        except Exception as exc:
            return f"### Nutrition: error reading data ({exc})"

    @staticmethod
    def _weight_table(mf_data, week_end: pd.Timestamp) -> str:
        try:
            sw = mf_data.scale_weight
            wt = mf_data.weight_trend
            cutoff = week_end - pd.Timedelta(days=30)

            frames: dict = {}
            if not sw.empty:
                w_col = next((c for c in sw.columns if c != "date"), None)
                if w_col:
                    frames["scale"] = sw[sw["date"] >= cutoff].set_index("date")[w_col]
            if not wt.empty:
                t_col = next((c for c in wt.columns if c != "date"), None)
                if t_col:
                    frames["trend"] = wt[wt["date"] >= cutoff].set_index("date")[t_col]

            if not frames:
                return "### Weight: no data available"

            merged = pd.DataFrame(frames).sort_index()
            lines = [
                "### Weight readings (last 30 days)",
                "Date | Scale (lbs) | Trend (lbs)",
                "--- | --- | ---",
            ]
            for dt, row in merged.iterrows():
                s = (
                    f"{float(row['scale']):.1f}"
                    if "scale" in row.index and pd.notna(row.get("scale"))
                    else "—"
                )
                t = (
                    f"{float(row['trend']):.1f}"
                    if "trend" in row.index and pd.notna(row.get("trend"))
                    else "—"
                )
                lines.append(f"{dt.strftime('%Y-%m-%d')} | {s} | {t}")
            return "\n".join(lines)
        except Exception as exc:
            return f"### Weight: error reading data ({exc})"

    @staticmethod
    def _activities_table(garmin_data, week_end: pd.Timestamp) -> str:
        try:
            from peakform.parsers.garmin import _decimal_minutes_to_mmss

            cutoff = week_end - pd.Timedelta(days=30)
            df = garmin_data.all_activities
            if df.empty:
                return "### Activities: no data available"

            df = df[(df["date"] >= cutoff) & (df["date"] <= week_end)].copy()
            if df.empty:
                return "### Activities: none in last 30 days"

            def _f(val, fmt=".1f"):
                try:
                    return f"{float(val):{fmt}}" if pd.notna(val) else "—"
                except (TypeError, ValueError):
                    return "—"

            lines = [
                "### Activity log (last 30 days)",
                "Date | Type | Distance (mi) | Pace (min/mi) | Avg HR | Duration (min)",
                "--- | --- | --- | --- | --- | ---",
            ]
            for _, row in df.iterrows():
                pace_raw = row.get("avg_pace")
                pace = _decimal_minutes_to_mmss(pace_raw) if pd.notna(pace_raw) else "—"
                dur_sec = row.get("duration")
                dur = f"{float(dur_sec) / 60:.0f}" if pd.notna(dur_sec) else "—"
                lines.append(
                    f"{row['date'].strftime('%Y-%m-%d')} | "
                    f"{str(row.get('activity_type', '—'))} | "
                    f"{_f(row.get('distance_mi'))} | "
                    f"{pace} | "
                    f"{_f(row.get('avg_hr'), '.0f')} | "
                    f"{dur}"
                )
            return "\n".join(lines)
        except Exception as exc:
            return f"### Activities: error reading data ({exc})"
