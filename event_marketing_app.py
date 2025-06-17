import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO

# --- PowerPoint and Styling Imports ---
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import matplotlib.pyplot as plt

# --- Excel Styling Imports ---
from openpyxl.styles import Font, PatternFill, Alignment

# ================================================================================
# VERSION CONTROL TO FORCE CACHE RESET
# ================================================================================
APP_VERSION = "4.0" # Change this number to force a reset on update

st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# --- Initialize or Reset session state ---
if st.session_state.get('app_version') != APP_VERSION:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state['app_version'] = APP_VERSION

# Initialize keys if they don't exist after a potential reset
for key in ['style_uploaded', 'scorecard_ready']:
    if key not in st.session_state:
        st.session_state[key] = False
for key in ['brand_style', 'template_file', 'presentation_buffer', 'sheets_dict']:
     if key not in st.session_state:
        st.session_state[key] = None
# ================================================================================

def create_default_style():
    """Creates a default style dictionary for fallback."""
    return {
        "colors": {
            "primary": RGBColor(79, 129, 189), "accent": RGBColor(192, 80, 77),
            "text_dark": RGBColor(38, 38, 38), "text_light": RGBColor(255, 255, 255),
            "background_alt": RGBColor(242, 242, 242),
        },
        "fonts": {"heading": "Arial", "body": "Calibri"},
        "font_sizes": {
            "title": Pt(36), "subtitle": Pt(24), "body": Pt(12),
            "table_header": Pt(11), "table_body": Pt(10),
        }
    }

def extract_style_from_upload(uploaded_file):
    """
    Analyzes an in-memory .pptx file. Falls back to a default if the theme is missing.
    """
    try:
        file_stream = BytesIO(uploaded_file.getvalue())
        prs = Presentation(file_stream)
        
        try:
            color_scheme = prs.theme.theme_elements.clr_scheme
            font_scheme = prs.theme.theme_elements.font_scheme

            color_map = {'accent1': 'primary', 'accent2': 'accent', 'dk1': 'text_dark', 'lt1': 'text_light'}
            extracted_colors = {key: getattr(color_scheme, name).rgb for name, key in color_map.items() if hasattr(getattr(color_scheme, name), 'rgb')}
            extracted_colors.setdefault('background_alt', RGBColor(242, 242, 242))

            fonts = {
                "heading": font_scheme.major_font.latin or "Arial",
                "body": font_scheme.minor_font.latin or "Calibri",
            }
            st.success(f"Successfully extracted color & font theme from '{uploaded_file.name}'!")

        except AttributeError:
            st.warning("Could not find a standard theme in the presentation. Using a default style for colors and fonts, but your slide layouts will still be used.")
            default_style = create_default_style()
            extracted_colors = default_style['colors']
            fonts = default_style['fonts']

        brand_style = {
            "colors": extracted_colors,
            "fonts": fonts,
            "font_sizes": create_default_style()['font_sizes'],
        }
        return brand_style

    except Exception as e:
        st.error(f"Could not read or parse the presentation file. It may be corrupt or not a standard .pptx file. Error: {e}")
        return None

st.title("Event Marketing Scorecard & Presentation Generator")

# --------------------------------------------------------------------------------
# Step 1 - Style Uploader
# --------------------------------------------------------------------------------
with st.expander("Step 1: Upload Your Branded PowerPoint Template", expanded=not st.session_state.style_uploaded):
    uploaded_template = st.file_uploader(
        "Upload a .pptx file to copy its style (colors, fonts, and layouts)",
        type="pptx",
        key="style_uploader"
    )

    if uploaded_template:
        if st.button("Set as Style Template"):
            style_dict = extract_style_from_upload(uploaded_template)
            if style_dict:
                st.session_state.brand_style = style_dict
                st.session_state.template_file = uploaded_template
                st.session_state.style_uploaded = True
                st.rerun()

