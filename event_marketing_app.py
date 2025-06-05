import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

# ────────────────────────────────────────────────────────────────────────────────
# 1) Helper functions (unchanged)
# ────────────────────────────────────────────────────────────────────────────────

def setup_levelup_headers(api_key: str) -> dict:
    return {
        "accept": "application/json",
        "X-API-KEY": api_key
    }

def fetch_levelup_data(api_headers, brand_id, start_date, end_date, region_code, data_type):
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
        if "hoursWatched" in df.columns:
            df["hoursWatched"] = df["hoursWatched"].astype(float)
    return df

def generate_levelup_metrics_for_event(event, api_headers):
    event_date = event["date"].date()
    baseline_start = (event_date - timedelta(days=30)).strftime("%Y-%m-%d")
    baseline_end   = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
    actual_start   = event_date.strftime("%Y-%m-%d")
    actual_end     = (event_date + timedelta(days=30)).strftime("%Y-%m-%d")

    brand = int(event["brandId"])
    region = event["region"]

    metrics_dfs = {}

    vid_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "videos")
    vid_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "videos")
    if vid_df_baseline is not None and vid_df_actual is not None:
        vid_df_baseline["period"] = "baseline"
        vid_df_actual["period"]   = "actual"
        metrics_dfs["videos"] = pd.concat([vid_df_baseline, vid_df_actual], ignore_index=True)

    str_df_baseline = fetch_levelup_data(api_headers, brand, baseline_start, baseline_end, region, "streams")
    str_df_actual   = fetch_levelup_data(api_headers, brand, actual_start, actual_end, region, "streams")
    if str_df_baseline is not None and str_df_actual is not None:
        str_df_baseline["period"] = "baseline"
        str_df_actual["period"]   = "actual"
        metrics_dfs["streams"] = pd.concat([str_df_baseline, str_df_actual], ignore_index=True)

    return metrics_dfs

def compute_three_month_average(api_headers, brand_id, region, event_date, data_type):
    end_date = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (event_date - timedelta(days=90)).strftime("%Y-%m-%d")
    df = fetch_levelup_data(api_headers, brand_id, start_date, end_date, region, data_type)
    if df is None or df.empty:
        return 0.0

    if data_type == "videos":
        column = "views"
    else:
        column = "hoursWatched" if "hoursWatched" in df.columns else None

    if column and column in df.columns:
        return df[column].mean()
    return 0.0

# ────────────────────────────────────────────────────────────────────────────────
# 2) Streamlit page configuration
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

events = []
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
    default=[]
)

# Clear saved Onclusive state if needed
if "Social Mentions" not in metrics:
    for k in [
        "manual_social_toggle",
        "onclusive_user",
        "onclusive_pw",
        "onclusive_query",
    ]:
        st.session_state.pop(k, None)

# Clear saved LevelUp state if needed
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
manual_social_inputs = {}

if "Social Mentions" in metrics:
    st.sidebar.markdown("## 💬 Social Mentions (Onclusive)")
    st.sidebar.markdown(
        "Enter your Onclusive (Digimind) credentials or skip for manual entry."
    )

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
        if onclusive_username and onclusive_password and onclusive_query:
            st.sidebar.write("🔍 Testing Onclusive credentials…")
            test_count = fetch_social_mentions_count(
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                onclusive_username,
                onclusive_password,
                onclusive_language,
                onclusive_query,
            )
            if test_count is not None:
                st.sidebar.success("✅ Onclusive login OK")
            else:
                st.sidebar.error("❌ Onclusive login failed")
    st.sidebar.markdown("---")

# ────────────────────────────────────────────────────────────────────────────────
# 6) Sidebar: LevelUp (Video/Streams) Authentication
# ────────────────────────────────────────────────────────────────────────────────

levelup_api_key = None
api_headers = None
manual_levelup_inputs = {}

if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.sidebar.markdown("## 🎮 LevelUp API")
    st.sidebar.markdown(
        "If you want to fetch Video Views or Hours Watched automatically, paste your LevelUp API Key below. "
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
                manual_levelup_inputs[idx] = manual_levelup_inputs.get(idx, {})
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
                manual_levelup_inputs[idx] = manual_levelup_inputs.get(idx, {})
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

    # 8.2 Build and display one table per event
    sheets_dict = {}
    for idx, ev in enumerate(events):
        ev_date = ev["date"].date()
        baseline_start = ev_date - timedelta(days=30)
        baseline_end   = ev_date - timedelta(days=1)
        actual_start   = ev_date
        actual_end     = ev_date + timedelta(days=30)

        baseline_label = f"Baseline  {baseline_start:%Y-%m-%d} → {baseline_end:%Y-%m-%d}"
        actual_label   = f"Actual    {actual_start:%Y-%m-%d} → {actual_end:%Y-%m-%d}"
        avg_label      = "Baseline Method (3 months)"

        needs_levelup = any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics)
        fetched = {}
        if needs_levelup and not (manual_levelup_inputs and idx in manual_levelup_inputs):
            fetched = generate_levelup_metrics_for_event(ev, api_headers)

        rows_for_event = []
        for metric_name in metrics:
            row = {
                "Metric": metric_name,
                baseline_label: None,
                actual_label: None,
                avg_label: None,
            }

            # Social Mentions
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

            # Video Views (VOD)
            elif metric_name == "Video Views (VOD)":
                if idx in manual_levelup_inputs and "Video Views (VOD)" in manual_levelup_inputs[idx]:
                    base_vv, act_vv = manual_levelup_inputs[idx]["Video Views (VOD)"]
                    row[baseline_label] = base_vv
                    row[actual_label]   = act_vv
                else:
                    vid_df = fetched.get("videos", pd.DataFrame())
                    if not vid_df.empty and "period" in vid_df.columns and "views" in vid_df.columns:
                        bv = vid_df[vid_df["period"] == "baseline"]["views"].sum()
                        av = vid_df[vid_df["period"] == "actual"]["views"].sum()
                    else:
                        bv, av = 0, 0
                    row[baseline_label] = bv
                    row[actual_label]   = av

                avg_vv = compute_three_month_average(api_headers, ev["brandId"], ev["region"], ev_date, "videos")
                row[avg_label] = round(avg_vv, 2)

            # Hours Watched (Streams)
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

                avg_hw = compute_three_month_average(api_headers, ev["brandId"], ev["region"], ev_date, "streams")
                row[avg_label] = round(avg_hw, 2)

            # Other metrics placeholders
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

    # Write all event‐tables to Excel
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df_event in sheets_dict.items():
            safe_name = sheet_name[:31]
            df_event.to_excel(writer, sheet_name=safe_name, index=False)
    buffer.seek(0)

    st.download_button(
        label="📥 Download Full Scorecard Workbook",
        data=buffer,
        file_name="event_marketing_scorecard.xlsx",
        mime="application/vnd.openxmlformats-officedocument-spreadsheetml.sheet",
    )
