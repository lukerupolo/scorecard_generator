# event_marketing_app.py
# -------------------------------------------------------------
# Streamlit – Event Marketing Analytics Suite
# • Onclusive API (Digimind) for Social Mentions
# • LevelUp Analytics via Device-Code Flow (Google SSO)
# -------------------------------------------------------------

import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from io import BytesIO

import msal

# ---------------------------------------------------------
# LevelUp (Azure AD) configuration for Device-Code Flow
# ---------------------------------------------------------
# NOTE: These values are hard-coded so you can paste this into GitHub directly.
#       Users will authenticate via Google SSO when prompted by the device-code flow.
TENANT_ID = "cc74fc12-4142-400e-a653-f98bfa4b03ba"
CLIENT_ID = "009029d5-8095-4561-b513-eaa0eb10767c"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = [f"api://{CLIENT_ID}/.default"]  # scope to match LevelUp API

# ---------------------------------------------------------
# Acquire a LevelUp access token via Device-Code Flow
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def acquire_levelup_token_device_flow() -> str | None:
    """
    Runs MSAL Device-Code Flow. Users will see a code + URL to open. They sign in via Google SSO there.
    Returns a valid access_token (JWT) or None if it fails.
    """
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    flow = app.initiate_device_flow(scopes=SCOPE)
    if "user_code" not in flow:
        st.error("Failed to start LevelUp device‐code flow. Check CLIENT_ID and TENANT_ID.")
        return None

    # Prompt user to do the device‐code login
    st.info(
        "**LevelUp Login Required**\n\n"
        "1. Open in a new tab:\n\n    **" + flow["verification_uri"] + "**\n\n"
        "2. Enter the code:\n\n    **" + flow["user_code"] + "**\n\n"
        "3. Complete Google/Corporate sign-in.\n"
        "4. Return here once you have signed in successfully."
    )

    result = app.acquire_token_by_device_flow(flow)  # This will block until user completes or times out
    if "access_token" in result:
        return result["access_token"]
    else:
        st.error(f"LevelUp login failed: {result.get('error_description', 'No error description')}")
        return None


