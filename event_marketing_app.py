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
    Dates should be "YYYY-MM-DD" strings. Returns a DataFrame or None if no data / error.
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
        st.error(f"Error fetching {data_type} for brand {brand_id}, region {region_code}: HTTP {response.status_code}")
        return None

    payload = response.json().get("data", [])
    if not payload:
        return None

    df = pd.DataFrame(payload)
    df["brand_id"] = brand_id
    df["country_region_code"] = region_code

    if data_type == "videos" and "views" in df.columns:
        df["views"] = df["views"].astype(int)
    elif data_type == "streams" and "hoursWatched" in df.columns:
        df["hoursWatched"] = df["hoursWatched"].astype(float)

    return df

def generate_levelup_metrics_for_event(event: dict, api_headers: dict) -> dict[str, pd.DataFrame]:
    """
    For a single event (with keys name, date, brandId, region), fetch:
      - Baseline (30 days before) and Actual (30 days after) for both “videos” and “streams”.
    Returns a dict with possible keys "videos" and "streams", each mapping to the concatenated DataFrame.
    """
    event_date = event["date"].date()
    baseline_start = (event_date - timedelta(days=30)).strftime("%Y-%m-%d")
    baseline_end   = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
    actual_start   = event_date.strftime("%Y-%m-%d")
    actual_end     = (event_date + timedelta(days=30)).strftime("%Y-%m-%d")

    brand = int(event["brandId"])
    region = event["region"]

    metrics_dfs: dict[str, pd.DataFrame] = {}

    # --- Video Views (VOD) ---
    vid_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "videos")
    vid_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "videos")
    if vid_df_baseline is not None and vid_df_actual is not None:
        vid_df_baseline["period"] = "baseline"
        vid_df_actual["period"]   = "actual"
        metrics_dfs["videos"] = pd.concat([vid_df_baseline, vid_df_actual], ignore_index=True)

    # --- Hours Watched (Streams) ---
    str_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "streams")
    str_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "streams")
    if str_df_baseline is not None and str_df_actual is not None:
        str_df_baseline["period"] = "baseline"
        str_df_actual["period"]   = "actual"
        metrics_dfs["streams"] = pd.concat([str_df_baseline, str_df_actual], ignore_index=True)

    return metrics_dfs

def compute_three_month_average(
    api_headers: dict,
    brand_id: int,
    region: str,
    event_date: datetime.date,
    data_type: str
) -> float:
    """
    Compute the average daily metric (views or watchTime) for the 90 days prior to event_date.
    data_type: "videos" → use "views"; "streams" → use "watchTime".
    Returns 0 if no data.
    """
    end_date = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (event_date - timedelta(days=90)).strftime("%Y-%m-%d")
    df = fetch_levelup_data(api_headers, brand_id, start_date, end_date, region, data_type)
    if df is None or df.empty:
        return 0.0
    column = "views" if data_type == "videos" else "watchTime"
    if column not in df.columns or "period" not in df.columns:
        return 0.0
    # The API returns daily rows; compute average over all returned days
    return df[column].mean()

# ────────────────────────────────────────────────────────────────────────────────
# 2) Main Streamlit App
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

# ───────── Sidebar: Single‐Game (EA Sports FC 25) ─────────────────────────────────
SINGLE_BRAND_ID = 3136
SINGLE_BRAND_NAME = "EA Sports FC 25"

st.sidebar.markdown("---")
st.sidebar.header("Event Configuration")
n_events = st.sidebar.number_input(
    "Number of events",
    min_value=1, max_value=10, value=1, step=1
)
events: list[dict] = []

for i in range(n_events):
    st.sidebar.markdown(f"**Event {i+1} Details**")
    name   = st.sidebar.text_input(f"Event Name {i+1}", key=f"name_{i}") or f"Event{i+1}"
    date   = st.sidebar.date_input(f"Event Date {i+1}", key=f"date_{i}")
    _      = st.sidebar.selectbox(
               f"Brand (Event {i+1})",
               options=[SINGLE_BRAND_NAME],
               key=f"brand_select_{i}"
            )
    selected_id = SINGLE_BRAND_ID
    region = st.sidebar.text_input(f"Region (Event {i+1})", key=f"region_{i}", value="TH")

    events.append({
        "name":   name,
        "date":   datetime.combine(date, datetime.min.time()),
        "brandId": selected_id,
        "region": region
    })

