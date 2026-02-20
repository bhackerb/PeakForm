"""PeakForm — Streamlit web app.

Upload your MacroFactor XLSX and Garmin CSV exports, generate your weekly
report, and chat with the AI coach — all from a browser.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_upload(upload, suffix: str) -> str:
    """Write an uploaded file to a session-persistent temp dir and return path."""
    if "tmp_dir" not in st.session_state:
        st.session_state.tmp_dir = tempfile.mkdtemp(prefix="peakform_")
    path = os.path.join(st.session_state.tmp_dir, f"upload{suffix}")
    with open(path, "wb") as f:
        f.write(upload.getvalue())
    return path


def _api_key() -> str:
    """Return the Anthropic API key: sidebar input → st.secrets → empty string."""
    if st.session_state.get("_api_key_input"):
        return st.session_state["_api_key_input"]
    try:
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("# 🏔️ PeakForm")
    st.caption("Weekly Fitness & Nutrition Intelligence")
    st.divider()

    st.markdown("#### 📂 Data Exports")
    mf_upload = st.file_uploader(
        "MacroFactor Export",
        type=["xlsx"],
        help="MacroFactor → Profile → Export Data → Download XLSX",
    )
    garmin_upload = st.file_uploader(
        "Garmin Activities",
        type=["csv"],
        help="Garmin Connect → Activities → Export to CSV",
    )
    week_input = st.text_input(
        "Analysis week",
        placeholder="YYYY-MM-DD  (blank = this week)",
        help="Any date within the Mon–Sun week you want to analyse.",
    )

    can_run = bool(mf_upload and garmin_upload)
    run_btn = st.button(
        "▶  Run Analysis",
        type="primary",
        disabled=not can_run,
        use_container_width=True,
    )

    st.divider()

    st.markdown("#### 🔑 AI Coach")
    _default_key = ""
    try:
        _default_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass

    st.text_input(
        "Anthropic API Key",
        value=_default_key,
        type="password",
        placeholder="sk-ant-...   (required for chat)",
        help="Get a key at console.anthropic.com — stored only in your browser session.",
        key="_api_key_input",
    )

    st.divider()
    st.caption("v0.2 · [GitHub](https://github.com/bhackerb/PeakForm-C)")


# ---------------------------------------------------------------------------
# Run analysis
# ---------------------------------------------------------------------------

if run_btn and can_run:
    mf_path = _save_upload(mf_upload, ".xlsx")
    garmin_path = _save_upload(garmin_upload, ".csv")

    with st.spinner("⏳ Analysing your data…"):
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

            key = _api_key()
            if key:
                from peakform.chat import PeakFormAgent

                st.session_state.agent = PeakFormAgent(
                    report_md=result.report_md,
                    mf_data=result.mf_data,
                    garmin_data=result.garmin_data,
                    week_start=result.week_start,
                    week_end=result.week_end,
                    api_key=key,
                )
            elif "agent" in st.session_state:
                del st.session_state["agent"]

        except Exception as exc:
            st.error(f"❌ Analysis failed: {exc}", icon="🚨")


# ---------------------------------------------------------------------------
# Landing screen (no data loaded yet)
# ---------------------------------------------------------------------------

if "result" not in st.session_state:
    st.markdown("## Welcome to PeakForm 🏔️")
    st.markdown(
        "Upload your **MacroFactor** and **Garmin** exports in the sidebar, "
        "then click **▶ Run Analysis** to generate your weekly report."
    )
    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            "### 📊 Weekly Report\n"
            "Running, strength, nutrition, and body composition — "
            "all in one structured summary."
        )
    with c2:
        st.markdown(
            "### 💬 AI Coach\n"
            "Ask follow-up questions about your numbers. "
            "The agent has your full data as context."
        )
    with c3:
        st.markdown(
            "### 📈 Charts *(soon)*\n"
            "Visual trends for weight, mileage, macro adherence, "
            "and pace — inline with the report."
        )

    st.stop()


# ---------------------------------------------------------------------------
# Main content — Report + Chat tabs
# ---------------------------------------------------------------------------

result = st.session_state.result
week_label = result.week_start.strftime("%b %d") + " – " + result.week_end.strftime("%b %d, %Y")

st.markdown(f"## Week of {week_label}")

tab_report, tab_chat = st.tabs(["📊 Weekly Report", "💬 Ask PeakForm"])

# ── Report tab ──────────────────────────────────────────────────────────────
with tab_report:
    st.markdown(result.report_md)
    st.divider()
    st.download_button(
        label="⬇️  Download report (.md)",
        data=result.report_md,
        file_name=f"peakform_report_{result.week_start.strftime('%Y-%m-%d')}.md",
        mime="text/markdown",
    )

# ── Chat tab ────────────────────────────────────────────────────────────────
with tab_chat:
    if "agent" not in st.session_state:
        st.info(
            "Add your **Anthropic API Key** in the sidebar to enable the AI coach.  \n"
            "Get a free key at [console.anthropic.com](https://console.anthropic.com).",
            icon="🔑",
        )
    else:
        # Render history
        for msg in st.session_state.get("messages", []):
            avatar = "🏃" if msg["role"] == "user" else "🏔️"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

        # Chat input (always at bottom)
        if prompt := st.chat_input("Ask anything about your training data…"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar="🏃"):
                st.markdown(prompt)

            with st.chat_message("assistant", avatar="🏔️"):
                with st.spinner(""):
                    try:
                        reply = st.session_state.agent.chat(prompt)
                    except Exception as exc:
                        reply = f"⚠️ **Error:** {exc}"
                st.markdown(reply)

            st.session_state.messages.append({"role": "assistant", "content": reply})

        # Clear button (only shown when there is history)
        if st.session_state.get("messages"):
            if st.button("🗑️  Clear conversation"):
                st.session_state.messages = []
                st.session_state.agent.reset()
                st.rerun()
