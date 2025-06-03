# event_marketing_app.py
# -------------------------------------------------------------
# Streamlit – Event Marketing Analytics Suite (with Onclusive API Login)
# -------------------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from io import BytesIO

# ---------------------------------------------------------
# API Function
# ---------------------------------------------------------
def fetch_social_mentions_count(from_date, to_date, username, password, language='en', query=None):
    url = "https://social.digimind.com/d/gd2/api/mentions"
    headers = {"Accept": "application/json"}
    payload = {
        "dateRangeType": "CUSTOM",
        "fromDate": from_date,
        "toDate": to_date,
        "filter": [f"lang:{language}"]
    }
    if query:
        payload["query"] = query

    try:
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password))
        if response.status_code == 200:
            return response.json().get("count", 0)
        else:
            st.warning(f"API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.warning(f"API request failed: {e}")
        return None

# ---------------------------------------------------------
# Format date span labels
# ---------------------------------------------------------
def format_span_labels(event_date):
    b_start = event_date - timedelta(days=7)
    b_end = event_date - timedelta(days=1)
    a_end = event_date + timedelta(days=6)
    baseline = f"Baseline {b_start:%Y-%m-%d} → {b_end:%Y-%m-%d}"
    actual = f"Actual  {event_date:%Y-%m-%d} → {a_end:%Y-%m-%d}"
    return baseline, actual

# ---------------------------------------------------------
# Generate event template tables
# ---------------------------------------------------------
def generate_event_tables(events, metrics, countries, username, password, language='en', query=None):
    sheets = {}

    for ev in events:
        baseline_col, actual_col = format_span_labels(ev["date"])

        sheet_df_data = []
        for metric in metrics:
            baseline_val, actual_val = None, None

            if metric == "Social Mentions" and username and password:
                b_from = (ev["date"] - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                b_to   = (ev["date"] - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                a_from = ev["date"].strftime("%Y-%m-%dT00:00:00Z")
                a_to   = (ev["date"] + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")
                baseline_val = fetch_social_mentions_count(b_from, b_to, username, password, language, query)
                actual_val   = fetch_social_mentions_count(a_from, a_to, username, password, language, query)

            sheet_df_data.append({
                "Metric": metric,
                baseline_col: baseline_val,
                actual_col: actual_val,
                "Baseline Method": None
            })

        template_df = pd.DataFrame(sheet_df_data)

        for country in countries:
            sheet_name = f"{ev['name'][:25]}_{country}"
            sheets[sheet_name] = template_df.copy()

    return sheets

# ---------------------------------------------------------
# Streamlit App UI
# ---------------------------------------------------------
st.set_page_config(page_title="Event Marketing Analytics", layout="wide")
st.markdown("""
# 📊 Event Marketing Analytics Suite
This tool helps you:
1. Generate a workbook template to track events.
2. Automatically fill in social mention data.
3. Compute benchmarks by uploading filled workbooks.
""", unsafe_allow_html=True)

# Sidebar Login Section
st.sidebar.header("🔐 Onclusive API Login")
username = st.sidebar.text_input("Username", placeholder="you@example.com")
password = st.sidebar.text_input("Password", type="password")
language = st.sidebar.text_input("Language", value="en")
query = st.sidebar.text_input("Search Keywords", placeholder="e.g. FIFA, EA Sports")

# Login test
if username and password:
    st.sidebar.write("🔍 Testing API login...")
    test_result = fetch_social_mentions_count(
        "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z",
        username=username, password=password, language=language, query="test"
    )
    if test_result is not None:
        st.sidebar.success("✅ Login successful!")
    else:
        st.sidebar.error("❌ Login failed. Check credentials.")

mode = st.sidebar.radio("Choose mode:", ["Generate template", "Final benchmarks"])

if mode == "Generate template":
    st.sidebar.subheader("Step 1: Configure template")
    n_events = st.sidebar.number_input("Number of events", 1, 10, 1)
    events = []
    for i in range(n_events):
        st.sidebar.markdown(f"**Event {i+1}**")
        name = st.sidebar.text_input(f"Event name {i+1}", key=f"name_{i}") or f"Event{i+1}"
        date = st.sidebar.date_input(f"Event date {i+1}", key=f"date_{i}")
        events.append({"name": name, "date": datetime.combine(date, datetime.min.time())})

    metrics = st.sidebar.multiselect("Select metrics:", [
        "Sessions", "DAU", "Revenue", "Installs",
        "Retention", "Watch Time", "ARPU", "Conversions",
        "Video Views (VOD)", "Hours Watched (Streams)",
        "Social Mentions", "Search Index", "PCCV", "AMA"
    ], default=["Social Mentions"])

    countries = st.sidebar.multiselect("Select regions:", [
        "US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"
    ], default=["US", "GB"])

    if st.sidebar.button("Generate template"):
        if not username or not password:
            st.warning("Please enter your API credentials.")
        elif not query:
            st.warning("Please enter search keywords.")
        else:
            with st.spinner("Generating Excel workbook..."):
                sheets = generate_event_tables(events, metrics, countries, username, password, language, query)
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    for name, df in sheets.items():
                        df.to_excel(writer, sheet_name=name[:31], index=False)
                buffer.seek(0)
                st.download_button("📥 Download Workbook", data=buffer, file_name="event_marketing_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