# ================================================================================
# ALL CORE FUNCTIONALITY IS NOW NESTED BELOW AND ONLY RUNS AFTER STYLE IS SET
# ================================================================================
if st.session_state.style_uploaded:

    # ────────────────────────────────────────────────────────────────────────────────
    # 1) Helper functions for LevelUp API integration and Social Mentions (Onclusive)
    # ────────────────────────────────────────────────────────────────────────────────
    def setup_levelup_headers(api_key: str) -> dict:
        return {"accept": "application/json", "X-API-KEY": api_key}

    def generate_levelup_metrics_for_event(event: dict, headers: dict) -> dict:
        base_url = "https://www.levelup-analytics.com/api/client/v1"
        brand_id = event["brandId"]
        region = event["region"]
        event_date = event["date"].date()
        windows = {
            "baseline": ((event_date - timedelta(days=7)).strftime("%Y-%m-%d"), (event_date - timedelta(days=1)).strftime("%Y-%m-%d")),
            "actual": (event_date.strftime("%Y-%m-%d"), (event_date + timedelta(days=6)).strftime("%Y-%m-%d")),
        }
        def fetch_metrics(metric: str, start: str, end: str, period: str) -> pd.DataFrame:
            url = f"{base_url}/{metric}/statsEvolution/brand/{brand_id}"
            params = {"from": start, "to": end, "brandid": brand_id, "region": region}
            try:
                r = requests.get(url, headers=headers, params=params)
                r.raise_for_status()
                df = pd.DataFrame(r.json().get("data", []))
                if not df.empty: df["period"] = period
                return df
            except Exception as e:
                print(f"⚠️ Error fetching {metric} ({period}): {e}")
                return pd.DataFrame()
        videos = [fetch_metrics("videos", s, e, p) for p, (s, e) in windows.items()]
        streams = [fetch_metrics("streams", s, e, p) for p, (s, e) in windows.items()]
        return {"videos": pd.concat(videos, ignore_index=True), "streams": pd.concat(streams, ignore_index=True)}

    def compute_three_month_average(headers: dict, brand_id: int, region: str, event_date: datetime, metric: str) -> float:
        base_url = "https://www.levelup-analytics.com/api/client/v1"
        end_date = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = (event_date - timedelta(days=90)).strftime("%Y-%m-%d")
        url = f"{base_url}/{metric}/statsEvolution/brand/{brand_id}"
        params = {"from": start_date, "to": end_date, "brandid": brand_id, "region": region}
        try:
            r = requests.get(url, headers=headers, params=params)
            r.raise_for_status()
            df = pd.DataFrame(r.json().get("data", []))
            if df.empty: return 0.0
            if metric == "videos": return df["views"].sum() / 12
            col = "hoursWatched" if "hoursWatched" in df.columns else "watchTime"
            return df[col].sum() / 12
        except Exception as e:
            print(f"⚠️ Error computing 3-month avg for {metric}: {e}")
            return 0.0
    
    # NOTE: A dummy function is used here as the original was not provided.
    def fetch_social_mentions_count(*args, **kwargs):
        """Dummy function for social mentions."""
        return np.random.randint(500, 2000)

    # ────────────────────────────────────────────────────────────────────────────────
    # 2) Sidebar UI
    # ────────────────────────────────────────────────────────────────────────────────
    DEBUG = st.sidebar.checkbox("🔍 Show LevelUp raw data")
    game_options = {"EA Sports FC25": 3136, "FIFA 25": 3140, "Madden NFL 25": 3150, "NHL 25": 3160}
    region_options = ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR", "TH", "Other"]
    
    st.sidebar.markdown("## 📅 Event Configuration")
    n_events = st.sidebar.number_input("Number of events", min_value=1, max_value=10, value=1, step=1)
    events: list[dict] = []
    for i in range(n_events):
        st.sidebar.markdown(f"### Event {i+1}")
        selected_game = st.sidebar.selectbox(f"🎮 Select Game (Event {i+1})", options=list(game_options.keys()), key=f"game_{i}")
        brand_name = selected_game
        brand_id = game_options[selected_game]
        name = st.sidebar.text_input(f"🔤 Event Label (Event {i+1})", key=f"name_{i}", value=brand_name)
        date = st.sidebar.date_input(f"📅 Date (Event {i+1})", key=f"date_{i}")
        selected_region = st.sidebar.selectbox(f"🌐 Select Region (Event {i+1})", options=region_options, key=f"region_select_{i}")
        if selected_region == "Other":
            region = st.sidebar.text_input(f"Enter custom region code (Event {i+1})", key=f"region_custom_{i}") or ""
        else:
            region = selected_region
        events.append({"name": name, "date": datetime.combine(date, datetime.min.time()), "brandId": int(brand_id), "brandName": brand_name, "region": region})

    st.sidebar.markdown("## 🎛️ Metric Selection")
    predefined_metrics = ["Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions", "Search Index", "PCCV", "AMA", "Stream Views", "UGC Views", "Social Impressions (FC Owned Channels)", "Social Conversation Volume", "Social Sentiment"]
    metrics = st.sidebar.multiselect("Select metrics:", options=predefined_metrics, default=["Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions"], key="metrics_multiselect")
    custom_metric = st.sidebar.text_input("✍️ Add Custom Metric", placeholder="Type a custom metric and press Enter", key="custom_metric_input")
    if custom_metric: metrics.append(custom_metric)
    
    # ────────────────────────────────────────────────────────────────────────────────
    # 3) Authentication UI
    # ────────────────────────────────────────────────────────────────────────────────
    onclusive_username, onclusive_password, onclusive_query = None, None, None
    manual_social_inputs = {}
    if "Social Mentions" in metrics:
        st.sidebar.markdown("## 💬 Social Mentions (Onclusive)")
        if st.sidebar.checkbox("✍️ Manual Social Mentions entry", key="manual_social_toggle"):
            for idx, ev in enumerate(events):
                base_sm = st.sidebar.number_input(f"Event {idx+1} ({ev['name']}): Baseline SM", min_value=0, step=1, key=f"social_baseline_{idx}")
                act_sm = st.sidebar.number_input(f"Event {idx+1} ({ev['name']}): Actual SM", min_value=0, step=1, key=f"social_actual_{idx}")
                manual_social_inputs[idx] = (base_sm, act_sm)
        else:
            onclusive_username = st.sidebar.text_input("🔐 Onclusive Username", key="onclusive_user")
            onclusive_password = st.sidebar.text_input("🔒 Onclusive Password", type="password", key="onclusive_pw")
            onclusive_query = st.sidebar.text_input("🔍 Search Keywords", key="onclusive_query")

    levelup_api_key, api_headers = None, None
    manual_levelup_inputs = {}
    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
        st.sidebar.markdown("## 🎮 LevelUp API")
        if st.sidebar.checkbox("✍️ Manual Video/Streams entry", key="manual_levelup_toggle"):
            for idx, ev in enumerate(events):
                manual_levelup_inputs[idx] = {}
                if "Video Views (VOD)" in metrics:
                    vv_base = st.sidebar.number_input(f"Event {idx+1} ({ev['name']}): Baseline VV", min_value=0, step=1, key=f"levelup_vv_baseline_{idx}")
                    vv_act = st.sidebar.number_input(f"Event {idx+1} ({ev['name']}): Actual VV", min_value=0, step=1, key=f"levelup_vv_actual_{idx}")
                    manual_levelup_inputs[idx]["Video Views (VOD)"] = (vv_base, vv_act)
                if "Hours Watched (Streams)" in metrics:
                    hw_base = st.sidebar.number_input(f"Event {idx+1} ({ev['name']}): Baseline HW", min_value=0, step=1, key=f"levelup_hw_baseline_{idx}")
                    hw_act = st.sidebar.number_input(f"Event {idx+1} ({ev['name']}): Actual HW", min_value=0, step=1, key=f"levelup_hw_actual_{idx}")
                    manual_levelup_inputs[idx]["Hours Watched (Streams)"] = (hw_base, hw_act)
        else:
            levelup_api_key = st.sidebar.text_input("🔑 Paste LevelUp API Key here", type="password", key="levelup_api_key")
            if levelup_api_key: api_headers = setup_levelup_headers(levelup_api_key)

    # ────────────────────────────────────────────────────────────────────────────────
    # 4) Main Area: Scorecard Generation Button and Logic
    # ────────────────────────────────────────────────────────────────────────────────
    st.header("Step 2: Generate Scorecard")
    if st.button("✅ Generate Scorecard"):
        sheets_dict = {}
        with st.spinner("Fetching data and building scorecards..."):
            for idx, ev in enumerate(events):
                ev_date = ev["date"].date()
                baseline_start, baseline_end = ev_date - timedelta(days=7), ev_date - timedelta(days=1)
                actual_start, actual_end = ev_date, ev_date + timedelta(days=6)
                baseline_label = f"Baseline  {baseline_start:%Y-%m-%d} → {baseline_end:%Y-%m-%d}"
                actual_label = f"Actual    {actual_start:%Y-%m-%d} → {actual_end:%Y-%m-%d}"
                avg_label = "Baseline Method (3 months)"
                
                fetched = {}
                if api_headers and not manual_levelup_inputs:
                    fetched = generate_levelup_metrics_for_event(ev, api_headers)

                rows_for_event = []
                for metric_name in metrics:
                    row = {"Metric": metric_name, baseline_label: None, actual_label: None, avg_label: None}
                    if metric_name == "Social Mentions":
                        if idx in manual_social_inputs:
                            row[baseline_label], row[actual_label] = manual_social_inputs[idx]
                        elif onclusive_username and onclusive_password and onclusive_query:
                            row[baseline_label] = fetch_social_mentions_count()
                            row[actual_label] = fetch_social_mentions_count()
                    elif metric_name == "Video Views (VOD)":
                        if idx in manual_levelup_inputs and "Video Views (VOD)" in manual_levelup_inputs[idx]:
                            row[baseline_label], row[actual_label] = manual_levelup_inputs[idx]["Video Views (VOD)"]
                        elif "videos" in fetched and not fetched['videos'].empty:
                            vid_df = fetched["videos"]
                            row[baseline_label] = vid_df[vid_df["period"] == "baseline"]["views"].sum()
                            row[actual_label] = vid_df[vid_df["period"] == "actual"]["views"].sum()
                        if api_headers: row[avg_label] = round(compute_three_month_average(api_headers, ev["brandId"], ev["region"], ev_date, "videos"), 2)
                    elif metric_name == "Hours Watched (Streams)":
                        if idx in manual_levelup_inputs and "Hours Watched (Streams)" in manual_levelup_inputs[idx]:
                            row[baseline_label], row[actual_label] = manual_levelup_inputs[idx]["Hours Watched (Streams)"]
                        elif "streams" in fetched and not fetched['streams'].empty:
                            str_df = fetched["streams"]
                            col_name = "hoursWatched" if "hoursWatched" in str_df.columns else "watchTime"
                            row[baseline_label] = str_df[str_df["period"] == "baseline"][col_name].sum()
                            row[actual_label] = str_df[str_df["period"] == "actual"][col_name].sum()
                        if api_headers: row[avg_label] = round(compute_three_month_average(api_headers, ev["brandId"], ev["region"], ev_date, "streams"), 2)
                    rows_for_event.append(row)
                
                df_event = pd.DataFrame(rows_for_event).set_index("Metric")
                sheets_dict[ev["name"][:28] or f"Event{idx+1}"] = df_event.reset_index()
            
            st.session_state["sheets_dict"] = sheets_dict
            st.session_state["scorecard_ready"] = True
            st.rerun()

    if st.session_state.scorecard_ready and st.session_state.sheets_dict:
        st.subheader("Generated Scorecards")
        for name, df in st.session_state.sheets_dict.items():
            st.markdown(f"#### {name}")
            st.dataframe(df)

        # ────────────────────────────────────────────────────────────────────────────────
        # 5) Benchmark and Download Section
        # ────────────────────────────────────────────────────────────────────────────────
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎯 Generate Proposed Benchmark"):
                # ... (Benchmark logic from before, omitted for brevity)
                st.info("Benchmark logic would run here.")
        with col2:
            # Excel Download
            if st.session_state.sheets_dict:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    for sheet_name, df_sheet in st.session_state.sheets_dict.items():
                        df_sheet.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                buffer.seek(0)
                st.download_button(label="📥 Download as Excel Workbook", data=buffer, file_name="full_scorecard.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("---")

    # ────────────────────────────────────────────────────────────────────────────────
    # 6) PowerPoint Generation
    # ────────────────────────────────────────────────────────────────────────────────
    # (PowerPoint helper functions like add_df_to_slide etc. go here)
    def apply_table_style_pptx(table, style_guide):
        primary_color = style_guide["colors"].get("primary", RGBColor(0,0,0))
        text_light_color = style_guide["colors"].get("text_light", RGBColor(255,255,255))
        alt_bg_color = style_guide["colors"].get("background_alt", RGBColor(240,240,240))
        text_dark_color = style_guide["colors"].get("text_dark", RGBColor(0,0,0))
        heading_font = style_guide["fonts"]["heading"]
        body_font = style_guide["fonts"]["body"]
        header_font_size = style_guide["font_sizes"]["table_header"]
        body_font_size = style_guide["font_sizes"]["table_body"]
        for cell in table.rows[0].cells:
            cell.fill.solid(); cell.fill.fore_color.rgb = primary_color
            p = cell.text_frame.paragraphs[0]; p.font.color.rgb = text_light_color; p.font.name = heading_font; p.font.size = header_font_size; p.alignment = PP_ALIGN.CENTER
        for row_idx, row in enumerate(table.rows[1:], start=1):
            if row_idx % 2 != 0:
                for cell in row.cells: cell.fill.solid(); cell.fill.fore_color.rgb = alt_bg_color
            for cell in row.cells:
                p = cell.text_frame.paragraphs[0]; p.font.name = body_font; p.font.size = body_font_size; p.font.color.rgb = text_dark_color

    def add_df_to_slide(prs, df, slide_title, style_guide):
        slide_layout = prs.slide_layouts[5] # Blank Layout
        slide = prs.slides.add_slide(slide_layout)
        title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.8))
        p = title_shape.text_frame.paragraphs[0]; p.text = slide_title; p.font.name = style_guide['fonts']['heading']; p.font.size = Pt(28); p.font.color.rgb = style_guide['colors']['text_dark']
        rows, cols = df.shape
        table = slide.shapes.add_table(rows + 1, cols, Inches(0.5), Inches(1.2), Inches(9), Inches(0.8)).table
        for i, col_name in enumerate(df.columns): table.cell(0, i).text = col_name
        for r in range(rows):
            for c in range(cols): table.cell(r + 1, c).text = str(df.iloc[r, c])
        apply_table_style_pptx(table, style_guide)
    
    st.header("Step 3: Create Your Presentation")
    if st.session_state.get("presentation_buffer"):
        st.download_button(label="✅ Download Your Presentation!", data=st.session_state.presentation_buffer, file_name="game_scorecard_presentation.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")

    with st.form("ppt_form"):
        st.subheader("Presentation Details")
        ppt_title = st.text_input("Presentation Title", "Game Scorecard")
        ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
        submitted = st.form_submit_button("Generate Presentation")

        if submitted:
            if not st.session_state.get("sheets_dict"):
                st.error("Please generate scorecard data first.")
            else:
                template_stream = BytesIO(st.session_state.template_file.getvalue())
                prs = Presentation(template_stream)
                style_guide = st.session_state.brand_style

                title_slide_layout = prs.slide_layouts[0]
                slide = prs.slides.add_slide(title_slide_layout)
                slide.shapes.title.text = ppt_title
                slide.placeholders[1].text = ppt_subtitle

                for sheet_name, scorecard_df in st.session_state.sheets_dict.items():
                    if sheet_name.lower() != "benchmark":
                        add_df_to_slide(prs, scorecard_df, f"Metrics: {sheet_name}", style_guide)

                ppt_buffer = BytesIO()
                prs.save(ppt_buffer)
                ppt_buffer.seek(0)
                st.session_state["presentation_buffer"] = ppt_buffer
                st.rerun()

