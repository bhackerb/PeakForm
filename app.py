"""PeakForm — Streamlit web app (v0.3 · premium redesign).

Upload MacroFactor XLSX + Garmin CSV → instant weekly intelligence.
AI Coach lives in the sidebar so it's always one click away.
"""

from __future__ import annotations

import os
import tempfile

import streamlit as st

st.set_page_config(
    page_title="PeakForm",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────────────────────────────────────
# Global CSS — premium dark aurora theme
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
/* ─────────────────────────────────────────────────────────────────────────── */
/* Fonts                                                                       */
/* Headings  → Space Grotesk  (geometric, authoritative, screen-optimised)    */
/* Body      → Inter          (humanist, high-legibility at small sizes)       */
/* ─────────────────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* ── Global base — 16 px anchor so every rem is predictable ─────────────── */
html { font-size: 16px !important; }

/* ── Reset ───────────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
    font-size: 1rem !important;
    line-height: 1.6 !important;
    color: #cbd5e1 !important;
    -webkit-font-smoothing: antialiased !important;
}

/* ── App background ─────────────────────────────────────────────────────── */
.stApp {
    background: radial-gradient(ellipse at 20% 20%, #0f1729 0%, #080c14 45%, #0a0f1e 100%) !important;
}

/* ── Hide Streamlit chrome ──────────────────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0c1120 0%, #0d1528 60%, #0a1020 100%) !important;
    border-right: 1px solid rgba(129, 140, 248, 0.12) !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
[data-testid="stSidebar"] section[data-testid="stSidebarContent"] { overflow-y: auto; }

/* ── Sidebar scrollbar ──────────────────────────────────────────────────── */
[data-testid="stSidebar"] ::-webkit-scrollbar { width: 3px; }
[data-testid="stSidebar"] ::-webkit-scrollbar-track { background: transparent; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
    background: rgba(129, 140, 248, 0.35);
    border-radius: 10px;
}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(129, 140, 248, 0.18) !important;
    gap: 0;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    color: rgba(148, 163, 184, 0.6) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    padding: 0.7rem 1.6rem !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.01em !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #a5b4fc !important;
    border-bottom: 2px solid #818cf8 !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: #c7d2fe !important;
    background: rgba(129, 140, 248, 0.06) !important;
}

/* ── Primary button ─────────────────────────────────────────────────────── */
button[kind="primary"], [data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.02em !important;
    padding: 0.55rem 1.2rem !important;
    box-shadow: 0 0 18px rgba(99, 102, 241, 0.35), 0 2px 8px rgba(0,0,0,0.4) !important;
    transition: all 0.22s ease !important;
}
button[kind="primary"]:hover, [data-testid="stButton"] > button[kind="primary"]:hover {
    box-shadow: 0 0 32px rgba(139, 92, 246, 0.6), 0 4px 16px rgba(0,0,0,0.5) !important;
    transform: translateY(-1px) !important;
    background: linear-gradient(135deg, #7175f3 0%, #9b6cf8 100%) !important;
}
button[kind="primary"]:disabled {
    opacity: 0.35 !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── Secondary button ───────────────────────────────────────────────────── */
[data-testid="stButton"] > button[kind="secondary"],
[data-testid="stFormSubmitButton"] > button {
    background: rgba(99, 102, 241, 0.12) !important;
    color: #a5b4fc !important;
    border: 1px solid rgba(99, 102, 241, 0.3) !important;
    border-radius: 9px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    transition: all 0.2s ease !important;
}
[data-testid="stButton"] > button[kind="secondary"]:hover,
[data-testid="stFormSubmitButton"] > button:hover {
    background: rgba(99, 102, 241, 0.22) !important;
    border-color: rgba(129, 140, 248, 0.5) !important;
    color: #c7d2fe !important;
}

/* ── Text / password inputs ─────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: rgba(10, 15, 30, 0.7) !important;
    border: 1px solid rgba(99, 102, 241, 0.25) !important;
    border-radius: 9px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: rgba(129, 140, 248, 0.55) !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12) !important;
}

/* ── File uploader ──────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: transparent !important;
    border: none !important;
}
[data-testid="stFileUploaderDropzone"] {
    background: rgba(8, 12, 20, 0.85) !important;
    border: 1px dashed rgba(99, 102, 241, 0.35) !important;
    border-radius: 10px !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: rgba(129, 140, 248, 0.6) !important;
    background: rgba(99, 102, 241, 0.06) !important;
}
[data-testid="stFileUploaderDropzone"] p,
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] span { color: #94a3b8 !important; }
[data-testid="stFileUploaderDropzone"] button {
    background: rgba(99, 102, 241, 0.15) !important;
    border: 1px solid rgba(99, 102, 241, 0.35) !important;
    color: #a5b4fc !important;
    border-radius: 8px !important;
}
/* Uploaded file row */
[data-testid="stFileUploaderFile"],
[data-testid="stFileUploaderFileName"] {
    background: rgba(13, 21, 40, 0.7) !important;
    border: 1px solid rgba(99, 102, 241, 0.15) !important;
    border-radius: 8px !important;
    color: #cbd5e1 !important;
}
[data-testid="stFileUploaderFile"] small,
[data-testid="stFileUploaderFile"] p,
[data-testid="stFileUploaderFile"] span { color: #94a3b8 !important; }

/* ── Expander ───────────────────────────────────────────────────────────── */
[data-testid="stExpander"] details {
    background: rgba(8, 12, 20, 0.85) !important;
    border: 1px solid rgba(99, 102, 241, 0.18) !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] summary {
    background: transparent !important;
    color: #94a3b8 !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
[data-testid="stExpander"] summary:hover { color: #c7d2fe !important; }

/* ── Alerts / info boxes ─────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    background: rgba(13, 21, 40, 0.7) !important;
    border-radius: 10px !important;
    border-left-color: #6366f1 !important;
}

/* ── Spinner ────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: #818cf8 !important; }

/* ── Divider ────────────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid rgba(129, 140, 248, 0.12) !important;
    margin: 1.2rem 0 !important;
}

/* ── Download button ────────────────────────────────────────────────────── */
[data-testid="stDownloadButton"] button {
    background: rgba(16, 185, 129, 0.1) !important;
    color: #6ee7b7 !important;
    border: 1px solid rgba(16, 185, 129, 0.3) !important;
    border-radius: 9px !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    transition: all 0.2s ease !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: rgba(16, 185, 129, 0.2) !important;
    border-color: rgba(16, 185, 129, 0.5) !important;
}

/* ── Chat message bubbles (sidebar) ─────────────────────────────────────── */
.pf-msg-user {
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.25);
    border-radius: 10px 10px 3px 10px;
    padding: 0.55rem 0.75rem;
    margin: 0.35rem 0 0.35rem 1.5rem;
    color: #e2e8f0;
    font-size: 0.82rem;
    line-height: 1.45;
}
.pf-msg-assistant {
    background: rgba(17, 24, 39, 0.8);
    border: 1px solid rgba(129, 140, 248, 0.15);
    border-radius: 10px 10px 10px 3px;
    padding: 0.55rem 0.75rem;
    margin: 0.35rem 1.5rem 0.35rem 0;
    color: #cbd5e1;
    font-size: 0.82rem;
    line-height: 1.45;
}
.pf-msg-label {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.1rem;
}
.pf-msg-label-user  { color: #818cf8; text-align: right; }
.pf-msg-label-coach { color: #10b981; }

/* ── Scrollable chat history container ──────────────────────────────────── */
.pf-chat-history {
    max-height: 320px;
    overflow-y: auto;
    padding: 0.25rem 0;
    margin-bottom: 0.5rem;
}
.pf-chat-history::-webkit-scrollbar { width: 3px; }
.pf-chat-history::-webkit-scrollbar-thumb {
    background: rgba(129, 140, 248, 0.3);
    border-radius: 10px;
}

/* ── Markdown typography — full scale ───────────────────────────────────── */
/*
   Major-third scale (×1.250) anchored at 1rem = 16 px
   H1  2.25 rem  → 36 px    lh 1.2
   H2  1.75 rem  → 28 px    lh 1.25
   H3  1.375rem  → 22 px    lh 1.35
   H4  1.125rem  → 18 px    lh 1.4
   p / li  1 rem → 16 px    lh 1.65
*/
[data-testid="stMarkdown"] h1,
[data-testid="stMarkdown"] h2,
[data-testid="stMarkdown"] h3,
[data-testid="stMarkdown"] h4 {
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    letter-spacing: -0.02em !important;
}
[data-testid="stMarkdown"] h1 {
    font-size: 2.25rem !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
    color: #a5b4fc !important;
    margin-top: 0 !important;
    margin-bottom: 0.75rem !important;
}
[data-testid="stMarkdown"] h2 {
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    line-height: 1.25 !important;
    color: #a5b4fc !important;
    margin-top: 2rem !important;
    margin-bottom: 0.5rem !important;
    padding-bottom: 0.35rem !important;
    border-bottom: 1px solid rgba(129, 140, 248, 0.2) !important;
}
[data-testid="stMarkdown"] h3 {
    font-size: 1.375rem !important;
    font-weight: 600 !important;
    line-height: 1.35 !important;
    color: #c7d2fe !important;
    margin-top: 1.5rem !important;
    margin-bottom: 0.4rem !important;
}
[data-testid="stMarkdown"] h4 {
    font-size: 1.125rem !important;
    font-weight: 600 !important;
    line-height: 1.4 !important;
    color: #e2e8f0 !important;
    margin-top: 1.2rem !important;
    margin-bottom: 0.3rem !important;
}
[data-testid="stMarkdown"] p {
    font-size: 1rem !important;
    line-height: 1.65 !important;
    color: #cbd5e1 !important;
    margin-bottom: 0.75rem !important;
}
[data-testid="stMarkdown"] li {
    font-size: 1rem !important;
    line-height: 1.65 !important;
    color: #cbd5e1 !important;
    margin-bottom: 0.3rem !important;
}
[data-testid="stMarkdown"] ul,
[data-testid="stMarkdown"] ol { color: #cbd5e1 !important; padding-left: 1.4rem !important; }
[data-testid="stMarkdown"] strong { color: #e2e8f0 !important; font-weight: 600 !important; }
[data-testid="stMarkdown"] table {
    width: 100%;
    border-collapse: collapse;
}
[data-testid="stMarkdown"] th {
    background: rgba(99, 102, 241, 0.15) !important;
    color: #a5b4fc !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    padding: 0.6rem 0.8rem !important;
    border: 1px solid rgba(99, 102, 241, 0.15) !important;
}
[data-testid="stMarkdown"] td {
    color: #cbd5e1 !important;
    font-size: 0.875rem !important;
    padding: 0.5rem 0.8rem !important;
    border: 1px solid rgba(129, 140, 248, 0.08) !important;
    background: rgba(13, 21, 40, 0.4) !important;
}
[data-testid="stMarkdown"] tr:hover td {
    background: rgba(99, 102, 241, 0.06) !important;
}
[data-testid="stMarkdown"] code {
    background: rgba(99, 102, 241, 0.15) !important;
    color: #a5b4fc !important;
    border-radius: 4px !important;
    padding: 0.15rem 0.4rem !important;
    font-size: 0.85em !important;
}
[data-testid="stMarkdown"] blockquote {
    border-left: 3px solid #6366f1 !important;
    background: rgba(99, 102, 241, 0.07) !important;
    padding: 0.6rem 1rem !important;
    border-radius: 0 8px 8px 0 !important;
    color: #94a3b8 !important;
}

/* ── Global scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.3);
    border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.55); }

/* ── Caption ────────────────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] {
    color: rgba(148, 163, 184, 0.7) !important;
    font-size: 0.8rem !important;
    line-height: 1.5 !important;
}

/* ── Global heading font (Space Grotesk everywhere) ─────────────────────── */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    letter-spacing: -0.02em !important;
}

/* ── Tab labels ─────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 0.9rem !important;
    letter-spacing: 0.01em !important;
}

/* ── Metric widget ──────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: rgba(13, 21, 40, 0.6);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 12px;
    padding: 0.9rem 1rem;
}
[data-testid="stMetricValue"] { color: #a5b4fc !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #94a3b8 !important; }
[data-testid="stMetricDelta"]  { font-size: 0.85rem !important; }

/* ── Widget labels ──────────────────────────────────────────────────────── */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label { color: #94a3b8 !important; font-size: 0.85rem !important; }

/* ── General paragraph / body text ─────────────────────────────────────── */
p, .stMarkdown p { color: #cbd5e1 !important; }
label                               { color: #94a3b8 !important; }

/* ── Number inputs ──────────────────────────────────────────────────────── */
input[type="number"],
[data-testid="stNumberInput"] input {
    background: rgba(10, 15, 30, 0.7) !important;
    border: 1px solid rgba(99, 102, 241, 0.25) !important;
    border-radius: 9px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}

/* ── Select boxes ───────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] [data-baseweb="select"] > div { background: rgba(10, 15, 30, 0.7) !important; color: #e2e8f0 !important; border-color: rgba(99, 102, 241, 0.25) !important; }
[data-baseweb="popover"] [data-baseweb="menu"]             { background: #0d1528 !important; border: 1px solid rgba(99,102,241,0.2) !important; }
[data-baseweb="option"]                                    { background: transparent !important; color: #cbd5e1 !important; }
[data-baseweb="option"]:hover                              { background: rgba(99,102,241,0.15) !important; }

/* ── Checkbox / radio ───────────────────────────────────────────────────── */
[data-testid="stCheckbox"] label p,
[data-testid="stRadio"]    label p { color: #cbd5e1 !important; }

/* ── Placeholder ────────────────────────────────────────────────────────── */
::placeholder { color: rgba(148, 163, 184, 0.4) !important; }

/* ── Sidebar text ───────────────────────────────────────────────────────── */
[data-testid="stSidebar"] p     { color: #94a3b8 !important; }
[data-testid="stSidebar"] label { color: #94a3b8 !important; }

/* ── Alert / warning text ───────────────────────────────────────────────── */
[data-testid="stAlert"] p,
[data-testid="stAlert"] div { color: #e2e8f0 !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# HTML component helpers
# ─────────────────────────────────────────────────────────────────────────────

def _html_logo() -> str:
    return """
<div style="padding:0.25rem 0 1.25rem 0; text-align:center;">
  <div style="
    font-size:2rem; margin-bottom:0.2rem; line-height:1;
    filter: drop-shadow(0 0 12px rgba(129,140,248,0.6));
  ">🏔️</div>
  <div style="
    background: linear-gradient(135deg, #818cf8 0%, #c084fc 60%, #818cf8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 1.45rem; font-weight: 900; letter-spacing: -0.03em; line-height:1;
  ">PeakForm</div>
  <div style="color:rgba(100,116,139,0.7); font-size:0.7rem; font-weight:500;
    text-transform:uppercase; letter-spacing:0.1em; margin-top:0.3rem;">
    Fitness &amp; Nutrition Intelligence
  </div>
</div>
"""


def _html_section_label(text: str, icon: str = "") -> str:
    return f"""
<div style="
  display:flex; align-items:center; gap:0.45rem;
  color:rgba(100,116,139,0.8); font-size:0.7rem; font-weight:700;
  text-transform:uppercase; letter-spacing:0.1em;
  margin:1.1rem 0 0.6rem 0;
">
  {f'<span style="font-size:0.85rem">{icon}</span>' if icon else ''}
  {text}
</div>
"""


def _html_week_banner(week_label: str) -> str:
    return f"""
<div style="
  display:flex; align-items:center; justify-content:space-between;
  background: linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(139,92,246,0.08) 100%);
  border: 1px solid rgba(99,102,241,0.2);
  border-radius: 14px;
  padding: 1rem 1.4rem;
  margin-bottom: 1.4rem;
  backdrop-filter: blur(20px);
">
  <div>
    <div style="color:rgba(148,163,184,0.6); font-size:0.72rem; font-weight:600;
      text-transform:uppercase; letter-spacing:0.09em; margin-bottom:0.3rem;">
      Analysis Week
    </div>
    <div style="
      background: linear-gradient(135deg, #a5b4fc 0%, #c084fc 100%);
      -webkit-background-clip:text; -webkit-text-fill-color:transparent;
      background-clip:text;
      font-size:1.5rem; font-weight:800; letter-spacing:-0.02em;
    ">{week_label}</div>
  </div>
  <div style="font-size:2rem; opacity:0.5; filter:drop-shadow(0 0 8px rgba(129,140,248,0.4));">🏔️</div>
</div>
"""


def _html_section_header(title: str, subtitle: str = "") -> str:
    sub = f'<div style="color:rgba(148,163,184,0.55);font-size:0.8rem;margin-top:0.2rem">{subtitle}</div>' if subtitle else ""
    return f"""
<div style="margin:0.5rem 0 1.1rem 0;">
  <div style="
    background:linear-gradient(135deg,#818cf8 0%,#c084fc 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;
    font-size:1.15rem;font-weight:800;letter-spacing:-0.01em;
  ">{title}</div>
  {sub}
</div>
"""


def _html_feature_card(icon: str, title: str, body: str, glow_color: str = "#6366f1") -> str:
    return f"""
<div style="
  background: linear-gradient(135deg, rgba(17,24,39,0.95) 0%, rgba(30,41,59,0.5) 100%);
  border: 1px solid rgba(99,102,241,0.18);
  border-radius: 16px;
  padding: 1.4rem;
  height:100%;
  backdrop-filter: blur(20px);
  box-shadow: 0 4px 30px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
">
  <div style="font-size:2rem;margin-bottom:0.7rem;filter:drop-shadow(0 0 10px {glow_color}44)">{icon}</div>
  <div style="
    font-size:1rem;font-weight:700;margin-bottom:0.4rem;
    color:#e2e8f0;letter-spacing:-0.01em;
  ">{title}</div>
  <div style="color:rgba(148,163,184,0.7);font-size:0.83rem;line-height:1.55;">{body}</div>
</div>
"""


def _html_chat_history(messages: list) -> str:
    if not messages:
        return """
<div style="text-align:center;padding:1.5rem 0;color:rgba(100,116,139,0.5);font-size:0.8rem;">
  No messages yet.<br>Ask me anything about your data!
</div>"""
    items = []
    for msg in messages[-10:]:  # show last 10
        role = msg["role"]
        content = msg["content"]
        # Escape HTML in content
        safe = (content
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>"))
        if role == "user":
            items.append(f"""
<div class="pf-msg-label pf-msg-label-user">You</div>
<div class="pf-msg-user">{safe}</div>""")
        else:
            items.append(f"""
<div class="pf-msg-label pf-msg-label-coach">🏔 Coach</div>
<div class="pf-msg-assistant">{safe}</div>""")
    return f'<div class="pf-chat-history">{"".join(items)}</div>'


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _save_upload(upload, suffix: str) -> str:
    if "tmp_dir" not in st.session_state:
        st.session_state.tmp_dir = tempfile.mkdtemp(prefix="peakform_")
    path = os.path.join(st.session_state.tmp_dir, f"upload{suffix}")
    with open(path, "wb") as f:
        f.write(upload.getvalue())
    return path


def _api_key() -> str:
    # Read from environment (set via Cloud Run env var / GitHub Secret)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    try:
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return ""


def _init_agent(result) -> None:
    """(Re-)initialise the PeakFormAgent if an API key is available."""
    key = _api_key()
    if key:
        try:
            from peakform.chat import PeakFormAgent
            st.session_state.agent = PeakFormAgent(
                report_md=result.report_md,
                mf_data=result.mf_data,
                garmin_data=result.garmin_data,
                week_start=result.week_start,
                week_end=result.week_end,
                api_key=key,
            )
        except Exception:
            pass
    elif "agent" in st.session_state:
        del st.session_state["agent"]


# ─────────────────────────────────────────────────────────────────────────────
# Password gate
# ─────────────────────────────────────────────────────────────────────────────

def _check_password() -> None:
    if st.session_state.get("authenticated"):
        return

    # Centered login card
    st.markdown(
        """
<div style="
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; min-height:70vh; padding:2rem;
">
  <div style="
    background:linear-gradient(135deg,rgba(17,24,39,0.97) 0%,rgba(30,41,59,0.7) 100%);
    border:1px solid rgba(99,102,241,0.22);
    border-radius:20px;
    padding:2.8rem 2.4rem;
    width:100%;max-width:400px;
    box-shadow:0 20px 60px rgba(0,0,0,0.6),inset 0 1px 0 rgba(255,255,255,0.04);
    text-align:center;
  ">
    <div style="font-size:3rem;margin-bottom:0.6rem;
      filter:drop-shadow(0 0 20px rgba(129,140,248,0.7))">🏔️</div>
    <div style="
      background:linear-gradient(135deg,#818cf8 0%,#c084fc 100%);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      background-clip:text;
      font-size:2rem;font-weight:900;letter-spacing:-0.04em;margin-bottom:0.3rem;
    ">PeakForm</div>
    <div style="color:rgba(148,163,184,0.6);font-size:0.85rem;margin-bottom:2rem;
      text-transform:uppercase;letter-spacing:0.08em;font-weight:500;">
      Fitness &amp; Nutrition Intelligence
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Actual inputs (can't put inside HTML div)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        pw = st.text_input("Password", type="password", key="_pw", label_visibility="collapsed",
                           placeholder="Enter password…")
        if st.button("Sign In", type="primary", use_container_width=True):
            expected = os.environ.get("APP_PASSWORD") or ""
            try:
                expected = expected or st.secrets.get("APP_PASSWORD", "")
            except Exception:
                pass
            if pw and pw == expected:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.", icon="🔒")
        st.caption("Only authorised users may access this app.")

    st.stop()


_check_password()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:

    # ── Logo ────────────────────────────────────────────────────────────────
    st.markdown(_html_logo(), unsafe_allow_html=True)

    # ── Data upload ──────────────────────────────────────────────────────────
    st.markdown(_html_section_label("Data Exports", "📂"), unsafe_allow_html=True)

    with st.expander("Upload files", expanded=not bool(st.session_state.get("result"))):
        mf_upload = st.file_uploader(
            "MacroFactor Export (.xlsx)",
            type=["xlsx"],
            help="MacroFactor → Profile → Export Data → Download XLSX",
            label_visibility="collapsed",
        )
        st.caption("MacroFactor XLSX export")

        garmin_upload = st.file_uploader(
            "Garmin Activities (.csv)",
            type=["csv"],
            help="Garmin Connect → Activities → Export to CSV",
            label_visibility="collapsed",
        )
        st.caption("Garmin Connect CSV export")

        week_input = st.text_input(
            "Analysis week",
            placeholder="YYYY-MM-DD  (blank = this week)",
            help="Any date within the Mon–Sun week you want to analyse.",
            label_visibility="collapsed",
        )
        st.caption("Week to analyse  ·  leave blank for this week")

    can_run = bool(mf_upload and garmin_upload)
    run_btn = st.button(
        "▶  Run Analysis",
        type="primary",
        disabled=not can_run,
        use_container_width=True,
    )

    # ── Footer ───────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="color:rgba(100,116,139,0.4);font-size:0.68rem;text-align:center;padding:1rem 0 0.5rem;">'
        'v0.3 · <a href="https://github.com/bhackerb/peakform" '
        'style="color:rgba(129,140,248,0.5);text-decoration:none;">GitHub</a>'
        "</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Run analysis
# ─────────────────────────────────────────────────────────────────────────────

if run_btn and can_run:
    mf_path = _save_upload(mf_upload, ".xlsx")
    garmin_path = _save_upload(garmin_upload, ".csv")

    with st.spinner("Analysing your data…"):
        try:
            from peakform.agent import run_full

            result = run_full(
                mf_path,
                garmin_path,
                week=week_input.strip() or None,
                verbose=False,
            )
            st.session_state.result = result
            st.session_state.messages = []
            _init_agent(result)

        except Exception as exc:
            st.error(f"Analysis failed: {exc}", icon="🚨")


# ─────────────────────────────────────────────────────────────────────────────
# Landing screen
# ─────────────────────────────────────────────────────────────────────────────

if "result" not in st.session_state:

    # Hero
    st.markdown(
        """
<div style="text-align:center;padding:3.5rem 1rem 2.5rem;">
  <div style="font-size:4rem;margin-bottom:0.5rem;
    filter:drop-shadow(0 0 30px rgba(129,140,248,0.7))">🏔️</div>
  <div style="
    background:linear-gradient(135deg,#a5b4fc 0%,#c084fc 50%,#818cf8 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;
    font-size:3.2rem;font-weight:900;letter-spacing:-0.04em;
    line-height:1.05;margin-bottom:0.8rem;
  ">PeakForm</div>
  <div style="
    color:rgba(148,163,184,0.65);font-size:1.05rem;
    font-weight:400;max-width:500px;margin:0 auto 0.8rem;
    line-height:1.6;
  ">Weekly fitness &amp; nutrition intelligence, powered by your own data.</div>
  <div style="
    display:inline-block;
    background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);
    border-radius:20px;padding:0.35rem 1rem;
    color:#818cf8;font-size:0.78rem;font-weight:600;
    text-transform:uppercase;letter-spacing:0.08em;
  ">← Upload data in the sidebar to get started</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Feature cards
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown(
            _html_feature_card(
                "📊",
                "Weekly Report",
                "Running, strength, nutrition, body composition — all in one intelligent summary with flags and recommendations.",
                "#6366f1",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _html_feature_card(
                "🤖",
                "AI Coach",
                "Ask anything about your numbers. The coach has your full data as context and is always available in the sidebar.",
                "#8b5cf6",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _html_feature_card(
                "📈",
                "Interactive Charts",
                "Weight trend, weekly mileage, calorie balance, protein adherence, pace trend, strength volume — all live.",
                "#06b6d4",
            ),
            unsafe_allow_html=True,
        )

    # Instruction strip
    st.markdown(
        """
<div style="
  display:flex;align-items:center;gap:1rem;
  background:rgba(13,21,40,0.5);
  border:1px solid rgba(99,102,241,0.12);
  border-radius:12px;padding:1rem 1.5rem;
  margin-top:1.8rem;
">
  <span style="font-size:1.4rem">💡</span>
  <div style="color:rgba(148,163,184,0.7);font-size:0.85rem;line-height:1.5;">
    <strong style="color:#a5b4fc;">How it works:</strong>
    Export your <strong style="color:#e2e8f0;">MacroFactor XLSX</strong> and
    <strong style="color:#e2e8f0;">Garmin CSV</strong>, upload them in the sidebar,
    click <strong style="color:#818cf8;">▶ Run Analysis</strong>, and your full
    weekly intelligence report will appear — along with interactive charts and
    an AI coach ready to answer your questions.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Main content — three top-level tabs
# ─────────────────────────────────────────────────────────────────────────────

result = st.session_state.result

if "agent" not in st.session_state and _api_key():
    _init_agent(result)

week_label = (
    result.week_start.strftime("%b %d")
    + " – "
    + result.week_end.strftime("%b %d, %Y")
)

st.markdown(_html_week_banner(week_label), unsafe_allow_html=True)

tab_report, tab_charts, tab_smart = st.tabs(
    ["📊  Weekly Report", "📈  Charts", "🎯  Smart Plan"]
)


# ── Reusable chat panel (used in Report + Charts tabs) ───────────────────────
def _render_chat_panel() -> None:
    st.markdown(
        """
<div style="
  background:linear-gradient(180deg,rgba(12,17,32,0.95) 0%,rgba(13,21,40,0.98) 100%);
  border:1px solid rgba(99,102,241,0.2);border-radius:16px;
  padding:1rem 1rem 0.75rem;margin-top:0.1rem;
">
  <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
    <span style="font-size:1.1rem;filter:drop-shadow(0 0 6px rgba(129,140,248,0.6))">🤖</span>
    <span style="
      background:linear-gradient(135deg,#818cf8,#c084fc);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      background-clip:text;font-weight:700;font-size:0.95rem;
    ">AI Coach</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    if "agent" not in st.session_state:
        st.markdown(
            '<div style="color:rgba(100,116,139,0.6);font-size:0.8rem;'
            'text-align:center;padding:1.5rem 0.5rem;">'
            "Run an analysis to<br>activate the AI Coach."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        _html_chat_history(st.session_state.get("messages", [])),
        unsafe_allow_html=True,
    )
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "message",
            placeholder="Ask about your data…",
            label_visibility="collapsed",
        )
        send = st.form_submit_button("Send →", use_container_width=True)

    if send and user_input.strip():
        msgs = st.session_state.setdefault("messages", [])
        msgs.append({"role": "user", "content": user_input.strip()})
        with st.spinner(""):
            try:
                reply = st.session_state.agent.chat(user_input.strip())
            except Exception as exc:
                reply = f"⚠️ Error: {exc}"
        msgs.append({"role": "assistant", "content": reply})
        st.rerun()

    if st.session_state.get("messages"):
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.agent.reset()
            st.rerun()


# ── Report tab ────────────────────────────────────────────────────────────────
with tab_report:
    col_r, col_c = st.columns([3, 1], gap="large")
    with col_r:
        st.markdown(result.report_md)
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        st.download_button(
            label="⬇️  Download report (.md)",
            data=result.report_md,
            file_name=f"peakform_report_{result.week_start.strftime('%Y-%m-%d')}.md",
            mime="text/markdown",
        )
    with col_c:
        _render_chat_panel()


# ── Charts tab ────────────────────────────────────────────────────────────────
with tab_charts:
    from peakform.charts import (
        adherence_scorecard,
        calories_vs_target_chart,
        muscle_group_chart,
        pace_trend_chart,
        protein_adherence_chart,
        weekly_deficit_chart,
        weekly_mileage_chart,
        weight_trend_chart,
    )

    mf = result.mf_data
    gd = result.garmin_data
    w_start = result.week_start
    w_end = result.week_end
    _PC = dict(use_container_width=True, config={"displayModeBar": False})

    col_ch, col_cc = st.columns([3, 1], gap="large")
    with col_ch:
        st.markdown(
            _html_section_header("Plan Adherence", "How closely did this week match the targets?"),
            unsafe_allow_html=True,
        )
        try:
            adh_fig, _ = adherence_scorecard(mf, gd, w_start, w_end)
            st.plotly_chart(adh_fig, **_PC)
        except Exception as e:
            st.warning(f"Adherence scorecard unavailable: {e}")

        st.divider()

        st.markdown(
            _html_section_header("Weight & Mileage", "Body weight trend toward goal · weekly running distance"),
            unsafe_allow_html=True,
        )
        col_w, col_m = st.columns(2, gap="medium")
        with col_w:
            try:
                st.plotly_chart(weight_trend_chart(mf), **_PC)
            except Exception as e:
                st.warning(f"Weight chart unavailable: {e}")
        with col_m:
            try:
                st.plotly_chart(weekly_mileage_chart(gd), **_PC)
            except Exception as e:
                st.warning(f"Mileage chart unavailable: {e}")

        st.divider()

        st.markdown(
            _html_section_header("Nutrition", "Daily calorie & protein tracking vs. active targets"),
            unsafe_allow_html=True,
        )
        col_cal, col_prot = st.columns(2, gap="medium")
        with col_cal:
            try:
                st.plotly_chart(calories_vs_target_chart(mf), **_PC)
            except Exception as e:
                st.warning(f"Calories chart unavailable: {e}")
        with col_prot:
            try:
                st.plotly_chart(protein_adherence_chart(mf), **_PC)
            except Exception as e:
                st.warning(f"Protein chart unavailable: {e}")

        try:
            st.plotly_chart(weekly_deficit_chart(mf), **_PC)
        except Exception as e:
            st.warning(f"Deficit chart unavailable: {e}")

        st.divider()

        st.markdown(
            _html_section_header("Running & Strength", "Flat-run pace trend · sets by muscle group this week"),
            unsafe_allow_html=True,
        )
        col_pace, col_mg = st.columns(2, gap="medium")
        with col_pace:
            try:
                st.plotly_chart(pace_trend_chart(gd), **_PC)
            except Exception as e:
                st.warning(f"Pace chart unavailable: {e}")
        with col_mg:
            try:
                st.plotly_chart(muscle_group_chart(mf, w_start, w_end), **_PC)
            except Exception as e:
                st.warning(f"Muscle group chart unavailable: {e}")

    with col_cc:
        _render_chat_panel()


# ── Smart Plan tab ────────────────────────────────────────────────────────────
with tab_smart:
    from peakform.recommendations import InterviewState, run_analysis, run_proposal, run_template

    # ── Phase progress indicator ─────────────────────────────────────────────
    _PHASES = ["Interview", "Analysis", "Proposal", "Weekly Plan"]

    def _phase_bar(current: int) -> str:
        items = []
        for i, label in enumerate(_PHASES, start=1):
            if i < current:
                color, weight = "#10b981", "600"
                dot = "✓"
            elif i == current:
                color, weight = "#818cf8", "700"
                dot = str(i)
            else:
                color, weight = "#334155", "400"
                dot = str(i)
            items.append(
                f'<div style="display:flex;align-items:center;gap:0.4rem;">'
                f'<div style="width:26px;height:26px;border-radius:50%;background:{color};'
                f'display:flex;align-items:center;justify-content:center;'
                f'font-size:0.75rem;font-weight:{weight};color:#fff;">{dot}</div>'
                f'<span style="font-size:0.82rem;font-weight:{weight};color:{color};">{label}</span>'
                f'</div>'
            )
        connectors = f'<div style="flex:1;height:2px;background:rgba(129,140,248,0.15);margin:0 0.3rem;"></div>'
        inner = connectors.join(items)
        return (
            f'<div style="display:flex;align-items:center;gap:0.2rem;'
            f'background:rgba(8,12,20,0.7);border:1px solid rgba(99,102,241,0.15);'
            f'border-radius:12px;padding:0.75rem 1.25rem;margin-bottom:1.5rem;">'
            f'{inner}</div>'
        )

    # ── State bootstrap ──────────────────────────────────────────────────────
    if "rec" not in st.session_state:
        st.session_state.rec = InterviewState(phase=0)

    rec: InterviewState = st.session_state.rec

    # ── Phase 0 — Landing ────────────────────────────────────────────────────
    if rec.phase == 0:
        st.markdown(
            """
<div style="text-align:center;padding:2rem 1rem 1.5rem;">
  <div style="font-size:3rem;margin-bottom:0.5rem;
    filter:drop-shadow(0 0 20px rgba(129,140,248,0.6))">🎯</div>
  <div style="
    background:linear-gradient(135deg,#a5b4fc 0%,#c084fc 50%,#818cf8 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;font-size:2rem;font-weight:800;letter-spacing:-0.03em;
    margin-bottom:0.5rem;">Smart Weekly Plan</div>
  <div style="color:rgba(148,163,184,0.7);font-size:1rem;max-width:520px;
    margin:0 auto;line-height:1.6;">
    A 4-phase AI coaching session that synthesises your Garmin performance,
    MacroFactor nutrition strategy, and subjective biofeedback into a
    personalised, downloadable weekly plan.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4, gap="small")
        _phase_cards = [
            ("1", "🎙️", "Performance Interview", "Sleep, RPE, hunger, mesocycle context, and your new MacroFactor targets."),
            ("2", "🔬", "AI Analysis", "Garmin trends + nutrition + biofeedback synthesised into a performance-first assessment."),
            ("3", "📋", "Strategy Proposal", "Nutrition pivot, intensity verdict, and day-by-day training schedule for your approval."),
            ("4", "📥", "Weekly Plan", "Finalised 7-day meal + training template, macro-verified and ready to download."),
        ]
        for col, (num, icon, title, desc) in zip([c1, c2, c3, c4], _phase_cards):
            with col:
                st.markdown(
                    f"""
<div style="
  background:linear-gradient(135deg,rgba(17,24,39,0.95),rgba(30,41,59,0.5));
  border:1px solid rgba(99,102,241,0.18);border-radius:14px;
  padding:1.2rem;height:100%;text-align:center;
">
  <div style="font-size:1.8rem;margin-bottom:0.5rem;">{icon}</div>
  <div style="font-size:0.7rem;font-weight:700;color:rgba(129,140,248,0.6);
    text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem;">Phase {num}</div>
  <div style="font-size:0.9rem;font-weight:700;color:#e2e8f0;margin-bottom:0.4rem;">{title}</div>
  <div style="font-size:0.8rem;color:rgba(148,163,184,0.65);line-height:1.5;">{desc}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            if st.button("▶  Start Performance Interview", type="primary", use_container_width=True):
                st.session_state.rec = InterviewState(phase=1)
                st.rerun()

    # ── Phase 1 — Interview form ─────────────────────────────────────────────
    elif rec.phase == 1:
        st.markdown(_phase_bar(1), unsafe_allow_html=True)
        st.markdown(
            _html_section_header(
                "Performance Interview",
                "Tell the coach how last week felt — be honest, not optimistic.",
            ),
            unsafe_allow_html=True,
        )

        with st.form("interview_form"):
            # ── Biofeedback ──────────────────────────────────────────────────
            st.markdown("**Subjective Biofeedback**")
            col_s, col_h, col_r = st.columns(3, gap="medium")
            with col_s:
                sleep = st.slider("Sleep Quality", 1, 10, rec.sleep_score,
                                  help="1 = terrible, 10 = perfect")
            with col_h:
                hunger = st.slider("Hunger Level", 1, 10, rec.hunger_score,
                                   help="1 = never hungry, 10 = ravenous all day")
            with col_r:
                rpe = st.slider("Overall Weekly RPE", 1, 10, rec.rpe_score,
                                help="1 = very easy week, 10 = maximal effort")

            notes = st.text_area(
                "Additional notes (soreness, mood, stress, notable events…)",
                value=rec.biofeedback_notes,
                height=80,
                placeholder="e.g. Left knee a bit sore after Thursday run. Work was stressful.",
            )

            st.divider()

            # ── Mesocycle context ────────────────────────────────────────────
            st.markdown("**Training Context**")
            col_mw, col_ml, col_mt = st.columns([1, 1, 2], gap="medium")
            with col_mw:
                meso_week = st.number_input("Mesocycle week #", 1, 20, rec.mesocycle_week)
            with col_ml:
                meso_len = st.selectbox("Cycle length", [4, 8, 12, 16],
                                        index=[4, 8, 12, 16].index(rec.mesocycle_length))
            with col_mt:
                meso_type = st.selectbox(
                    "Cycle type",
                    ["Base Build", "Strength Block", "Peak", "Taper", "Maintenance"],
                    index=["Base Build", "Strength Block", "Peak", "Taper", "Maintenance"].index(
                        rec.mesocycle_type
                    ),
                )

            st.divider()

            # ── New MacroFactor targets ──────────────────────────────────────
            st.markdown(
                "**New MacroFactor Targets** — run a Strategy Check-In in the app first, then enter the new numbers:"
            )
            col_cal, col_p, col_c2, col_f = st.columns(4, gap="medium")
            with col_cal:
                new_cals = st.number_input("Calories (kcal)", 800, 4000,
                                           int(rec.new_calories) or 1400, step=10)
            with col_p:
                new_prot = st.number_input("Protein (g)", 50, 400,
                                           int(rec.new_protein_g) or 150, step=1)
            with col_c2:
                new_carbs = st.number_input("Carbs (g)", 20, 600,
                                            int(rec.new_carbs_g) or 90, step=1)
            with col_f:
                new_fat = st.number_input("Fat (g)", 10, 200,
                                          int(rec.new_fat_g) or 45, step=1)

            st.divider()

            # ── Previous week's plan ─────────────────────────────────────────
            prev_plan = st.text_area(
                "Previous week's plan (optional — paste from Google Doc or elsewhere)",
                value=rec.prev_plan_text,
                height=160,
                placeholder="Paste your previous week's meal + training plan here for the AI to reference...",
            )

            submitted = st.form_submit_button(
                "Submit & Run Analysis →", type="primary", use_container_width=True
            )

        if submitted:
            if not _api_key():
                st.error("No Anthropic API key found. Set ANTHROPIC_API_KEY in your GitHub Secrets.", icon="🔒")
            else:
                rec.sleep_score = sleep
                rec.hunger_score = hunger
                rec.rpe_score = rpe
                rec.biofeedback_notes = notes
                rec.mesocycle_week = int(meso_week)
                rec.mesocycle_length = int(meso_len)
                rec.mesocycle_type = meso_type
                rec.new_calories = float(new_cals)
                rec.new_protein_g = float(new_prot)
                rec.new_carbs_g = float(new_carbs)
                rec.new_fat_g = float(new_fat)
                rec.prev_plan_text = prev_plan

                with st.spinner("Synthesising Garmin + MacroFactor + biofeedback…"):
                    try:
                        rec.analysis_text = run_analysis(
                            rec,
                            result.mf_data,
                            result.garmin_data,
                            result.week_start,
                            result.week_end,
                            _api_key(),
                        )
                        rec.phase = 2
                    except Exception as exc:
                        st.error(f"Analysis failed: {exc}", icon="🚨")
                st.rerun()

    # ── Phase 2 — Performance-First Analysis ─────────────────────────────────
    elif rec.phase == 2:
        st.markdown(_phase_bar(2), unsafe_allow_html=True)
        st.markdown(
            _html_section_header(
                "Performance-First Analysis",
                "AI synthesis of your Garmin data, nutrition, and biofeedback.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(rec.analysis_text)
        st.divider()

        col_fwd, col_bk = st.columns([3, 1], gap="medium")
        with col_fwd:
            if st.button("Generate Strategy Proposal →", type="primary", use_container_width=True):
                with st.spinner("Drafting strategy proposal…"):
                    try:
                        rec.proposal_text = run_proposal(rec, _api_key())
                        rec.phase = 3
                    except Exception as exc:
                        st.error(f"Proposal failed: {exc}", icon="🚨")
                st.rerun()
        with col_bk:
            if st.button("← Edit Interview", use_container_width=True):
                rec.phase = 1
                st.rerun()

    # ── Phase 3 — Strategy Proposal ──────────────────────────────────────────
    elif rec.phase == 3:
        st.markdown(_phase_bar(3), unsafe_allow_html=True)
        st.markdown(
            _html_section_header(
                "Strategy Proposal",
                "Review and approve the plan before the weekly template is generated.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(rec.proposal_text)
        st.divider()

        use_new = st.checkbox(
            "Suggest new meal options (beyond the standard rotation)",
            value=rec.use_new_meals,
        )
        rec.use_new_meals = use_new

        col_app, col_rev, col_rst = st.columns([3, 2, 1], gap="medium")
        with col_app:
            if st.button("✅  Approve & Generate Weekly Plan", type="primary", use_container_width=True):
                with st.spinner("Building your personalised 7-day plan…"):
                    try:
                        rec.week_template_md = run_template(rec, _api_key())
                        rec.phase = 4
                    except Exception as exc:
                        st.error(f"Template generation failed: {exc}", icon="🚨")
                st.rerun()
        with col_rev:
            if st.button("← Revise Analysis", use_container_width=True):
                rec.phase = 1
                st.rerun()
        with col_rst:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.rec = InterviewState(phase=0)
                st.rerun()

    # ── Phase 4 — Weekly Plan ────────────────────────────────────────────────
    elif rec.phase == 4:
        st.markdown(_phase_bar(4), unsafe_allow_html=True)
        st.markdown(
            _html_section_header(
                "Your Weekly Plan",
                "Macro-verified · ready to execute.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(rec.week_template_md)

        st.divider()
        col_dl, col_rst2 = st.columns([3, 1], gap="medium")
        with col_dl:
            from datetime import date as _date
            filename = f"peakform_plan_{_date.today().strftime('%Y-%m-%d')}.md"
            st.download_button(
                label="⬇️  Download Weekly Plan (.md)",
                data=rec.week_template_md,
                file_name=filename,
                mime="text/markdown",
                use_container_width=True,
                type="primary",
            )
        with col_rst2:
            if st.button("🔄  New Week", use_container_width=True):
                st.session_state.rec = InterviewState(phase=0)
                st.rerun()