# ---------------------------------------------------------
# LevelUp API helper
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
    Returns JSON containing at least 'brandMetrics' with 'hours_watched' and 'videosViews'.
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
        "id": "1748835037495",  # unique request ID (e.g. timestamp)
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
# Onclusive (Digimind) API helper
# ---------------------------------------------------------
def fetch_social_mentions_count(
    from_date: str,
    to_date: str,
    username: str,
    password: str,
    language: str = "en",
    query: str = None,
) -> int | None:
    """
    Calls Digimind’s mentions endpoint (Onclusive) and returns the count.
    """
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
            st.warning(f"Digimind API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.warning(f"Digimind request failed: {e}")
        return None


# ---------------------------------------------------------
# Helper: Format date‐span column labels
# ---------------------------------------------------------
def format_span_labels(event_date: datetime) -> tuple[str, str]:
    b_start = event_date - timedelta(days=7)
    b_end = event_date - timedelta(days=1)
    a_end = event_date + timedelta(days=6)
    baseline = f"Baseline {b_start:%Y-%m-%d} → {b_end:%Y-%m-%d}"
    actual = f"Actual  {event_date:%Y-%m-%d} → {a_end:%Y-%m-%d}"
    return baseline, actual


# ---------------------------------------------------------
# Generate one sheet per (event × country)
# ---------------------------------------------------------
def generate_event_tables(
    events: list[dict],
    metrics: list[str],
    countries: list[str],
    onclusive_username: str,
    onclusive_password: str,
    region: str,
    onclusive_language: str,
    onclusive_query: str,
) -> dict[str, pd.DataFrame]:
    """
    Builds a dict of DataFrames keyed by sheet name (event_name_region).
    For each event:
      • If “Social Mentions” in metrics → call Digimind
      • If “Video Views (VOD)” or “Hours Watched (Streams)” in metrics → call LevelUp
    """
    sheets: dict[str, pd.DataFrame] = {}

    # 1) Acquire a LevelUp access token via Device-Code Flow
    jwt_token = acquire_levelup_token_device_flow()
    if not jwt_token:
        st.error("LevelUp authentication failed. Cannot fetch metrics.")
        return {}

    for ev in events:
        baseline_col, actual_col = format_span_labels(ev["date"])
        sheet_rows = []

        for metric in metrics:
            baseline_val = None
            actual_val = None

            # Digimind: Social Mentions
            if metric == "Social Mentions" and onclusive_username and onclusive_password:
                b_from = (ev["date"] - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                b_to = (ev["date"] - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                a_from = ev["date"].strftime("%Y-%m-%dT00:00:00Z")
                a_to = (ev["date"] + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")
                baseline_val = fetch_social_mentions_count(
                    b_from, b_to, onclusive_username, onclusive_password, onclusive_language, onclusive_query
                )
                actual_val = fetch_social_mentions_count(
                    a_from, a_to, onclusive_username, onclusive_password, onclusive_language, onclusive_query
                )

            # LevelUp: Video Views or Hours Watched
            elif metric in ["Video Views (VOD)", "Hours Watched (Streams)"]:
                brand_id = ev.get("brandId", "")
                if brand_id:
                    b_from = (ev["date"] - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                    b_to = (ev["date"] - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                    a_from = ev["date"].strftime("%Y-%m-%dT00:00:00Z")
                    a_to = (ev["date"] + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")

                    baseline_json = fetch_levelup_evolution_metrics(
                        brand_id, b_from, b_to, region, jwt_token
                    )
                    actual_json = fetch_levelup_evolution_metrics(
                        brand_id, a_from, a_to, region, jwt_token
                    )

                    def extract_kpi(data_json: dict, kpi_key: str):
                        arr = data_json.get("brandMetrics", [])
                        for entry in arr:
                            if str(entry.get("brandId")) == str(brand_id):
                                return entry.get(kpi_key)
                        return None

                    if metric == "Video Views (VOD)":
                        baseline_val = extract_kpi(baseline_json, "videosViews")
                        actual_val = extract_kpi(actual_json, "videosViews")
                    else:  # Hours Watched (Streams)
                        baseline_val = extract_kpi(baseline_json, "hours_watched")
                        actual_val = extract_kpi(actual_json, "hours_watched")

            sheet_rows.append(
                {
                    "Metric": metric,
                    baseline_col: baseline_val,
                    actual_col: actual_val,
                    "Baseline Method": None,
                }
            )

        df = pd.DataFrame(sheet_rows)
        for country in countries:
            sheet_name = f"{ev['name'][:25]}_{country}"
            sheets[sheet_name] = df.copy()

    return sheets


# ---------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------
st.set_page_config(page_title="Event Marketing Analytics", layout="wide")
st.markdown(
    """
# 📊 Event Marketing Analytics Suite

This tool lets you:
1. Generate a template to track events.
2. Auto-populate **Social Mentions**, **Video Views (VOD)**, and **Hours Watched (Streams)**.
""",
    unsafe_allow_html=True,
)

# -- Sidebar: Onclusive (Digimind) Login --
st.sidebar.header("🔐 Onclusive API Login")
onclusive_username = st.sidebar.text_input("Onclusive Username", placeholder="you@example.com")
onclusive_password = st.sidebar.text_input("Onclusive Password", type="password")
onclusive_language = st.sidebar.text_input("Language", value="en")
onclusive_query = st.sidebar.text_input("Search Keywords", placeholder="e.g. FIFA, EA Sports")

if onclusive_username and onclusive_password:
    st.sidebar.write("🔍 Testing Digimind login…")
    test_count = fetch_social_mentions_count(
        "2024-01-01T00:00:00Z",
        "2024-01-02T00:00:00Z",
        onclusive_username,
        onclusive_password,
        onclusive_language,
        "test",
    )
    if test_count is not None:
        st.sidebar.success("✅ Digimind login successful!")
    else:
        st.sidebar.error("❌ Digimind login failed.")

# -- Sidebar: LevelUp info (Device-Code Flow) --
st.sidebar.header("🎮 LevelUp Device-Code Login")
st.sidebar.markdown(
    """
Click “Generate template” below and you will be prompted to sign in to LevelUp:
1. You’ll see a URL + code here.
2. Open the URL, enter the code, complete Google SSO.
3. Return here—your LevelUp metrics will populate automatically.
"""
)

mode = st.sidebar.radio("Mode:", ["Generate template", "Test LevelUp only"])

if mode == "Generate template":
    st.sidebar.subheader("Step 1: Configure Events")
    n_events = st.sidebar.number_input("Number of events", 1, 10, 1)
    events: list[dict] = []
    for i in range(n_events):
        st.sidebar.markdown(f"**Event {i+1}**")
        name = st.sidebar.text_input(f"Name for Event {i+1}", key=f"name_{i}") or f"Event{i+1}"
        date = st.sidebar.date_input(f"Date for Event {i+1}", key=f"date_{i}")
        brand_id = st.sidebar.text_input(
            f"LevelUp Brand ID (Event {i+1})", key=f"brand_{i}", value="3136"
        )
        events.append(
            {
                "name": name,
                "date": datetime.combine(date, datetime.min.time()),
                "brandId": brand_id,
            }
        )

    metrics = st.sidebar.multiselect(
        "Select metrics:",
        [
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
        ],
        default=["Social Mentions", "Video Views (VOD)", "Hours Watched (Streams)"],
    )
    countries = st.sidebar.multiselect(
        "Select regions:",
        ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"],
        default=["US", "GB"],
    )

    if st.sidebar.button("Generate template"):
        # Validate Digimind fields if needed
        if "Social Mentions" in metrics and (not onclusive_username or not onclusive_password or not onclusive_query):
            st.warning("Please enter Digimind credentials and Search Keywords for Social Mentions.")
        else:
            with st.spinner("Generating Excel workbook…"):
                sheets = generate_event_tables(
                    events,
                    metrics,
                    countries,
                    onclusive_username,
                    onclusive_password,
                    region="TH",  # change if you want a sidebar region input
                    onclusive_language=onclusive_language,
                    onclusive_query=onclusive_query,
                )
                if not sheets:
                    st.stop()  # an error was shown inside generate_event_tables
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    for sheet_name, df in sheets.items():
                        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                buffer.seek(0)
                st.download_button(
                    "📥 Download Event Template",
                    data=buffer,
                    file_name="event_marketing_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

elif mode == "Test LevelUp only":
    st.header("📈 LevelUp Test: Video Views & Hours Watched")
    st.markdown("Use this to verify your LevelUp device-code login and see raw results.")

    test_brand = st.text_input("Brand ID", value="3136")
    from_date = st.date_input("From (YYYY-MM-DD)", value=datetime.today() - timedelta(days=7))
    to_date = st.date_input("To (YYYY-MM-DD)", value=datetime.today())
    region_code = st.text_input("Region Code", value="TH")

    if st.button("Fetch LevelUp Data"):
        jwt = acquire_levelup_token_device_flow()
        if not jwt:
            st.error("LevelUp login/authorization failed.")
        else:
            b_from = f"{from_date:%Y-%m-%dT00:00:00Z}"
            b_to = f"{to_date:%Y-%m-%dT23:59:59Z}"
            resp = fetch_levelup_evolution_metrics(test_brand, b_from, b_to, region_code, jwt)
            arr = resp.get("brandMetrics", [])
            entry = next((x for x in arr if str(x.get("brandId")) == test_brand), None)
            if entry:
                st.subheader(f"Brand {test_brand} Metrics ({from_date} → {to_date})")
                st.write("• Video Views (VOD):", entry.get("videosViews", "N/A"))
                st.write("• Hours Watched (Streams):", entry.get("hours_watched", "N/A"))
            else:
                st.warning("No data returned for that Brand ID in the given range.")