# ───────── Sidebar: Metric selection ──────────────────────────────────────────────
metrics = st.sidebar.multiselect(
    "Select metrics to include:",
    [
        "Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions",
        "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time",
        "ARPU", "Conversions", "Search Index", "PCCV", "AMA"
    ],
    default=[]
)

# Reset Onclusive state if Social Mentions is deselected
if "Social Mentions" not in metrics:
    for k in ["manual_social_toggle", "onclusive_user", "onclusive_pw", "onclusive_query"]:
        st.session_state.pop(k, None)

# Reset manual LevelUp inputs if no video metrics are selected
if not any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.session_state.pop("manual_levelup_toggle", None)

# ───────── Sidebar: Output Regions (sheet tabs) ─────────────────────────────────
regions = st.sidebar.multiselect(
    "Output Regions (sheet tabs):",
    ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"],
    default=[]
)

# ────────────────────────────────────────────────────────────────────────────────
# 3) Onclusive (Social Mentions) Inputs
# ────────────────────────────────────────────────────────────────────────────────

onclusive_username = st.session_state.get("onclusive_user")
onclusive_password = st.session_state.get("onclusive_pw")
onclusive_language = st.session_state.get("onclusive_lang", "en")
onclusive_query    = st.session_state.get("onclusive_query")
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
        onclusive_query    = st.text_input("Search Keywords", placeholder="e.g. FIFA, EA Sports", key="onclusive_query")

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
# 4) LevelUp (Video Views & Hours Watched) Inputs
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
# 5) Generate & Download Scorecard—one table per event with metrics on left
# ────────────────────────────────────────────────────────────────────────────────

