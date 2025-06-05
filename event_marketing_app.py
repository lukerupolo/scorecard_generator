import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO

# ────────────────────────────────────────────────────────────────────────────────
# 1) Helper functions for LevelUp API integration and Social Mentions (Onclusive)
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
    resp = requests.get(api_url, headers=api_headers, params=params)
    if resp.status_code != 200:
        st.error(f"Error fetching {data_type} for brand {brand_id}, region {region_code}: HTTP {resp.status_code}")
        return None

    payload = resp.json().get("data", [])
    if not payload:
        return None

    df = pd.DataFrame(payload)
    df["brand_id"] = brand_id
    df["country_region_code"] = region_code

    if data_type == "videos" and "views" in df.columns:
        df["views"] = df["views"].astype(int)
    elif data_type == "streams":
        # LevelUp uses "hoursWatched" field for streams
        if "hoursWatched" in df.columns:
            df["hoursWatched"] = df["hoursWatched"].astype(float)
    return df

def generate_levelup_metrics_for_event(event: dict, api_headers: dict) -> dict[str, pd.DataFrame]:
    """
    For a single event (with keys name, date, brandId, region), fetch:
      - Baseline (7 days before) and Actual (7 days after) for both “videos” and “streams”.
      Returns a dict with possible keys "videos" and "streams", each mapping to the concatenated DataFrame.
    """
    event_date = event["date"].date()

    # --- NEW: 7-day windows instead of 30-day ---
    baseline_start = (event_date - timedelta(days=7)).strftime("%Y-%m-%d")
    baseline_end   = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
    actual_start   = event_date.strftime("%Y-%m-%d")
    actual_end     = (event_date + timedelta(days=6)).strftime("%Y-%m-%d")
    # — End of NEW section —

    brand = int(event["brandId"])
    region = event["region"]

    metrics_dfs: dict[str, pd.DataFrame] = {}

    # Video Views (VOD)
    vid_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "videos")
    vid_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "videos")
    if vid_df_baseline is not None and vid_df_actual is not None:
        vid_df_baseline["period"] = "baseline"
        vid_df_actual["period"]   = "actual"
        metrics_dfs["videos"] = pd.concat([vid_df_baseline, vid_df_actual], ignore_index=True)

    # Hours Watched (Streams)
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
    Compute the average daily metric (views or hoursWatched) for 90 days prior to event_date.
    data_type: "videos" → use "views"; "streams" → use "hoursWatched".
    Returns 0 if no data.
    """
    end_date = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (event_date - timedelta(days=90)).strftime("%Y-%m-%d")
    df = fetch_levelup_data(api_headers, brand_id, start_date, end_date, region, data_type)
    if df is None or df.empty:
        return 0.0

    if data_type == "videos":
        column = "views"
    else:  # data_type == "streams"
        column = "hoursWatched" if "hoursWatched" in df.columns else None

    if column and column in df.columns:
        return df[column].mean()
    return 0.0

# Placeholder for fetching social mentions count.
# If you have a function `fetch_social_mentions_count(...)`, import or define it here.
# For now, we will default Social Mentions to zeros if the function is not present.

def fetch_social_mentions_count(
    start_iso: str,
    end_iso: str,
    username: str,
    password: str,
    language: str,
    query: str
) -> int:
    """
    Placeholder function. Replace with your actual Onclusive API call implementation.
    Returns an integer count of social mentions between start_iso and end_iso.
    """
    # TODO: Implement actual call to Onclusive (Digimind) here.
    return 0

# ────────────────────────────────────────────────────────────────────────────────
# 2) Streamlit app configuration and sidebar with emojis
# ────────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# ────────────────────────────────────────────────────────────────────────────────
# 3) Sidebar: Event Configuration
# ────────────────────────────────────────────────────────────────────────────────

st.sidebar.markdown("## 📅 Event Configuration")
st.sidebar.markdown("Set up one or more events and their details below.")

SINGLE_BRAND_ID = 3136
SINGLE_BRAND_NAME = "EA Sports FC 25"

n_events = st.sidebar.number_input(
    "Number of events", min_value=1, max_value=10, value=1, step=1
)

events: list[dict] = []
for i in range(n_events):
    st.sidebar.markdown(f"### Event {i+1}")
    name = st.sidebar.text_input(
        f"🔤 Name (Event {i+1})", key=f"name_{i}"
    ) or f"Event{i+1}"
    date = st.sidebar.date_input(
        f"📅 Date (Event {i+1})", key=f"date_{i}"
    )

    st.sidebar.markdown(f"• **Brand** (fixed): {SINGLE_BRAND_NAME}")
    _ = st.sidebar.selectbox(
        f"", options=[SINGLE_BRAND_NAME], key=f"brand_select_{i}"
    )
    region = st.sidebar.text_input(
        f"🌐 Region Code (Event {i+1})", key=f"region_{i}", value="TH"
    )

    events.append({
        "name": name,
        "date": datetime.combine(date, datetime.min.time()),
        "brandId": SINGLE_BRAND_ID,
        "region": region,
    })

st.sidebar.markdown("---")

# ────────────────────────────────────────────────────────────────────────────────
# 4) Sidebar: Metric Selection
# ────────────────────────────────────────────────────────────────────────────────

st.sidebar.markdown("## 🎛️ Metric Selection")
st.sidebar.markdown("Choose one or more metrics to include in your scorecard:")

metrics = st.sidebar.multiselect(
    "",
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
        "AMA",
    ],
    default=[],
)

# Clear saved Onclusive state if Social Mentions is deselected
if "Social Mentions" not in metrics:
    for k in [
        "manual_social_toggle",
        "onclusive_user",
        "onclusive_pw",
        "onclusive_query",
    ]:
        st.session_state.pop(k, None)

# Clear saved LevelUp state if no Video/Streams metrics are selected
if not any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.session_state.pop("manual_levelup_toggle", None)

st.sidebar.markdown("---")

# ────────────────────────────────────────────────────────────────────────────────
# 5) Sidebar: Onclusive (Social Mentions) Authentication
# ────────────────────────────────────────────────────────────────────────────────

onclusive_username = None
onclusive_password = None
onclusive_language = "en"
onclusive_query = None
manual_social_inputs: dict[int, tuple[int, int]] = {}

if "Social Mentions" in metrics:
    st.sidebar.markdown("## 💬 Social Mentions (Onclusive)")
    st.sidebar.markdown("Enter your Onclusive credentials or skip for manual entry.")

    use_manual_social = st.sidebar.checkbox(
        "✍️ Manual Social Mentions entry (skip Onclusive)",
        key="manual_social_toggle",
        value=st.session_state.get("manual_social_toggle", False),
    )
    if use_manual_social:
        st.sidebar.info("Provide baseline & actual counts for each event.")
        for idx, ev in enumerate(events):
            base_sm = st.sidebar.number_input(
                f"Event {idx+1} ({ev['name']}): Baseline Social Mentions",
                min_value=0,
                step=1,
                key=f"social_baseline_{idx}",
            )
            act_sm = st.sidebar.number_input(
                f"Event {idx+1} ({ev['name']}): Actual Social Mentions",
                min_value=0,
                step=1,
                key=f"social_actual_{idx}",
            )
            manual_social_inputs[idx] = (base_sm, act_sm)
    else:
        onclusive_username = st.sidebar.text_input(
            "🔐 Onclusive Username", placeholder="you@example.com", key="onclusive_user"
        )
        onclusive_password = st.sidebar.text_input(
            "🔒 Onclusive Password", type="password", key="onclusive_pw"
        )
        onclusive_language = st.sidebar.text_input(
            "🌐 Language", value="en", key="onclusive_lang"
        )
        onclusive_query = st.sidebar.text_input(
            "🔍 Search Keywords", placeholder="e.g. FIFA, EA Sports", key="onclusive_query"
        )

        # Optional: Uncomment below once fetch_social_mentions_count is implemented
        # if onclusive_username and onclusive_password and onclusive_query:
        #     st.sidebar.write("🔍 Testing Onclusive credentials…")
        #     test_count = fetch_social_mentions_count(
        #         "2024-01-01T00:00:00Z",
        #         "2024-01-02T00:00:00Z",
        #         onclusive_username,
        #         onclusive_password,
        #         onclusive_language,
        #         onclusive_query,
        #     )
        #     if test_count is not None:
        #         st.sidebar.success("✅ Onclusive login OK")
        #     else:
        #         st.sidebar.error("❌ Onclusive login failed")

    st.sidebar.markdown("---")

# ────────────────────────────────────────────────────────────────────────────────
# 6) Sidebar: LevelUp (Video/Streams) Authentication
# ────────────────────────────────────────────────────────────────────────────────

levelup_api_key = None
api_headers = None
manual_levelup_inputs: dict[int, dict[str, tuple[int, int]]] = {}

if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.sidebar.markdown("## 🎮 LevelUp API")
    st.sidebar.markdown(
        "To auto-fetch Video Views or Hours Watched, paste your LevelUp API Key below. "
        "Otherwise, use manual entry."
    )

    use_manual_levelup = st.sidebar.checkbox(
        "✍️ Manual Video/Streams entry (skip API)",
        key="manual_levelup_toggle",
        value=st.session_state.get("manual_levelup_toggle", False),
    )

    if use_manual_levelup:
        st.sidebar.info("Provide baseline & actual values for each event.")
        for idx, ev in enumerate(events):
            manual_levelup_inputs[idx] = {}
            if "Video Views (VOD)" in metrics:
                vv_base = st.sidebar.number_input(
                    f"Event {idx+1} ({ev['name']}): Baseline Video Views (VOD)",
                    min_value=0,
                    step=1,
                    key=f"levelup_vv_baseline_{idx}",
                )
                vv_act = st.sidebar.number_input(
                    f"Event {idx+1} ({ev['name']}): Actual Video Views (VOD)",
                    min_value=0,
                    step=1,
                    key=f"levelup_vv_actual_{idx}",
                )
                manual_levelup_inputs[idx]["Video Views (VOD)"] = (vv_base, vv_act)

            if "Hours Watched (Streams)" in metrics:
                hw_base = st.sidebar.number_input(
                    f"Event {idx+1} ({ev['name']}): Baseline Hours Watched",
                    min_value=0,
                    step=1,
                    key=f"levelup_hw_baseline_{idx}",
                )
                hw_act = st.sidebar.number_input(
                    f"Event {idx+1} ({ev['name']}): Actual Hours Watched",
                    min_value=0,
                    step=1,
                    key=f"levelup_hw_actual_{idx}",
                )
                manual_levelup_inputs[idx]["Hours Watched (Streams)"] = (hw_base, hw_act)

    else:
        levelup_api_key = st.sidebar.text_input(
            "🔑 Paste LevelUp API Key here", type="password", key="levelup_api_key"
        )
        if levelup_api_key:
            api_headers = setup_levelup_headers(levelup_api_key)
            st.sidebar.success("✅ LevelUp API Key set")
        else:
            st.sidebar.info("Enter your API Key to fetch data automatically.")

    st.sidebar.markdown("---")

# ────────────────────────────────────────────────────────────────────────────────
# 7) Sidebar: Output Regions (sheet tabs)
# ────────────────────────────────────────────────────────────────────────────────

st.sidebar.markdown("## 🌍 Output Regions")
st.sidebar.markdown("Select which regions should appear as separate tabs in the Excel output.")
regions = st.sidebar.multiselect(
    "",
    ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"],
    default=[],
)
st.sidebar.markdown("---")

# Initialize session_state flags (only once)
if "scorecard_ready" not in st.session_state:
    st.session_state["scorecard_ready"] = False
if "sheets_dict" not in st.session_state:
    st.session_state["sheets_dict"] = {}

# ────────────────────────────────────────────────────────────────────────────────
# 8) Main: Generate Scorecard
# ────────────────────────────────────────────────────────────────────────────────

if st.button("✅ Generate Scorecard"):
    # 8.1 Validate selections
    if not metrics:
        st.warning("⚠️ Please select at least one metric before generating.")
        st.stop()

    if "Social Mentions" in metrics and not manual_social_inputs:
        if not (onclusive_username and onclusive_password and onclusive_query):
            st.warning("⚠️ Enter Onclusive credentials or choose manual entry for Social Mentions.")
            st.stop()

    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
        if not manual_levelup_inputs and not levelup_api_key:
            st.warning("⚠️ Provide a LevelUp API Key or choose manual entry for video/streams.")
            st.stop()
        if levelup_api_key:
            api_headers = setup_levelup_headers(levelup_api_key)

    # 8.2 Build and display one table per event, collect into sheets_dict
    sheets_dict: dict[str, pd.DataFrame] = {}

    for idx, ev in enumerate(events):
        ev_date = ev["date"].date()

        # --- NEW: Use 7-day windows (instead of 30-day) ---
        baseline_start = ev_date - timedelta(days=7)
        baseline_end   = ev_date - timedelta(days=1)
        actual_start   = ev_date
        actual_end     = ev_date + timedelta(days=6)
        # — End of NEW section —

        baseline_label = f"Baseline  {baseline_start:%Y-%m-%d} → {baseline_end:%Y-%m-%d}"
        actual_label   = f"Actual    {actual_start:%Y-%m-%d} → {actual_end:%Y-%m-%d}"
        avg_label      = "Baseline Method (3 months)"

        needs_levelup = any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics)
        fetched = {}
        if needs_levelup and not (manual_levelup_inputs and idx in manual_levelup_inputs):
            fetched = generate_levelup_metrics_for_event(ev, api_headers)

        rows_for_event: list[dict[str, object]] = []
        for metric_name in metrics:
            row = {
                "Metric": metric_name,
                baseline_label: None,
                actual_label: None,
                avg_label: None,
            }

            # — Social Mentions —
            if metric_name == "Social Mentions":
                if idx in manual_social_inputs:
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
                        onclusive_query,
                    ) or 0
                    as_ = fetch_social_mentions_count(
                        f"{actual_start:%Y-%m-%d}T00:00:00Z",
                        f"{actual_end:%Y-%m-%d}T23:59:59Z",
                        onclusive_username,
                        onclusive_password,
                        onclusive_language,
                        onclusive_query,
                    ) or 0
                    row[baseline_label] = bs
                    row[actual_label]   = as_
                row[avg_label] = None

            # — Video Views (VOD) —
            elif metric_name == "Video Views (VOD)":
                if idx in manual_levelup_inputs and "Video Views (VOD)" in manual_levelup_inputs[idx]:
                    base_vv, act_vv = manual_levelup_inputs[idx]["Video Views (VOD)"]
                    row[baseline_label] = base_vv
                    row[actual_label]   = act_vv
                else:
                    vid_df = fetched.get("videos", pd.DataFrame())
                    if (
                        not vid_df.empty
                        and "period" in vid_df.columns
                        and "views" in vid_df.columns
                    ):
                        bv = vid_df[vid_df["period"] == "baseline"]["views"].sum()
                        av = vid_df[vid_df["period"] == "actual"]["views"].sum()
                    else:
                        bv, av = 0, 0
                    row[baseline_label] = bv
                    row[actual_label]   = av

                avg_vv = compute_three_month_average(
                    api_headers, ev["brandId"], ev["region"], ev_date, "videos"
                )
                row[avg_label] = round(avg_vv, 2)

            # — Hours Watched (Streams) —
            elif metric_name == "Hours Watched (Streams)":
                if idx in manual_levelup_inputs and "Hours Watched (Streams)" in manual_levelup_inputs[idx]:
                    base_hw, act_hw = manual_levelup_inputs[idx]["Hours Watched (Streams)"]
                    row[baseline_label] = base_hw
                    row[actual_label]   = act_hw
                else:
                    str_df = fetched.get("streams", pd.DataFrame())
                    if (
                        not str_df.empty
                        and "period" in str_df.columns
                        and ("hoursWatched" in str_df.columns or "watchTime" in str_df.columns)
                    ):
                        col_name = "hoursWatched" if "hoursWatched" in str_df.columns else "watchTime"
                        bh = str_df[str_df["period"] == "baseline"][col_name].sum()
                        ah = str_df[str_df["period"] == "actual"][col_name].sum()
                    else:
                        bh, ah = 0, 0
                    row[baseline_label] = bh
                    row[actual_label]   = ah

                avg_hw = compute_three_month_average(
                    api_headers, ev["brandId"], ev["region"], ev_date, "streams"
                )
                row[avg_label] = round(avg_hw, 2)

            # — Other metrics placeholders —
            else:
                row[baseline_label] = None
                row[actual_label]   = None
                row[avg_label]      = None

            rows_for_event.append(row)

        df_event = pd.DataFrame(rows_for_event).set_index("Metric")

        st.markdown(
            f"### Event {idx+1}: {ev['name']}  \n"
            f"**Date:** {ev['date'].date():%Y-%m-%d}  |  **Region:** {ev['region']}"
        )
        st.dataframe(df_event)

        sheets_dict[ev["name"][:28] or f"Event{idx+1}"] = df_event.reset_index()

    # Save to session_state so we can re‐use it for Proposed Benchmark
    st.session_state["sheets_dict"] = sheets_dict
    st.session_state["scorecard_ready"] = True

# ────────────────────────────────────────────────────────────────────────────────
# 9) If scorecard was generated, show the “Generate Proposed Benchmark” button
# ────────────────────────────────────────────────────────────────────────────────

if st.session_state.get("scorecard_ready", False):
    if st.button("🎯 Generate Proposed Benchmark"):
        sheets_dict = st.session_state["sheets_dict"]

        # Build benchmark_data from all event tables
        benchmark_data = {m: {"actuals": [], "baseline_methods": []} for m in metrics}
        for df in sheets_dict.values():
            if "Metric" not in df.columns:
                continue
            df_metric = df.set_index("Metric")
            for m in metrics:
                if m in df_metric.index:
                    row = df_metric.loc[m]
                    actual_col = [c for c in row.index if c.startswith("Actual")]
                    base_method_col = [c for c in row.index if "Baseline Method" in c]
                    if actual_col and base_method_col:
                        actual = row[actual_col[0]]
                        baseline_method = row[base_method_col[0]]
                        benchmark_data[m]["actuals"].append(actual)
                        benchmark_data[m]["baseline_methods"].append(baseline_method)

        benchmark_rows = []
        for metric, values in benchmark_data.items():
            actuals = values["actuals"]
            baselines = values["baseline_methods"]
            if not actuals or not baselines:
                continue
            avg_actual = np.mean(actuals)
            avg_baseline_method = np.mean(baselines)

            # --- Uplift math: (Avg Actual – Avg Baseline) / Avg Baseline × 100%
            if avg_baseline_method != 0:
                uplift_pct = (avg_actual - avg_baseline_method) / avg_baseline_method * 100
            else:
                uplift_pct = 0

            # Proposed Benchmark as median of the two averages
            proposed_benchmark = np.median([avg_actual, avg_baseline_method])

            benchmark_rows.append({
                "Metric": metric,
                "Avg. Actuals (Event Periods)": round(avg_actual, 2),
                "Baseline Method": round(avg_baseline_method, 2),
                "Baseline Uplift Expect.": f"{uplift_pct:.2f}%",
                "Proposed Benchmark": round(proposed_benchmark, 2),
            })

        if benchmark_rows:
            benchmark_table = pd.DataFrame(benchmark_rows)
            st.markdown("### ✨ Proposed Benchmark Table")
            st.dataframe(benchmark_table)
            # Append the benchmark sheet to sheets_dict for Excel export
            sheets_dict["Benchmark"] = benchmark_table
            st.session_state["sheets_dict"] = sheets_dict
        else:
            st.info("No complete data to generate benchmark.")

# ────────────────────────────────────────────────────────────────────────────────
# 10) Download Excel (always present, but will include “Benchmark” sheet if generated)
# ────────────────────────────────────────────────────────────────────────────────

if st.session_state.get("scorecard_ready", False):
    sheets_dict = st.session_state["sheets_dict"]
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df_sheet in sheets_dict.items():
            safe_name = sheet_name[:31]
            df_sheet.to_excel(writer, sheet_name=safe_name, index=False)
    buffer.seek(0)

    st.download_button(
        label="📥 Download Full Scorecard Workbook",
        data=buffer,
        file_name="event_marketing_scorecard.xlsx",
        mime="application/vnd.openxmlformats-officedocument-spreadsheetml.sheet",
    )
