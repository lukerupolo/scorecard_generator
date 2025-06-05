# event_marketing_app.py
# -------------------------------------------------------------
# Streamlit – Event Marketing Analytics Suite (Modified UI)
# • Onclusive (Digimind) for Social Mentions (Basic-Auth or manual)
# • LevelUp Analytics via Device-Code (Google SSO) → JWT or manual
# -------------------------------------------------------------

import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from io import BytesIO
import msal

#
# ─── 1) LevelUp (AAD) CONFIGURATION ─────────────────────────
#
import os

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
AUTHORITY = os.getenv("AUTHORITY") or f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = [f"api://{CLIENT_ID}/.default"]   # must match the LevelUp API’s “default scope”

#
# ─── 2) Acquire LevelUp JWT via Device-Code (Google SSO) ────
#
@st.cache_data(show_spinner=False)
def get_levelup_jwt() -> str | None:
    """
    Launches MSAL Device-Code flow. Shows the user a code + URL. They go to that URL,
    pick “Sign in with Google,” confirm corporate login, and then MSAL returns a JWT.
    """
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    flow = app.initiate_device_flow(scopes=SCOPE)

    if "user_code" not in flow:
        st.error("⚠️ Failed to initiate LevelUp Device-Code flow. Check CLIENT_ID / TENANT_ID.")
        return None

    st.info(
        "**LevelUp Login Required**\n\n"
        "1. Open a new browser tab and visit:\n\n"
        f"    👉 **{flow['verification_uri']}**\n\n"
        "2. Enter this code:\n\n"
        f"    👉 **{flow['user_code']}**\n\n"
        "3. Choose your Google/Corporate account (e.g. `you@ea.com`).\n"
        "4. Once you see the “Success” message there, return here."
    )

    result = app.acquire_token_by_device_flow(flow)  # blocks until you finish SSO or timeout
    if "access_token" in result:
        return result["access_token"]
    else:
        st.error(f"❌ LevelUp login failed:\n  {result.get('error_description', 'no description')}")
        return None


#
# ─── 3) Digimind / Onclusive “Social Mentions” ───────────────
#
def fetch_social_mentions_count(
    from_date: str,
    to_date: str,
    username: str,
    password: str,
    language: str = "en",
    query: str = None,
) -> int | None:
    """
    Calls Digimind’s /mentions endpoint (Onclusive).
    Returns `count` (int) or None on error.
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
        resp = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(username, password),
        )
        if resp.status_code == 200:
            return resp.json().get("count", 0)
        else:
            st.warning(f"Onclusive error {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        st.warning(f"Onclusive request failed: {e}")
        return None


#
# ─── 4) LevelUp “SocialPagesEvolution” ───────────────────────
#
def fetch_levelup_evolution_metrics(
    brand_id: str,
    date_from: str,
    date_to: str,
    region: str,
    jwt_token: str,
    chart_id: str = "c40d6125dcd3b137ab3cb6cb1c859e0320d62b66_1748993752143",
) -> dict:
    """
    Calls LevelUp’s SocialPagesEvolution via GET + Bearer <jwt_token>.
    Returns a JSON dict containing “brandMetrics,” including “hours_watched” and “videosViews.”
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
        "id": "1748835037495",  # some unique request ID (e.g. fixed or timestamp)
        # ───────────────────────────────────────────────────────────────────────
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
        st.error(f"LevelUp error {resp.status_code}: {resp.text}")
        return {}
    return resp.json()


#
# ─── 5) Helper: Format column labels for Baseline vs. Actual spans ───
#
def format_span_labels(event_date: datetime) -> tuple[str, str]:
    b_start = event_date - timedelta(days=7)
    b_end = event_date - timedelta(days=1)
    a_end = event_date + timedelta(days=6)
    baseline_label = f"Baseline {b_start:%Y-%m-%d} → {b_end:%Y-%m-%d}"
    actual_label = f"Actual  {event_date:%Y-%m-%d} → {a_end:%Y-%m-%d}"
    return baseline_label, actual_label


