import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

# ────────────────────────────────────────────────────────────────────────────────
# 1) Helper functions for LevelUp API integration
# ────────────────────────────────────────────────────────────────────────────────

def setup_levelup_headers(api_key: str) -> dict:
    """
    Constructs HTTP headers for LevelUp API requests using the provided API key.
    """
    return {
        "accept": "application/json",
        "X-API-KEY": api_key
    }

def fetch_levelup_data(
    api_headers: dict,
    brand_id: int,
    start_date: str,
    end_date: str,
    region_code: str,
    data_type: str
) -> pd.DataFrame | None:
    """
    Fetches time-series data ("videos" or "streams") from LevelUp for the given brand_id & region_code.
    Returns a DataFrame, or None on failure / empty payload.
    """
    api_url = f"https://www.levelup-analytics.com/api/client/v1/{data_type}/statsEvolution/brand/{brand_id}"
    params = {
        "from": start_date,
        "to": end_date,
        "brandid": brand_id,
        "region": region_code
    }

    response = requests.get(api_url, headers=api_headers, params=params)
    if response.status_code != 200:
        st.error(f"Error fetching {data_type} for brand {brand_id}, region {region_code}: {response.status_code}")
        return None

    payload = response.json().get("data", [])
    if not payload:
        return None

    df = pd.DataFrame(payload)
    df["brand_id"] = brand_id
    df["country_region_code"] = region_code

    # Convert columns to proper types if they exist:
    if data_type == "videos" and "views" in df.columns:
        df["views"] = df["views"].astype(int)
    elif data_type == "streams" and "watchTime" in df.columns:
        df["watchTime"] = df["watchTime"].astype(float)

    return df

def generate_levelup_metrics_for_event(event: dict, api_headers: dict) -> dict[str, pd.DataFrame]:
    """
    For a single event {name, date, brandId, region}, fetch:
      - Baseline (30 days before event) "videos" and "streams"
      - Actual   (30 days after event) "videos" and "streams"
    Returns a dict with possible keys "videos" and "streams" mapping to concatenated DataFrames.
    """
    event_date = event["date"].date()
    baseline_start = (event_date - timedelta(days=30)).strftime("%Y-%m-%d")
    baseline_end   = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
    actual_start   = event_date.strftime("%Y-%m-%d")
    actual_end     = (event_date + timedelta(days=30)).strftime("%Y-%m-%d")

    brand = int(event["brandId"])
    region = event["region"]

    metrics_dfs: dict[str, pd.DataFrame] = {}

    # Videos (VOD)
    vid_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "videos")
    vid_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "videos")
    if vid_df_baseline is not None and vid_df_actual is not None:
        vid_df_baseline["period"] = "baseline"
        vid_df_actual["period"]   = "actual"
        metrics_dfs["videos"] = pd.concat([vid_df_baseline, vid_df_actual], ignore_index=True)

    # Streams (Hours Watched)
    str_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "streams")
    str_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "streams")
    if str_df_baseline is not None and str_df_actual is not None:
        str_df_baseline["period"] = "baseline"
        str_df_actual["period"]   = "actual"
        metrics_dfs["streams"] = pd.concat([str_df_baseline, str_df_actual], ignore_index=True)

    return metrics_dfs

# ────────────────────────────────────────────────────────────────────────────────
# 2) The “master” Streamlit app
# ────────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# ───────── Sidebar: LevelUp API Key ──────────────────────────────────────────────
st.sidebar.subheader("🔒 LevelUp Authentication")
levelup_api_key = st.sidebar.text_input(
    "Paste your LevelUp API Key here",
    type="password",
    key="levelup_api_key"
)

if not levelup_api_key:
    st.sidebar.info("Enter your LevelUp API Key to proceed.")
    st.stop()

api_headers = setup_levelup_headers(levelup_api_key)

# ───────── Sidebar: Define the single known game ─────────────────────────────────
# We know the only valid game is "EA Sports FC 25" with brand ID = 3136
SINGLE_BRAND_ID = 3136
SINGLE_BRAND_NAME = "EA Sports FC 25"

# ───────── Sidebar: Event Details & Single-Game Dropdown ────────────────────────
st.sidebar.markdown("---")
st.sidebar.header("Event Configuration")