if st.button("Generate Scorecard"):
    # 1) Validate Onclusive inputs if needed
    if "Social Mentions" in metrics and not manual_social_inputs:
        if not (onclusive_username and onclusive_password and onclusive_query):
            st.warning("Enter Onclusive credentials or choose manual entry for Social Mentions.")
            st.stop()

    # 2) Validate LevelUp API inputs if needed
    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics) and not manual_levelup_inputs:
        if not levelup_api_key:
            st.warning("Provide a LevelUp API Key or choose manual entry for video metrics.")
            st.stop()
        api_headers = setup_levelup_headers(levelup_api_key)

    # 3) Build one DataFrame per event:
    #      • Rows = each selected metric
    #      • Columns = [“Metric”, “Baseline <range>”, “Actual <range>”, “3-Month Avg”]
    sheets_dict: dict[str, pd.DataFrame] = {}

    for idx, ev in enumerate(events):
        ev_date = ev["date"].date()
        baseline_start = ev_date - timedelta(days=30)
        baseline_end   = ev_date - timedelta(days=1)
        actual_start   = ev_date
        actual_end     = ev_date + timedelta(days=30)

        # Column headers
        baseline_label = f"Baseline  {baseline_start:%Y-%m-%d} → {baseline_end:%Y-%m-%d}"
        actual_label   = f"Actual    {actual_start:%Y-%m-%d} → {actual_end:%Y-%m-%d}"
        avg_label      = "3-Month Avg"

        # Prepare rows
        rows_for_event: list[dict[str, object]] = []

        # Fetch LevelUp metrics once if needed
        needs_levelup = any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics)
        fetched_metrics: dict[str, pd.DataFrame] = {}
        if needs_levelup and not (manual_levelup_inputs and idx in manual_levelup_inputs):
            fetched_metrics = generate_levelup_metrics_for_event(ev, api_headers)

        for metric_name in metrics:
            row = {
                "Metric": metric_name,
                baseline_label: None,
                actual_label: None,
                avg_label: None
            }

            # -- Social Mentions --
            if metric_name == "Social Mentions":
                # Baseline & Actual
                if manual_social_inputs and idx in manual_social_inputs:
                    base_sm, act_sm = manual_social_inputs[idx]
                    row[baseline_label] = base_sm
                    row[actual_label]   = act_sm
                else:
                    bs = fetch_social_mentions_count(
                        f"{baseline_start:%Y-%m-%d}T00:00:00Z",
                        f"{baseline_end:%Y-%m-%d}T23:59:59Z",
                        onclusive_username,
                        onclusive_password,
                        onclusive_language,
                        onclusive_query
                    ) or 0
                    as_ = fetch_social_mentions_count(
                        f"{actual_start:%Y-%m-%d}T00:00:00Z",
                        f"{actual_end:%Y-%m-%d}T23:59:59Z",
                        onclusive_username,
                        onclusive_password,
                        onclusive_language,
                        onclusive_query
                    ) or 0
                    row[baseline_label] = bs
                    row[actual_label]   = as_
                # 3‐month average for Social Mentions isn’t defined; leave blank
                row[avg_label] = None

            # -- Video Views (VOD) --
            elif metric_name == "Video Views (VOD)":
                # Baseline & Actual
                if manual_levelup_inputs and idx in manual_levelup_inputs and "Video Views (VOD)" in manual_levelup_inputs[idx]:
                    base_vv, act_vv = manual_levelup_inputs[idx]["Video Views (VOD)"]
                    row[baseline_label] = base_vv
                    row[actual_label]   = act_vv
                else:
                    vid_df = fetched_metrics.get("videos", pd.DataFrame())
                    if not vid_df.empty and "period" in vid_df.columns and "views" in vid_df.columns:
                        bv = vid_df[vid_df["period"] == "baseline"]["views"].sum()
                        av = vid_df[vid_df["period"] == "actual"]["views"].sum()
                    else:
                        bv, av = 0, 0
                    row[baseline_label] = bv
                    row[actual_label]   = av

                # 3‐Month Avg (average daily “views” for 90 days before event_date)
                avg_vv = compute_three_month_average(api_headers, ev["brandId"], ev["region"], ev_date, "videos")
                row[avg_label] = round(avg_vv, 2)

            # -- Hours Watched (Streams) --
            elif metric_name == "Hours Watched (Streams)":
                # Baseline & Actual
                if manual_levelup_inputs and idx in manual_levelup_inputs and "Hours Watched (Streams)" in manual_levelup_inputs[idx]:
                    base_hw, act_hw = manual_levelup_inputs[idx]["Hours Watched (Streams)"]
                    row[baseline_label] = base_hw
                    row[actual_label]   = act_hw
                else:
                    str_df = fetched_metrics.get("streams", pd.DataFrame())
                    if not str_df.empty and "period" in str_df.columns and "watchTime" in str_df.columns:
                        bh = str_df[str_df["period"] == "baseline"]["watchTime"].sum()
                        ah = str_df[str_df["period"] == "actual"]["watchTime"].sum()
                    else:
                        bh, ah = 0, 0
                    row[baseline_label] = bh
                    row[actual_label]   = ah

                # 3‐Month Avg (average daily “watchTime” for 90 days before event_date)
                avg_hw = compute_three_month_average(api_headers, ev["brandId"], ev["region"], ev_date, "streams")
                row[avg_label] = round(avg_hw, 2)

            # -- Other metrics (e.g., Sessions, DAU) can be added here similarly --
            else:
                row[baseline_label] = None
                row[actual_label]   = None
                row[avg_label]      = None

            rows_for_event.append(row)

        # Convert to DataFrame and set index to “Metric”
        df_event = pd.DataFrame(rows_for_event).set_index("Metric")

        # Display in Streamlit under event header
        st.markdown(f"### Event {idx+1}: {ev['name']}  \n"
                    f"**Date:** {ev['date'].date():%Y-%m-%d}  |  **Region:** {ev['region']}")
        st.dataframe(df_event)

        # Save for Excel (reset index so “Metric” is a column again)
        sheets_dict[ev["name"][:28] or f"Event{idx+1}"] = df_event.reset_index()

    # 4) Write each event’s table into a separate sheet in one Excel workbook
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df_event in sheets_dict.items():
            safe_name = sheet_name[:31]
            df_event.to_excel(writer, sheet_name=safe_name, index=False)
    buffer.seek(0)

    st.download_button(
        label="Download Full Scorecard Workbook",
        data=buffer,
        file_name="event_marketing_scorecard.xlsx",
        mime="application/vnd.openxmlformats-officedocument-spreadsheetml.sheet"
    )
