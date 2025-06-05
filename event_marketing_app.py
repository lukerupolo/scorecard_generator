import streamlit as st
from datetime import datetime
import pandas as pd
from io import BytesIO

# ─ Sidebar: Overall Configuration ───────────────────────────────────────────
n_events = st.sidebar.number_input("Number of events", 1, 10, 1)
events: list[dict] = []
for i in range(n_events):
    st.sidebar.markdown(f"**Event {i+1} Details**")
    name = st.sidebar.text_input(f"Event Name {i+1}", key=f"name_{i}") or f"Event{i+1}"
    date = st.sidebar.date_input(f"Event Date {i+1}", key=f"date_{i}")
    brand_id = st.sidebar.text_input(f"LevelUp Brand ID (Event {i+1})", key=f"brand_{i}", value="3136")
    region = st.sidebar.text_input(f"LevelUp Region (Event {i+1})", key=f"region_{i}", value="TH")
    events.append({
        "name": name,
        "date": datetime.combine(date, datetime.min.time()),
        "brandId": brand_id,
        "region": region,
    })

metrics = st.sidebar.multiselect(
    "Select metrics:",
    [
        "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions",
        "Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Search Index", "PCCV", "AMA"
    ],
    default=[],
)

# Reset login decisions if metrics change
if "Social Mentions" not in metrics:
    for k in [
        "onclusive_decision",
        "manual_social_toggle",
        "onclusive_user",
        "onclusive_pw",
        "onclusive_query",
    ]:
        st.session_state.pop(k, None)

if not any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    for k in ["levelup_decision", "manual_levelup_toggle", "levelup_jwt"]:
        st.session_state.pop(k, None)

# ─ Blocking login modals ────────────────────────────────────────────────────
if "Social Mentions" in metrics and not st.session_state.get("onclusive_decision"):
    with st.modal("Onclusive Login Required", key="onclusive_block"):
        st.markdown(
            "<div style='border:2px solid #999; background:#f8f8f8; padding:20px; text-align:center;'>",
            unsafe_allow_html=True,
        )
        st.write("Please log in to Onclusive or skip to manual entry.")
        o_user = st.text_input("Onclusive Username", key="modal_onclusive_user")
        o_pw = st.text_input("Onclusive Password", type="password", key="modal_onclusive_pw")
        o_query = st.text_input("Search Keywords", key="modal_onclusive_query")
        col1, col2 = st.columns(2)
        if col1.button("Log In", key="onclusive_login_btn"):
            st.session_state["onclusive_user"] = o_user
            st.session_state["onclusive_pw"] = o_pw
            st.session_state["onclusive_query"] = o_query
            st.session_state["manual_social_toggle"] = False
            st.session_state["onclusive_decision"] = True
            st.experimental_rerun()
        if col2.button("Skip (Manual)", key="onclusive_skip_btn"):
            st.session_state["manual_social_toggle"] = True
            st.session_state["onclusive_decision"] = True
            st.experimental_rerun()
        st.markdown("</div>", unsafe_allow_html=True)

if (
    any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics)
    and not st.session_state.get("levelup_decision")
):
    with st.modal("LevelUp Login Required", key="levelup_block"):
        st.markdown(
            "<div style='border:2px solid #999; background:#f8f8f8; padding:20px; text-align:center;'>",
            unsafe_allow_html=True,
        )
        st.write("Video metrics selected. Sign in with LevelUp or skip to manual entry.")
        col1, col2 = st.columns(2)
        if col1.button("Login with Google", key="levelup_login_btn"):
            jwt = get_levelup_jwt()
            if jwt:
                st.session_state["levelup_jwt"] = jwt
                st.session_state["manual_levelup_toggle"] = False
                st.session_state["levelup_decision"] = True
                st.experimental_rerun()
        if col2.button("Skip (Manual)", key="levelup_skip_btn"):
            st.session_state["manual_levelup_toggle"] = True
            st.session_state["levelup_decision"] = True
            st.experimental_rerun()
        st.markdown("</div>", unsafe_allow_html=True)

regions = st.sidebar.multiselect(
    "Output Regions (sheet tabs):",
    ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"],
    default=[],
)

# ─ Main: Conditional Login or Manual Inputs Based on Metrics ─────────────────

# 1) Initialize variables for Onclusive (Digimind)
onclusive_username = st.session_state.get("onclusive_user")
onclusive_password = st.session_state.get("onclusive_pw")
onclusive_language = st.session_state.get("onclusive_lang", "en")
onclusive_query = st.session_state.get("onclusive_query")
manual_social_inputs: dict[int, tuple[int, int]] = {}