n_events = st.sidebar.number_input(
    "Number of events",
    min_value=1,
    max_value=10,
    value=1,
    step=1
)
events: list[dict] = []

for i in range(n_events):
    st.sidebar.markdown(f"**Event {i+1} Details**")
    name = st.sidebar.text_input(f"Event Name {i+1}", key=f"name_{i}") or f"Event{i+1}"
    date = st.sidebar.date_input(f"Event Date {i+1}", key=f"date_{i}")

    # Single-game selectbox (always "EA Sports FC 25")
    _ = st.sidebar.selectbox(
        f"Brand (Event {i+1})",
        options=[SINGLE_BRAND_NAME],
        key=f"brand_select_{i}"
    )
    selected_id = SINGLE_BRAND_ID  # always 3136

    region = st.sidebar.text_input(f"Region (Event {i+1})", key=f"region_{i}", value="TH")

    events.append({
        "name": name,
        "date": datetime.combine(date, datetime.min.time()),
        "brandId": selected_id,
        "region": region
    })

# ───────── Sidebar: Metric selection ──────────────────────────────────────────────
metrics = st.sidebar.multiselect(
    "Select metrics to include:",
    [
        "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions",
        "Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Search Index", "PCCV", "AMA"
    ],
    default=[]
)

# Reset Onclusive state if Social Mentions is deselected
if "Social Mentions" not in metrics:
    for k in ["manual_social_toggle", "onclusive_user", "onclusive_pw", "onclusive_query"]:
        st.session_state.pop(k, None)

# Reset manual LevelUp inputs if video metrics are deselected
if not any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.session_state.pop("manual_levelup_toggle", None)

# ───────── Sidebar: Output Regions (sheet tabs) ─────────────────────────────────
regions = st.sidebar.multiselect(
    "Output Regions (sheet tabs):",
    ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"],
    default=[]
)

# ────────────────────────────────────────────────────────────────────────────────
# 3) Onclusive (Social Mentions) inputs
# ────────────────────────────────────────────────────────────────────────────────

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
        value=st.session_state.get("manual_social_toggle", False)
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

        if onclusive_username and onclusive_password and onclusive_query:
            st.write("🔍 Testing Onclusive credentials…")
            test_count = fetch_social_mentions_count(
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                onclusive_username,
                onclusive_password,
                onclusive_language,
                onclusive_query
            )
            if test_count is not None:
                st.success("✅ Onclusive login OK")
            else:
                st.error("❌ Onclusive login failed")

# ────────────────────────────────────────────────────────────────────────────────
# 4) LevelUp (Video Views & Hours Watched) inputs
# ────────────────────────────────────────────────────────────────────────────────

levelup_api_key = st.session_state.get("levelup_api_key")
manual_levelup_inputs: dict[int, dict[str, tuple[int, int]]] = {}

