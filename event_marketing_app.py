import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

# ─ Helper Functions for LevelUp API Integration ─────────────────────────────────

def setup_levelup_headers(api_key: str) -> dict:
    """
    Constructs HTTP headers for LevelUp API requests using the provided API key.
    """
    return {
        "accept": "application/json",
        "X-API-KEY": api_key
    }

def fetch_levelup_data(api_headers: dict, brand_id: int, start_date: str, end_date: str, region_code: str, data_type: str):
    """
    Fetches time-series data ("videos" or "streams") for a specific brand and region
    from LevelUp between start_date and end_date (ISO "YYYY-MM-DD" format).
    Returns a pandas DataFrame with columns for date, metric (views or watchTime), brand_id, and region.
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

    # The API returns different fields depending on data_type:
    # - For "videos", each row has a "views" field (integer).
    # - For "streams", each row has a "watchTime" field (float or integer).
    if data_type == "videos" and "views" in df.columns:
        df["views"] = df["views"].astype(int)
    elif data_type == "streams" and "watchTime" in df.columns:
        df["watchTime"] = df["watchTime"].astype(float)

    return df

def generate_levelup_metrics_for_event(event: dict, api_headers: dict) -> dict:
    """
    For a single event (dict with "name", "date", "brandId", "region"), fetch:
      - Baseline (30 days before event date up to day before event) data
      - Actual   (event date up to 30 days after event) data
    Returns a dict with DataFrames for "videos" and "streams" if requested.
    """
    event_date = event["date"].date()
    baseline_start = (event_date - timedelta(days=30)).strftime("%Y-%m-%d")
    baseline_end   = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
    actual_start   = event_date.strftime("%Y-%m-%d")
    actual_end     = (event_date + timedelta(days=30)).strftime("%Y-%m-%d")

    brand = int(event["brandId"])
    region = event["region"]

    metrics_dfs = {}

    # Fetch video views (VOD)
    vid_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "videos")
    vid_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "videos")
    if vid_df_baseline is not None and vid_df_actual is not None:
        vid_df_baseline["period"] = "baseline"
        vid_df_actual["period"]   = "actual"
        metrics_dfs["videos"] = pd.concat([vid_df_baseline, vid_df_actual], ignore_index=True)

    # Fetch hours watched (streams)
    str_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "streams")
    str_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "streams")
    if str_df_baseline is not None and str_df_actual is not None:
        str_df_baseline["period"] = "baseline"
        str_df_actual["period"]   = "actual"
        metrics_dfs["streams"] = pd.concat([str_df_baseline, str_df_actual], ignore_index=True)

    return metrics_dfs

# ─ Streamlit App ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

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
    for k in ["manual_levelup_toggle", "levelup_api_key"]:
        st.session_state.pop(k, None)

# Sidebar: Output regions for report tabs
regions = st.sidebar.multiselect(
    "Output Regions (sheet tabs):",
    ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"],
    default=[]
)

# ─ Onclusive (Social Mentions) Inputs ─────────────────────────────────────────

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

        # Optional quick test for Onclusive credentials
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

# ─ LevelUp (Video Views & Hours Watched) Inputs ─────────────────────────────────

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
        levelup_api_key = st.text_input("LevelUp API Key", type="password", key="levelup_api_key")
        if levelup_api_key:
            api_headers = setup_levelup_headers(levelup_api_key)
        else:
            st.info("Enter your LevelUp API Key above or choose manual entry.")

# ─ Generate & Download Scorecard ─────────────────────────────────────────────────

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

    # 3) Build Excel sheets dictionary
    sheets: dict[str, pd.DataFrame] = {}

    # 3a) Social Mentions sheet
    if "Social Mentions" in metrics:
        social_rows = []
        if manual_social_inputs:
            for idx, ev in enumerate(events):
                base, actual = manual_social_inputs[idx]
                social_rows.append({
                    "Event": ev["name"],
                    "Region": ev["region"],
                    "Brand ID": ev["brandId"],
                    "Baseline Social Mentions": base,
                    "Actual Social Mentions": actual
                })
        else:
            for idx, ev in enumerate(events):
                event_date = ev["date"].date()
                baseline_start = (event_date - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
                baseline_end   = (event_date - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                actual_start   = event_date.strftime("%Y-%m-%dT00:00:00Z")
                actual_end     = (event_date + timedelta(days=30)).strftime("%Y-%m-%dT23:59:59Z")

                baseline_count = fetch_social_mentions_count(
                    baseline_start,
                    baseline_end,
                    onclusive_username,
                    onclusive_password,
                    onclusive_language,
                    onclusive_query
                )
                actual_count = fetch_social_mentions_count(
                    actual_start,
                    actual_end,
                    onclusive_username,
                    onclusive_password,
                    onclusive_language,
                    onclusive_query
                )
                social_rows.append({
                    "Event": ev["name"],
                    "Region": ev["region"],
                    "Brand ID": ev["brandId"],
                    "Baseline Social Mentions": baseline_count or 0,
                    "Actual Social Mentions": actual_count or 0
                })

        sheets["Social Mentions"] = pd.DataFrame(social_rows)

    # 3b) LevelUp Video Views & Hours Watched sheets
    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
        if manual_levelup_inputs:
            lv_rows = []
            for idx, ev in enumerate(events):
                row = {
                    "Event": ev["name"],
                    "Region": ev["region"],
                    "Brand ID": ev["brandId"]
                }
                vid_base, vid_act = manual_levelup_inputs[idx].get("Video Views (VOD)", (None, None))
                str_base, str_act = manual_levelup_inputs[idx].get("Hours Watched (Streams)", (None, None))
                if "Video Views (VOD)" in metrics:
                    row["Baseline Video Views"] = vid_base
                    row["Actual Video Views"]   = vid_act
                if "Hours Watched (Streams)" in metrics:
                    row["Baseline Hours Watched"] = str_base
                    row["Actual Hours Watched"]   = str_act
                lv_rows.append(row)

            sheets["LevelUp Metrics (Manual)"] = pd.DataFrame(lv_rows)

        else:
            # Use LevelUp API to fetch automatically
            all_videos = []
            all_streams = []

            for ev in events:
                ev_metrics = generate_levelup_metrics_for_event(ev, api_headers)

                if "videos" in ev_metrics and "Video Views (VOD)" in metrics:
                    vid_df = ev_metrics["videos"]
                    base_total = vid_df[vid_df["period"] == "baseline"]["views"].sum()
                    act_total  = vid_df[vid_df["period"] == "actual"]["views"].sum()
                    all_videos.append({
                        "Event": ev["name"],
                        "Region": ev["region"],
                        "Brand ID": ev["brandId"],
                        "Baseline Video Views": base_total,
                        "Actual Video Views": act_total
                    })

                if "streams" in ev_metrics and "Hours Watched (Streams)" in metrics:
                    str_df = ev_metrics["streams"]
                    base_total = str_df[str_df["period"] == "baseline"]["watchTime"].sum()
                    act_total  = str_df[str_df["period"] == "actual"]["watchTime"].sum()
                    all_streams.append({
                        "Event": ev["name"],
                        "Region": ev["region"],
                        "Brand ID": ev["brandId"],
                        "Baseline Hours Watched": base_total,
                        "Actual Hours Watched": act_total
                    })

            if all_videos:
                sheets["Video Views (LevelUp)"] = pd.DataFrame(all_videos)
            if all_streams:
                sheets["Hours Watched (LevelUp)"] = pd.DataFrame(all_streams)

    # 3c) Additional metric sheets (Sessions, DAU, etc.) can be built similarly

    if not sheets:
        st.warning("No sheets to generate. Please select at least one metric.")
        st.stop()

    # 4) Write out to Excel and provide download
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)
    buffer.seek(0)

    st.download_button(
        label="Download Scorecard Report",
        data=buffer,
        file_name="event_marketing_scorecard.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
