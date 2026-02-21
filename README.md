# 🏔️ PeakForm

> AI-powered weekly performance intelligence for serious athletes. Garmin + MacroFactor → instant insights, smart recommendations, and a 7-day plan.

PeakForm turns your Garmin activity data and MacroFactor nutrition exports into a weekly performance report. An AI coach answers questions about your data, and a built-in planning engine generates a personalised training schedule and macro-verified meal plan — all in a single Streamlit dashboard.

## Features

- **Weekly Report** — auto-generated markdown summary of training load, nutrition adherence, and body composition trends
- **Interactive Charts** — running pace trends, strength volume, muscle group breakdown, and nutrition macro splits
- **AI Coach** — ask questions about your week's data in plain English, powered by Claude
- **Smart Plan** — a 4-phase interview engine that analyses your biofeedback, proposes a training strategy, and produces a macro-verified 7-day meal + training template

## Stack

- [Streamlit](https://streamlit.io) — UI
- [Anthropic Claude](https://anthropic.com) — AI coach & planning engine
- [Plotly](https://plotly.com) — charts
- Deployed on Google Cloud Run

## Usage

1. Export your **MacroFactor** data as `.xlsx` and your **Garmin** data as `.csv`
2. Upload both files in the sidebar
3. Click **Run Analysis**
4. Explore your report, charts, and smart plan
