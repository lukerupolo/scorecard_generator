import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

# ────────────────────────────────────────────────────────────────────────────────
# 1) Helper functions (same as before; omitted here for brevity)
# ────────────────────────────────────────────────────────────────────────────────

def setup_levelup_headers(api_key: str) -> dict:
    return {
        "accept": "application/json",
        "X-API-KEY": api_key
    }

def fetch_levelup_data(api_headers, brand_id, start_date, end_date, region_code, data_type):
    # … (unchanged) …
    pass

def generate_levelup_metrics_for_event(event, api_headers):
    # … (unchanged) …
    pass

def compute_three_month_average(api_headers, brand_id, region, event_date, data_type):
    # … (unchanged) …
    pass

# ────────────────────────────────────────────────────────────────────────────────
# 2) Streamlit page configuration
# ────────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# ────────────────────────────────────────────────────────────────────────────────
# 3) Sidebar: Select events (always visible)
# ────────────────────────────────────────────────────────────────────────────────

SINGLE_BRAND_ID = 3136
SINGLE_BRAND_NAME = "EA Sports FC 25"

st.sidebar.header("Event Configuration")
n_events = st.sidebar.number_input("Number of events", min_value=1, max_value=10, value=1, step=1)
events = []
for i in range(n_events):
    st.sidebar.markdown(f"**Event {i+1} Details**")
    name = st.sidebar.text_input(f"Event Name {i+1}", key=f"name_{i}") or f"Event{i+1}"
    date = st.sidebar.date_input(f"Event Date {i+1}", key=f"date_{i}")
    _ = st.sidebar.selectbox(f"Brand (Event {i+1})", options=[SINGLE_BRAND_NAME], key=f"brand_select_{i}")
    region = st.sidebar.text_input(f"Region (Event {i+1})", key=f"region_{i}", value="TH")
    events.append({
        "name": name,
        "date": datetime.combine(date, datetime.min.time()),
        "brandId": SINGLE_BRAND_ID,
        "region": region
    })

# ────────────────────────────────────────────────────────────────────────────────
# 4) Sidebar: Metric selection (always visible)
# ────────────────────────────────────────────────────────────────────────────────

metrics = st.sidebar.multiselect(
    "Select metrics to include:",
    [
        "Video Views (VOD)",
        "Hours Watched (Streams)",
        "Social Mentions",
        "Sessions",
        "DAU",
        "Revenue",
        "Installs",
        "Retention",
        "Watch Time",
        "ARPU",
        "Conversions",
        "Search Index",
        "PCCV",
        "AMA"
    ],
    default=[]
)

# Clear any saved Onclusive state if Social Mentions is now deselected
if "Social Mentions" not in metrics:
    for k in ["manual_social_toggle", "onclusive_user", "onclusive_pw", "onclusive_query"]:
        st.session_state.pop(k, None)

# Clear any saved manual LevelUp state if no Video/Streams metrics are selected
if not any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.session_state.pop("manual_levelup_toggle", None)

# ────────────────────────────────────────────────────────────────────────────────
# 5) Sidebar: Onclusive (Social Mentions) credentials (only if needed)
# ────────────────────────────────────────────────────────────────────────────────

onclusive_username = None
onclusive_password = None
onclusive_language = "en"
onclusive_query = None
manual_social_inputs = {}

if "Social Mentions" in metrics:
    st.sidebar.subheader("🔐 Onclusive Authentication")
    use_manual_social = st.sidebar.checkbox(
        "❔ Enter Social Mentions counts manually (skip Onclusive)",
        key="manual_social_toggle",
        value=st.session_state.get("manual_social_toggle", False)
    )
    if use_manual_social:
        for idx, ev in enumerate(events):
            base_sm = st.sidebar.number_input(
                f"Event {idx+1} ({ev['name']}): Baseline Social Mentions",
                min_value=0, step=1, key=f"social_baseline_{idx}"
            )
            act_sm = st.sidebar.number_input(
                f"Event {idx+1} ({ev['name']}): Actual Social Mentions",
                min_value=0, step=1, key=f"social_actual_{idx}"
            )
            manual_social_inputs[idx] = (base_sm, act_sm)
    else:
        onclusive_username = st.sidebar.text_input("Onclusive Username", placeholder="you@example.com", key="onclusive_user")
        onclusive_password = st.sidebar.text_input("Onclusive Password", type="password", key="onclusive_pw")
        onclusive_language = st.sidebar.text_input("Language", value="en", key="onclusive_lang")
        onclusive_query = st.sidebar.text_input("Search Keywords", placeholder="e.g. FIFA, EA Sports", key="onclusive_query")
        if onclusive_username and onclusive_password and onclusive_query:
            st.sidebar.write("🔍 Testing Onclusive credentials…")
            test_count = fetch_social_mentions_count(
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                onclusive_username,
                onclusive_password,
                onclusive_language,
                onclusive_query
            )
            if test_count is not None:
                st.sidebar.success("✅ Onclusive login OK")
            else:
                st.sidebar.error("❌ Onclusive login failed")