if "Social Mentions" in metrics:
    st.subheader("🔐 Onclusive (Digimind) for Social Mentions")
    use_manual_social = st.checkbox(
        "❔ Enter Social Mentions counts manually (skip Onclusive)",
        key="manual_social_toggle",
        value=st.session_state.get("manual_social_toggle", False),
    )
    if use_manual_social:
        st.info("Provide baseline & actual Social Mentions per event.")
        for idx, ev in enumerate(events):
            baseline_input = st.number_input(
                f"Event {idx+1} ({ev['name']}): Baseline Social Mentions",
                min_value=0, step=1, key=f"social_baseline_{idx}"
            )
            actual_input = st.number_input(
                f"Event {idx+1} ({ev['name']}): Actual Social Mentions",
                min_value=0, step=1, key=f"social_actual_{idx}"
            )
            manual_social_inputs[idx] = (baseline_input, actual_input)
    else:
        onclusive_username = st.text_input("Onclusive Username", placeholder="you@example.com", key="onclusive_user")
        onclusive_password = st.text_input("Onclusive Password", type="password", key="onclusive_pw")
        onclusive_language = st.text_input("Language", value="en", key="onclusive_lang")
        onclusive_query = st.text_input("Search Keywords", placeholder="e.g. FIFA, EA Sports", key="onclusive_query")

        # Quick test for Onclusive credentials (optional)
        if onclusive_username and onclusive_password and onclusive_query:
            st.write("🔍 Testing Onclusive credentials…")
            test_count = fetch_social_mentions_count(
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                onclusive_username,
                onclusive_password,
                onclusive_language,
                "test"
            )
            if test_count is not None:
                st.success("✅ Onclusive login OK")
            else:
                st.error("❌ Onclusive login failed")


# 2) Initialize variables for LevelUp (Google SSO)
levelup_jwt = st.session_state.get("levelup_jwt")
manual_levelup_inputs: dict[int, dict[str, tuple[int, int]]] = {}

if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.subheader("🎮 LevelUp (Google SSO) for Video Views & Hours Watched")
    use_manual_levelup = st.checkbox(
        "❔ Enter LevelUp metrics manually (skip Google SSO)",
        key="manual_levelup_toggle",
        value=st.session_state.get("manual_levelup_toggle", False),
    )
    if use_manual_levelup:
        st.info("Provide baseline & actual values for LevelUp metrics per event.")
        for idx, ev in enumerate(events):
            manual_levelup_inputs[idx] = {}
            if "Video Views (VOD)" in metrics:
                vv_baseline = st.number_input(
                    f"Event {idx+1} ({ev['name']}): Baseline Video Views (VOD)",
                    min_value=0, step=1, key=f"levelup_vv_baseline_{idx}"
                )
                vv_actual = st.number_input(
                    f"Event {idx+1} ({ev['name']}): Actual Video Views (VOD)",
                    min_value=0, step=1, key=f"levelup_vv_actual_{idx}"
                )
                manual_levelup_inputs[idx]["Video Views (VOD)"] = (vv_baseline, vv_actual)

            if "Hours Watched (Streams)" in metrics:
                hw_baseline = st.number_input(
                    f"Event {idx+1} ({ev['name']}): Baseline Hours Watched (Streams)",
                    min_value=0, step=1, key=f"levelup_hw_baseline_{idx}"
                )
                hw_actual = st.number_input(
                    f"Event {idx+1} ({ev['name']}): Actual Hours Watched (Streams)",
                    min_value=0, step=1, key=f"levelup_hw_actual_{idx}"
                )
                manual_levelup_inputs[idx]["Hours Watched (Streams)"] = (hw_baseline, hw_actual)
    else:
        st.markdown(
            """
Press “Generate template” below → you will see a Device-Code prompt  
(“visit https://microsoft.com/devicelogin and enter code…”)  
Complete Google SSO, then the app will fetch Video Views & Hours Watched.
"""
        )

# ─ Generate & Download Template ───────────────────────────────────────────────
if st.button("Generate Template"):
    # 1) Validate Onclusive inputs if needed
    if "Social Mentions" in metrics and not manual_social_inputs:
        if not (onclusive_username and onclusive_password and onclusive_query):
            st.warning("Enter Onclusive credentials or choose manual input for Social Mentions.")
            st.stop()

    # 2) Acquire LevelUp JWT via Device-Code Flow if needed
    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics) and not manual_levelup_inputs:
        if not levelup_jwt:
            levelup_jwt = get_levelup_jwt()
            if not levelup_jwt:
                st.stop()

    # 3) Build Excel sheets
    with st.spinner("Building Excel…"):
        sheets = generate_event_tables(
            events,
            metrics,
            regions,
            # Onclusive API inputs (None if manual)
            onclusive_username,
            onclusive_password,
            onclusive_language,
            onclusive_query,
            manual_social_inputs,
            # LevelUp inputs
            levelup_jwt,
            manual_levelup_inputs,
        )
        if not sheets:
            st.stop()

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                safe_name = sheet_name[:31]  # Excel sheet name limit
                df.to_excel(writer, sheet_name=safe_name, index=False)

        buffer.seek(0)
        st.download_button(
            label="Download Report",
            data=buffer,
            file_name="event_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
