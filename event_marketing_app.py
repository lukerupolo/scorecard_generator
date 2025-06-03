# event_marketing_app.py
# -------------------------------------------------------------
# Streamlit – Event Marketing Analytics Suite (w/ Onclusive API + .env Secure Auth)
# -------------------------------------------------------------
pip install python-dotenv
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import os

# Load secrets from .env
load_dotenv()
ONCLUSIVE_CLIENT = os.getenv("ONCLUSIVE_CLIENT")
ONCLUSIVE_USERNAME = os.getenv("ONCLUSIVE_USERNAME")
ONCLUSIVE_PASSWORD = os.getenv("ONCLUSIVE_PASSWORD")

# ---------------------------------------------------------
# API: Fetch Social Mentions Count
# ---------------------------------------------------------
def fetch_social_mentions_count(from_date, to_date, topic_id=None, language='en', query=None):
    url = f"http://social.digimind.com/d/{ONCLUSIVE_CLIENT}/api/mentions"
    headers = {"Accept": "application/json"}
    payload = {
        "dateRangeType": "CUSTOM",
        "fromDate": from_date,
        "toDate": to_date,
        "filter": [f"lang:{language}"]
    }
    if topic_id:
        payload["topic"] = topic_id
    if query:
        payload["query"] = query

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(ONCLUSIVE_USERNAME, ONCLUSIVE_PASSWORD)
        )
        if response.status_code == 200:
            return response.json().get("count", 0)
        else:
            st.warning(f"Onclusive API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.warning(f"Exception during Onclusive API call: {e}")
        return None

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def format_span_labels(event_date: datetime) -> tuple[str, str]:
    b_start = event_date - timedelta(days=7)
    b_end   = event_date - timedelta(days=1)
    a_end   = event_date + timedelta(days=6)
    baseline = f"Baseline {b_start:%Y-%m-%d} → {b_end:%Y-%m-%d}"
    actual   = f"Actual  {event_date:%Y-%m-%d} → {a_end:%Y-%m-%d}"
    return baseline, actual

def generate_event_tables(events, metrics, countries, topic_id=None, language='en', query=None):
    sheets = {}
    for ev in events:
        event_date = ev["date"]
        baseline_col, actual_col = format_span_labels(event_date)

        for country in countries:
            sheet_name = f"{ev['name'][:25] or 'Event'}_{country}"
            sheet_df_data = []

            for metric in metrics:
                baseline_val = None
                actual_val = None

                if metric == "Social Mentions":
                    b_from = (event_date - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                    b_to   = (event_date - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                    a_from = event_date.strftime("%Y-%m-%dT00:00:00Z")
                    a_to   = (event_date + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")
                    baseline_val = fetch_social_mentions_count(b_from, b_to, topic_id, language, query)
                    actual_val = fetch_social_mentions_count(a_from, a_to, topic_id, language, query)

                sheet_df_data.append({
                    "Metric": metric,
                    baseline_col: baseline_val,
                    actual_col: actual_val,
                    "Baseline Method": None
                })

            sheets[sheet_name] = pd.DataFrame(sheet_df_data)

    return sheets

# ---------------------------------------------------------
# Streamlit App UI
# ---------------------------------------------------------
st.set_page_config(page_title="Event Marketing Analytics", layout="wide")
st.markdown("""
# 📊 Event Marketing Analytics Suite

1. **Generate** a tracking template with auto-filled social mentions.
2. **Download**, fill any missing data, then **upload** to get benchmarks.
""", unsafe_allow_html=True)

mode = st.sidebar.radio("Select an action:", ["Generate template", "Final benchmarks"])

if mode == "Generate template":
    st.sidebar.header("Step 1: Configure template")

    n_events = st.sidebar.number_input("Number of events", 1, 20, 1)
    events = []
    for i in range(n_events):
        st.sidebar.subheader(f"Event {i+1}")
        name = st.sidebar.text_input("Name", key=f"name_{i}") or f"Event{i+1}"
        date = st.sidebar.date_input("Start date (T)", key=f"date_{i}")
        events.append({"name": name, "date": datetime.combine(date, datetime.min.time())})

    all_metrics = [
        "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions",
        "Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions"
    ]
    metrics = st.sidebar.multiselect("Metrics to include:", all_metrics, default=["Social Mentions"])
    countries = st.sidebar.multiselect("Regions/Countries:", ["US", "GB", "AU", "FR", "DE"], default=["US", "AU"])

    st.sidebar.markdown("### Onclusive API Filters (for Social Mentions)")
    topic_id = st.sidebar.text_input("Onclusive Topic ID", placeholder="e.g. 336")
    language = st.sidebar.text_input("Language (ISO 639-1)", value="en")
    query = st.sidebar.text_input("Keyword (e.g. Game Title)", placeholder="e.g. SuperGameX")

    if st.sidebar.button("Generate template 📅"):
        if not events or not metrics or not countries:
            st.warning("Please fill in events, metrics, and countries.")
        else:
            with st.spinner("Generating Excel template..."):
                sheets = generate_event_tables(events, metrics, countries,
                                               topic_id=topic_id or None,
                                               language=language or "en",
                                               query=query or None)
                if sheets:
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        for name, df in sheets.items():
                            df.to_excel(writer, sheet_name=name[:31], index=False)
                    buffer.seek(0)
                    st.download_button("Download template workbook",
                                       data=buffer,
                                       file_name="event_marketing_template.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                else:
                    st.warning("No sheets generated. Please check your inputs.")

elif mode == "Final benchmarks":
    st.sidebar.header("Step 2: Upload completed workbook")
    uploaded_file = st.sidebar.file_uploader("Upload Excel workbook", type=["xlsx"])

    if uploaded_file:
        xls = pd.ExcelFile(uploaded_file)
        sheets_all = {sh: pd.read_excel(xls, sh) for sh in xls.sheet_names}
        region_groups = {}

        for name, df in sheets_all.items():
            parts = name.rsplit("_", 1)
            if len(parts) != 2:
                continue
            region_groups.setdefault(parts[1], []).append(df)

        summary = {}
        for region, dfs in region_groups.items():
            if not dfs or dfs[0].empty:
                continue
            metrics_list = dfs[0]["Metric"].tolist()
            data = {"Metric": metrics_list, "Average Actuals": [], "Baseline Method": [], "Baseline Uplift Expect": [], "Proposed Benchmark": []}

            for m in metrics_list:
                acts, meths, uplifts = [], [], []
                for df in dfs:
                    try:
                        b_col, a_col = df.columns[1], df.columns[2]
                        row = df[df["Metric"] == m]
                        base = row[b_col].iloc[0]
                        act = row[a_col].iloc[0]
                        meth = row["Baseline Method"].iloc[0] if "Baseline Method" in row else None
                        if pd.notna(base) and pd.notna(act):
                            uplift = ((act - base) / base * 100) if base != 0 else float("inf") if act > 0 else 0.0
                            uplifts.append(uplift)
                        if pd.notna(act): acts.append(act)
                        if pd.notna(meth): meths.append(meth)
                    except Exception: continue

                data["Average Actuals"].append(np.nanmean(acts) if acts else np.nan)
                data["Baseline Method"].append(np.nanmean(meths) if meths else np.nan)
                data["Baseline Uplift Expect"].append(np.nanmean(uplifts) if uplifts else np.nan)

                values = [v for v in [data["Average Actuals"][-1], data["Baseline Method"][-1]] if pd.notna(v)]
                data["Proposed Benchmark"].append(np.nanmedian(values) if values else np.nan)

            summary[region] = pd.DataFrame(data)

        st.header("Benchmark Summary per Region")
        for region, df in summary.items():
            st.subheader(f"Region: {region}")
            st.dataframe(df)

        summary_buffer = BytesIO()
        with pd.ExcelWriter(summary_buffer, engine='openpyxl') as writer:
            for region, df in summary.items():
                df.to_excel(writer, sheet_name=f"{region}_Summary"[:31], index=False)
        summary_buffer.seek(0)
        st.download_button("Download Benchmark Summary",
                           data=summary_buffer,
                           file_name="event_benchmark_summary.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
