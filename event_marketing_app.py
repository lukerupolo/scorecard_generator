# event_marketing_app.py
# -------------------------------------------------------------
# Streamlit – Event Marketing Analytics Suite (Onclusive + LevelUp Login)
# -------------------------------------------------------------

import streamlit as st
import pandas as pd
import numpy as np
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from io import BytesIO

import msal  # <--- newly added

# ---------------------------------------------------------
# Azure AD / LevelUp OAuth Configuration
# ---------------------------------------------------------
AUTHORITY = "https://login.microsoftonline.com/cc74fc12-4142-400e-a653-f98bfa4b03ba"
CLIENT_ID = "009029d5-8095-4561-b513-eaa0eb10767c"
SCOPE = [f"api://{CLIENT_ID}/.default"]


def acquire_levelup_token(username: str, password: str) -> str:
    """
    Exchange Streamlit user credentials (username, password) for an Azure AD access token (JWT).
    Returns the access_token string on success, or None if login fails.
    """
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    result = app.acquire_token_by_username_password(
        username=username,
        password=password,
        scopes=SCOPE,
    )
    if "access_token" in result:
        return result["access_token"]
    else:
        # Print/log the error:
        st.error(f"LevelUp login failed: {result.get('error_description')}")
        return None


# ---------------------------------------------------------
# LevelUp API Functions (unchanged from previous example)
# ---------------------------------------------------------
def fetch_levelup_evolution_metrics(
    brand_id: str,
    date_from: str,
    date_to: str,
    region: str,
    jwt_token: str,
    chart_id: str = "c40d6125dcd3b137ab3cb6cb1c859e0320d62b66_1748993752143",
) -> dict:
    """
    Calls the SocialPagesEvolution endpoint for a single brand_id over a date range.
    Returns JSON that includes hours_watched and videosViews.
    """
    url = f"https://app.levelup-analytics.com/api/v1/report/chart/SocialPagesEvolution/{chart_id}"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/json",
    }

    params = {
        "brandIds": brand_id,
        "dateFrom": date_from,
        "dateTo": date_to,
        "regions": region,
        "id": "1748835037495",
        "options[broadcaster]": "all",
        "options[itemsMaxNum]": "10000",
        "options[mobileFilter]": "only",
        "options[post_platforms]": "Facebook,Twitter,Instagram,Vk,Steam,Youtube,Discord,Threads",
        "options[sponsoredFilter]": "all",
        "options[video_platforms]": "Youtube,TikTok,Facebook,Twitter,Instagram,Vk",
        "options[streaming_platforms]": "Twitch,Youtube,Facebook,TikTok,Kick",
        "options[merged_platforms]": "Facebook,Twitter,Instagram,Vk,Steam,Youtube,Discord,Threads,TikTok,Twitch,Kick",
        "options[kpis]": "hours_watched,videosViews",
        "options[getHistory]": "false",
    }

    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        st.error(f"LevelUp API error {resp.status_code}: {resp.text}")
        return {}
    return resp.json()