#
# ─── 6) Build DataFrames for each (Event × Region) ───────────────────
#
def generate_event_tables(
    events: list[dict],
    metrics: list[str],
    regions: list[str],
    # Onclusive inputs:
    onclusive_user: str | None,
    onclusive_pw: str | None,
    onclusive_lang: str,
    onclusive_query: str | None,
    manual_social_inputs: dict[int, tuple[int, int]],
    # LevelUp inputs:
    levelup_jwt: str | None,
    manual_levelup_inputs: dict[int, dict[str, tuple[int, int]]],
) -> dict[str, pd.DataFrame]:
    """
    Loops over each event:
      • If “Social Mentions” is selected → either use Digimind OR manual inputs
      • If “Video Views (VOD)” or “Hours Watched (Streams)” is selected → either use LevelUp OR manual inputs
    Returns a dict of DataFrames keyed by sheet_name = f"{event_name[:25]}_{region}".
    """
    sheets: dict[str, pd.DataFrame] = {}

    for idx, ev in enumerate(events):
        baseline_col, actual_col = format_span_labels(ev["date"])
        rows = []

        for metric in metrics:
            baseline_val = None
            actual_val = None

            # — Manual Social Mentions override —
            if metric == "Social Mentions":
                if idx in manual_social_inputs:
                    baseline_val, actual_val = manual_social_inputs[idx]
                # If not manual, attempt Onclusive API
                elif onclusive_user and onclusive_pw and onclusive_query:
                    b_from = (ev["date"] - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                    b_to = (ev["date"] - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                    a_from = ev["date"].strftime("%Y-%m-%dT00:00:00Z")
                    a_to = (ev["date"] + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")

                    baseline_val = fetch_social_mentions_count(
                        b_from, b_to, onclusive_user, onclusive_pw, onclusive_lang, onclusive_query
                    )
                    actual_val = fetch_social_mentions_count(
                        a_from, a_to, onclusive_user, onclusive_pw, onclusive_lang, onclusive_query
                    )

            # — Manual LevelUp override —
            elif metric in ["Video Views (VOD)", "Hours Watched (Streams)"]:
                # Check manual inputs: manual_levelup_inputs[idx] is a dict with keys "Video Views (VOD)" or "Hours Watched (Streams)"
                if idx in manual_levelup_inputs and metric in manual_levelup_inputs[idx]:
                    baseline_val, actual_val = manual_levelup_inputs[idx][metric]
                # If not manual, attempt LevelUp API
                elif levelup_jwt:
                    brand_id = ev.get("brandId", "")
                    region = ev.get("region", "")
                    b_from = (ev["date"] - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                    b_to = (ev["date"] - timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
                    a_from = ev["date"].strftime("%Y-%m-%dT00:00:00Z")
                    a_to = (ev["date"] + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59:00Z")

                    baseline_json = fetch_levelup_evolution_metrics(
                        brand_id, b_from, b_to, region, levelup_jwt
                    )
                    actual_json = fetch_levelup_evolution_metrics(
                        brand_id, a_from, a_to, region, levelup_jwt
                    )

                    def extract_kpi(data_json: dict, key: str):
                        arr = data_json.get("brandMetrics", [])
                        for entry in arr:
                            if str(entry.get("brandId")) == str(brand_id):
                                return entry.get(key)
                        return None

                    if metric == "Video Views (VOD)":
                        baseline_val = extract_kpi(baseline_json, "videosViews")
                        actual_val = extract_kpi(actual_json, "videosViews")
                    else:  # Hours Watched (Streams)
                        baseline_val = extract_kpi(baseline_json, "hours_watched")
                        actual_val = extract_kpi(actual_json, "hours_watched")

            # For any other metric, baseline_val/actual_val remain None (or can be extended)
            rows.append(
                {
                    "Metric": metric,
                    baseline_col: baseline_val,
                    actual_col: actual_val,
                    "Baseline Method": None,
                }
            )

        df = pd.DataFrame(rows)
        for r in regions:
            sheet_name = f"{ev['name'][:25]}_{r}"
            sheets[sheet_name] = df.copy()

    return sheets


#
# ─── 7) Streamlit App UI ───────────────────────────────────────────────────
#
st.set_page_config(page_title="Event Marketing Analytics", layout="wide")
st.markdown(
    """
# 📊 Event Marketing Analytics Suite

1. **Onclusive (Digimind)** for Social Mentions (or manual input)  
2. **LevelUp (Google SSO)** for Video Views & Hours Watched (or manual input)  
3. Generates an Excel workbook with one sheet per (Event × Region)
""",
    unsafe_allow_html=True,
)

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
    "Select metrics:",
    [
        "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions",
        "Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Search Index", "PCCV", "AMA"
    ],
    default=["Social Mentions", "Video Views (VOD)", "Hours Watched (Streams)"],
)

regions = st.sidebar.multiselect(
    "Output Regions (sheet tabs):",
    ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR"],
    default=["US", "GB"],
)

# ─ Main: Conditional Login or Manual Inputs Based on Metrics ─────────────────

# 1) Initialize variables for Onclusive (Digimind)
onclusive_username = None
onclusive_password = None
onclusive_language = "en"
onclusive_query = None
manual_social_inputs: dict[int, tuple[int, int]] = {}

if "Social Mentions" in metrics:
    st.subheader("🔐 Onclusive (Digimind) for Social Mentions")
    use_manual_social = st.checkbox(
        "❔ Enter Social Mentions counts manually (skip Onclusive)",
        key="manual_social_toggle"
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

        # Quick test for Onclusive credentials (optional)
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


# 2) Initialize variables for LevelUp (Google SSO)
levelup_jwt = None
manual_levelup_inputs: dict[int, dict[str, tuple[int, int]]] = {}

if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
    st.subheader("🎮 LevelUp (Google SSO) for Video Views & Hours Watched")
    use_manual_levelup = st.checkbox(
        "❔ Enter LevelUp metrics manually (skip Google SSO)",
        key="manual_levelup_toggle"
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
        st.markdown(
            """
Press “Generate template” below → you will see a Device-Code prompt  
(“visit https://microsoft.com/devicelogin and enter code…”)  
Complete Google SSO, then the app will fetch Video Views & Hours Watched.
"""
        )

# ─ Generate & Download Template ───────────────────────────────────────────────
if st.button("Generate Template"):
    # 1) Validate Onclusive inputs if needed
    if "Social Mentions" in metrics and not manual_social_inputs:
        if not (onclusive_username and onclusive_password and onclusive_query):
            st.warning("Enter Onclusive credentials or choose manual input for Social Mentions.")
            st.stop()

    # 2) Acquire LevelUp JWT via Device-Code Flow if needed
    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics) and not manual_levelup_inputs:
        # Attempt SSO login if not manual
        levelup_jwt = get_levelup_jwt()
        if not levelup_jwt:
            st.stop()

    # 3) Build Excel sheets
    with st.spinner("Building Excel…"):
        sheets = generate_event_tables(
            events,
            metrics,
            regions,
            # Onclusive API inputs (None if manual)
            onclusive_username,
            onclusive_password,
            onclusive_language,
            onclusive_query,
            manual_social_inputs,
            # LevelUp inputs
            levelup_jwt,
            manual_levelup_inputs,
        )
        if not sheets:
            st.stop()

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                safe_name = sheet_name[:31]  # Excel sheet name limit
                df.to_excel(writer, sheet_name=safe_name, index=False)
        buffer.seek(0)

        st.download_button(
            "📥 Download Event Template",
            data=buffer,
            file_name="event_marketing_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