if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.subheader("🎮 LevelUp API for Video Views & Hours Watched")
    use_manual_levelup = st.checkbox(
        "❔ Enter LevelUp metrics manually (skip API)",
        key="manual_levelup_toggle",
        value=st.session_state.get("manual_levelup_toggle", False)
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
        if not levelup_api_key:
            st.error("🔑 You must supply a LevelUp API Key in the sidebar above or choose manual entry.")
        else:
            api_headers = setup_levelup_headers(levelup_api_key)
            st.success("🗝️ LevelUp API Key set. Ready to fetch data.")

# ────────────────────────────────────────────────────────────────────────────────
# 5) Generate & Download Scorecard (combined per-event rows)
# ────────────────────────────────────────────────────────────────────────────────

if st.button("Generate Scorecard"):
    # 1) Validate Onclusive inputs if needed
    if "Social Mentions" in metrics and not manual_social_inputs:
        if not (onclusive_username and onclusive_password and onclusive_query):
            st.warning("Enter Onclusive credentials or choose manual entry for Social Mentions.")
            st.stop()

    # 2) Validate LevelUp inputs if needed
    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics) and not manual_levelup_inputs:
        if not levelup_api_key:
            st.warning("Provide a LevelUp API Key or choose manual entry for video metrics.")
            st.stop()
        api_headers = setup_levelup_headers(levelup_api_key)

    # 3) Build a single combined DataFrame with one row per event, including all selected metrics
    combined_rows = []
    for idx, ev in enumerate(events):
        # Start row with basic info
        row = {
            "Event": ev["name"],
            "Date": ev["date"].date(),
            "Region": ev["region"],
            "Brand ID": ev["brandId"],
            "Brand Name": SINGLE_BRAND_NAME
        }

        # Prepare to fetch LevelUp metrics once if needed
        needs_levelup = any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics)
        ev_metrics: dict[str, pd.DataFrame] = {}
        if needs_levelup and not (manual_levelup_inputs and idx in manual_levelup_inputs):
            ev_metrics = generate_levelup_metrics_for_event(ev, api_headers)

        # ─ Social Mentions ─────────────────────────────────────────────────
        if "Social Mentions" in metrics:
            if manual_social_inputs and idx in manual_social_inputs:
                base_sm, act_sm = manual_social_inputs[idx]
            else:
                event_date = ev["date"].date()
                baseline_start = (event_date - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
                baseline_end   = (event_date - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                actual_start   = event_date.strftime("%Y-%m-%dT00:00:00Z")
                actual_end     = (event_date + timedelta(days=30)).strftime("%Y-%m-%dT23:59:59Z")

                base_sm = fetch_social_mentions_count(
                    baseline_start,
                    baseline_end,
                    onclusive_username,
                    onclusive_password,
                    onclusive_language,
                    onclusive_query
                ) or 0
                act_sm = fetch_social_mentions_count(
                    actual_start,
                    actual_end,
                    onclusive_username,
                    onclusive_password,
                    onclusive_language,
                    onclusive_query
                ) or 0

            row["Baseline Social Mentions"] = base_sm
            row["Actual Social Mentions"]   = act_sm

        # ─ Video Views (VOD) ────────────────────────────────────────────────
        if "Video Views (VOD)" in metrics:
            if manual_levelup_inputs and idx in manual_levelup_inputs and "Video Views (VOD)" in manual_levelup_inputs[idx]:
                base_vv, act_vv = manual_levelup_inputs[idx]["Video Views (VOD)"]
            else:
                # Check if the "videos" table exists and has "views"
                if "videos" in ev_metrics:
                    vid_df = ev_metrics["videos"]
                    if "views" in vid_df.columns and "period" in vid_df.columns:
                        base_vv = vid_df[vid_df["period"] == "baseline"]["views"].sum()
                        act_vv  = vid_df[vid_df["period"] == "actual"]["views"].sum()
                    else:
                        base_vv = 0
                        act_vv  = 0
                else:
                    base_vv = 0
                    act_vv  = 0

            row["Baseline Video Views"] = base_vv
            row["Actual Video Views"]   = act_vv

        # ─ Hours Watched (Streams) ───────────────────────────────────────────
        if "Hours Watched (Streams)" in metrics:
            if manual_levelup_inputs and idx in manual_levelup_inputs and "Hours Watched (Streams)" in manual_levelup_inputs[idx]:
                base_hw, act_hw = manual_levelup_inputs[idx]["Hours Watched (Streams)"]
            else:
                # Check if the "streams" table exists and has "watchTime"
                if "streams" in ev_metrics:
                    str_df = ev_metrics["streams"]
                    if "watchTime" in str_df.columns and "period" in str_df.columns:
                        base_hw = str_df[str_df["period"] == "baseline"]["watchTime"].sum()
                        act_hw  = str_df[str_df["period"] == "actual"]["watchTime"].sum()
                    else:
                        base_hw = 0
                        act_hw  = 0
                else:
                    base_hw = 0
                    act_hw  = 0

            row["Baseline Hours Watched"] = base_hw
            row["Actual Hours Watched"]   = act_hw

        # ─ Other metrics placeholders ────────────────────────────────────────
        # If you implement Sessions, DAU, etc., add them here similarly.

        combined_rows.append(row)

    # Convert to DataFrame
    combined_df = pd.DataFrame(combined_rows)

    # 4) Write out to Excel and provide a single sheet download
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # Name this sheet "Scorecard" or whatever you like
        combined_df.to_excel(writer, sheet_name="Scorecard", index=False)
    buffer.seek(0)

    st.download_button(
        label="Download Combined Scorecard",
        data=buffer,
        file_name="event_marketing_scorecard.xlsx",
        mime="application/vnd.openxmlformats-officedocument-spreadsheetml.sheet"
    )