# ────────────────────────────────────────────────────────────────────────────────
# 6) Sidebar: LevelUp API key & manual inputs (only if Video/Streams selected)
# ────────────────────────────────────────────────────────────────────────────────

levelup_api_key = None
api_headers = None
manual_levelup_inputs = {}

if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.sidebar.subheader("🔒 LevelUp Authentication")
    levelup_api_key = st.sidebar.text_input(
        "Paste your LevelUp API Key here",
        type="password",
        key="levelup_api_key"
    )

    use_manual_levelup = st.sidebar.checkbox(
        "❔ Enter LevelUp metrics manually (skip API)",
        key="manual_levelup_toggle",
        value=st.session_state.get("manual_levelup_toggle", False)
    )

    if use_manual_levelup:
        for idx, ev in enumerate(events):
            manual_levelup_inputs[idx] = {}
            if "Video Views (VOD)" in metrics:
                vv_base = st.sidebar.number_input(
                    f"Event {idx+1} ({ev['name']}): Baseline Video Views (VOD)",
                    min_value=0, step=1, key=f"levelup_vv_baseline_{idx}"
                )
                vv_act = st.sidebar.number_input(
                    f"Event {idx+1} ({ev['name']}): Actual Video Views (VOD)",
                    min_value=0, step=1, key=f"levelup_vv_actual_{idx}"
                )
                manual_levelup_inputs[idx]["Video Views (VOD)"] = (vv_base, vv_act)

            if "Hours Watched (Streams)" in metrics:
                hw_base = st.sidebar.number_input(
                    f"Event {idx+1} ({ev['name']}): Baseline Hours Watched (Streams)",
                    min_value=0, step=1, key=f"levelup_hw_baseline_{idx}"
                )
                hw_act = st.sidebar.number_input(
                    f"Event {idx+1} ({ev['name']}): Actual Hours Watched (Streams)",
                    min_value=0, step=1, key=f"levelup_hw_actual_{idx}"
                )
                manual_levelup_inputs[idx]["Hours Watched (Streams)"] = (hw_base, hw_act)

    else:
        if levelup_api_key:
            api_headers = setup_levelup_headers(levelup_api_key)
            st.sidebar.success("🗝️ LevelUp API Key set. Ready to fetch data.")
        else:
            st.sidebar.info("Enter LevelUp API Key to fetch Video/Streams metrics.")

# ────────────────────────────────────────────────────────────────────────────────
# 7) Sidebar: Output regions (always visible)
# ────────────────────────────────────────────────────────────────────────────────

regions = st.sidebar.multiselect(
    "Output Regions (sheet tabs):",
    ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"],
    default=[]
)

# ────────────────────────────────────────────────────────────────────────────────
# 8) Main: Generate Scorecard table(s)
# ────────────────────────────────────────────────────────────────────────────────

if st.button("Generate Scorecard"):
    # Ensure at least one metric is selected
    if not metrics:
        st.warning("Please select at least one metric before generating.")
        st.stop()

    # Check Onclusive if needed
    if "Social Mentions" in metrics and not manual_social_inputs:
        if not (onclusive_username and onclusive_password and onclusive_query):
            st.warning("Enter Onclusive credentials or choose manual entry for Social Mentions.")
            st.stop()

    # Check LevelUp if needed
    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
        if not manual_levelup_inputs and not levelup_api_key:
            st.warning("Provide a LevelUp API Key or choose manual entry for video metrics.")
            st.stop()
        if levelup_api_key:
            api_headers = setup_levelup_headers(levelup_api_key)

    # Build one table per event (omitting full code for brevity)
    # … (same logic as before, generating a DataFrame with "Baseline Method (3 months)") …

    # Example placeholder:
    for idx, ev in enumerate(events):
        st.markdown(f"### Event {idx+1}: {ev['name']} (Date: {ev['date'].date():%Y-%m-%d}, Region: {ev['region']})")
        st.write("… your metrics table appears here …")

    # Finally, offer Excel download:
    # buffer = BytesIO()
    # with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    #     … write each event’s table to its own sheet …
    # buffer.seek(0)
    # st.download_button(...)