# ---------------------------------------------------------
# Onclusive API (unchanged)
# ---------------------------------------------------------
def fetch_social_mentions_count(
    from_date, to_date, username, password, language="en", query=None
):
    url = "https://social.digimind.com/d/gd2/api/mentions"
    headers = {"Accept": "application/json"}
    payload = {
        "dateRangeType": "CUSTOM",
        "fromDate": from_date,
        "toDate": to_date,
        "filter": [f"lang:{language}"],
    }
    if query:
        payload["query"] = query

    try:
        response = requests.post(
            url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)
        )
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
# Generate event template tables (extended with LevelUp)
# ---------------------------------------------------------
def generate_event_tables(
    events,
    metrics,
    countries,
    username,
    password,
    levelup_username,
    levelup_password,
    language="en",
    query=None,
    region="US",
):
    """
    Builds one sheet per (event × country) with rows for each selected metric.
    If metric == "Social Mentions", calls Onclusive.
    If metric in [Video Views, Hours Watched], first logs in to LevelUp (ROPC), then fetches each range.
    """
    sheets = {}

    # Acquire a LevelUp token once (instead of asking user to paste a JWT)
    jwt_token = acquire_levelup_token(levelup_username, levelup_password)
    if not jwt_token:
        st.error("Could not obtain LevelUp access token. Check your LevelUp credentials.")
        return {}

    for ev in events:
        baseline_col, actual_col = format_span_labels(ev["date"])
        sheet_df_data = []

        for metric in metrics:
            baseline_val, actual_val = None, None

            # ONCLUSIVE: Social Mentions
            if metric == "Social Mentions" and username and password:
                b_from = (ev["date"] - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                b_to = (ev["date"] - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                a_from = ev["date"].strftime("%Y-%m-%dT00:00:00Z")
                a_to = (ev["date"] + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")
                baseline_val = fetch_social_mentions_count(
                    b_from, b_to, username, password, language, query
                )
                actual_val = fetch_social_mentions_count(
                    a_from, a_to, username, password, language, query
                )

            # LEVELUP: Video Views or Hours Watched
            elif metric in ["Video Views (VOD)", "Hours Watched (Streams)"]:
                brand_id = ev.get("brandId", None)
                if not brand_id:
                    baseline_val = actual_val = None
                else:
                    b_from = (ev["date"] - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                    b_to = (ev["date"] - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                    a_from = ev["date"].strftime("%Y-%m-%dT00:00:00Z")
                    a_to = (ev["date"] + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")

                    baseline_data = fetch_levelup_evolution_metrics(
                        brand_id, b_from, b_to, region, jwt_token
                    )
                    actual_data = fetch_levelup_evolution_metrics(
                        brand_id, a_from, a_to, region, jwt_token
                    )

                    def extract_kpi(data_json, kpi_key):
                        try:
                            arr = data_json.get("brandMetrics", [])
                            for entry in arr:
                                if int(entry.get("brandId", -1)) == int(brand_id):
                                    return entry.get(kpi_key, None)
                        except Exception:
                            return None
                        return None

                    if metric == "Video Views (VOD)":
                        baseline_val = extract_kpi(baseline_data, "videosViews")
                        actual_val = extract_kpi(actual_data, "videosViews")
                    else:  # "Hours Watched (Streams)"
                        baseline_val = extract_kpi(baseline_data, "hours_watched")
                        actual_val = extract_kpi(actual_data, "hours_watched")

            sheet_df_data.append(
                {
                    "Metric": metric,
                    baseline_col: baseline_val,
                    actual_col: actual_val,
                    "Baseline Method": None,
                }
            )

        template_df = pd.DataFrame(sheet_df_data)

        for country in countries:
            sheet_name = f"{ev['name'][:25]}_{country}"
            sheets[sheet_name] = template_df.copy()

    return sheets


# ---------------------------------------------------------
# Streamlit App UI
# ---------------------------------------------------------
st.set_page_config(page_title="Event Marketing Analytics", layout="wide")
st.markdown(
    """
# 📊 Event Marketing Analytics Suite
This tool helps you:
1. Generate a workbook template to track events.
2. Automatically fill in social mention data.
3. Compute benchmarks by uploading filled workbooks.
""",
    unsafe_allow_html=True,
)

# Sidebar: Onclusive Login
st.sidebar.header("🔐 Onclusive API Login")
username = st.sidebar.text_input("Onclusive Username", placeholder="you@example.com")
password = st.sidebar.text_input("Onclusive Password", type="password")
language = st.sidebar.text_input("Language", value="en")
query = st.sidebar.text_input("Search Keywords", placeholder="e.g. FIFA, EA Sports")

if username and password:
    st.sidebar.write("🔍 Testing Onclusive login...")
    test_result = fetch_social_mentions_count(
        "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z", username, password, language, "test"
    )
    if test_result is not None:
        st.sidebar.success("✅ Onclusive Login successful!")
    else:
        st.sidebar.error("❌ Onclusive login failed.")

# Sidebar: LevelUp Login
st.sidebar.header("🎮 LevelUp API Login (OAuth)")
levelup_username = st.sidebar.text_input("LevelUp Username", placeholder="you@ea.com")
levelup_password = st.sidebar.text_input("LevelUp Password", type="password")
# If you want, you can hide the ROPC fields unless they check “Use LevelUp Metrics”
use_levelup = st.sidebar.checkbox("Use LevelUp Metrics", value=False)

mode = st.sidebar.radio("Choose mode:", ["Generate template", "Standalone LevelUp test"])

if mode == "Generate template":
    st.sidebar.subheader("Step 1: Configure template")
    n_events = st.sidebar.number_input("Number of events", 1, 10, 1)
    events = []
    for i in range(n_events):
        st.sidebar.markdown(f"**Event {i+1}**")
        name = st.sidebar.text_input(f"Event name {i+1}", key=f"name_{i}") or f"Event{i+1}"
        date = st.sidebar.date_input(f"Event date {i+1}", key=f"date_{i}")
        # We’ll let users specify a brandId per event or default to 3136 if blank
        brand_id = st.sidebar.text_input(
            f"Brand ID for Event {i+1}", key=f"brand_{i}", value="3136"
        )
        events.append(
            {
                "name": name,
                "date": datetime.combine(date, datetime.min.time()),
                "brandId": brand_id,
            }
        )

    metrics_choices = [
        "Sessions",
        "DAU",
        "Revenue",
        "Installs",
        "Retention",
        "Watch Time",
        "ARPU",
        "Conversions",
        "Video Views (VOD)",
        "Hours Watched (Streams)",
        "Social Mentions",
        "Search Index",
        "PCCV",
        "AMA",
    ]
    metrics = st.sidebar.multiselect("Select metrics:", metrics_choices, default=["Social Mentions"])
    countries = st.sidebar.multiselect(
        "Select regions:", ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"], default=["US", "GB"]
    )

    if st.sidebar.button("Generate template"):
        # Validation
        if not username or not password:
            st.warning("Please enter your Onclusive credentials.")
        elif "Social Mentions" in metrics and not query:
            st.warning("Please supply Search Keywords for Social Mentions.")
        elif use_levelup and (not levelup_username or not levelup_password):
            st.warning("Please enter your LevelUp username/password to pull Video/Watch data.")
        else:
            with st.spinner("Generating Excel workbook..."):
                sheets = generate_event_tables(
                    events,
                    metrics,
                    countries,
                    username,
                    password,
                    levelup_username if use_levelup else "",
                    levelup_password if use_levelup else "",
                    language,
                    query,
                    region="TH",  # you can also expose region in UI if needed
                )
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    for name, df in sheets.items():
                        df.to_excel(writer, sheet_name=name[:31], index=False)
                buffer.seek(0)
                st.download_button(
                    "📥 Download Workbook",
                    data=buffer,
                    file_name="event_marketing_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

elif mode == "Standalone LevelUp test":
    st.header("📈 Fetch LevelUp Video Views & Hours Watched")
    st.markdown("Enter LevelUp credentials and date range → click Fetch.")

    b_brand = st.text_input("Brand ID", value="3136")
    from_date = st.date_input("From (YYYY-MM-DD)", value=datetime.today() - timedelta(days=7))
    to_date = st.date_input("To (YYYY-MM-DD)", value=datetime.today())
    chosen_region = st.text_input("Region Code", value="TH")

    if st.button("Fetch LevelUp data"):
        if not levelup_username or not levelup_password:
            st.error("⚠️ Please enter LevelUp username + password.")
        else:
            # Acquire token via MSAL ROPC
            jwt = acquire_levelup_token(levelup_username, levelup_password)
            if not jwt:
                st.error("LevelUp login failed. Check credentials or ROPC restrictions.")
            else:
                b_from = f"{from_date:%Y-%m-%dT00:00:00Z}"
                b_to = f"{to_date:%Y-%m-%dT23:59:59Z}"
                data = fetch_levelup_evolution_metrics(b_brand, b_from, b_to, chosen_region, jwt)
                if data:
                    arr = data.get("brandMetrics", [])
                    entry = next((x for x in arr if str(x.get("brandId")) == b_brand), None)
                    if entry:
                        st.subheader(f"Brand {b_brand} Metrics")
                        st.write("• Video Views:", entry.get("videosViews", "N/A"))
                        st.write("• Hours Watched:", entry.get("hours_watched", "N/A"))
                    else:
                        st.warning("No data for that Brand ID in the given range.")

# ---------------------------------------------------------
# End of Streamlit app
# ---------------------------------------------------------
