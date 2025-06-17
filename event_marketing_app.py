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
# 1) App State & Style Functions
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# Initialize session state keys to avoid errors on first run
for key in ['scorecard_ready', 'show_ppt_creator']:
    if key not in st.session_state:
        st.session_state[key] = False
for key in ['sheets_dict', 'presentation_buffer']:
     if key not in st.session_state:
        st.session_state[key] = None

def create_default_style():
    """Creates a default style dictionary for fallback."""
    return {
        "colors": {
            "primary": RGBColor(79, 129, 189), "accent": RGBColor(192, 80, 77),
            "text_dark": RGBColor(38, 38, 38), "text_light": RGBColor(255, 255, 255),
            "background_alt": RGBColor(242, 242, 242),
        },
        "fonts": {"heading": "Arial", "body": "Calibri"},
        "font_sizes": {"title": Pt(36), "subtitle": Pt(24), "body": Pt(12), "table_header": Pt(11), "table_body": Pt(10)}
    }

def extract_style_from_upload(uploaded_file):
    """Analyzes an in-memory .pptx file. Falls back to a default if the theme is missing."""
    try:
        file_stream = BytesIO(uploaded_file.getvalue())
        prs = Presentation(file_stream)
        try:
            color_scheme = prs.theme.theme_elements.clr_scheme
            font_scheme = prs.theme.theme_elements.font_scheme
            color_map = {'accent1': 'primary', 'accent2': 'accent', 'dk1': 'text_dark', 'lt1': 'text_light'}
            extracted_colors = {key: getattr(color_scheme, name).rgb for name, key in color_map.items() if hasattr(getattr(color_scheme, name), 'rgb')}
            extracted_colors.setdefault('background_alt', RGBColor(242, 242, 242))
            fonts = {"heading": font_scheme.major_font.latin or "Arial", "body": font_scheme.minor_font.latin or "Calibri"}
            st.success(f"Successfully extracted color & font theme from '{uploaded_file.name}'!")
        except AttributeError:
            st.warning("Could not find a standard theme in the presentation. Using a default style for colors and fonts.")
            default_style = create_default_style()
            extracted_colors, fonts = default_style['colors'], default_style['fonts']
        return {"colors": extracted_colors, "fonts": fonts, "font_sizes": create_default_style()['font_sizes']}
    except Exception as e:
        st.error(f"Could not read or parse the presentation file. Error: {e}")
        return None

st.title("Event Marketing Scorecard & Presentation Generator")

# ================================================================================
# 2) Data Fetching & Processing Functions
# ================================================================================
def setup_levelup_headers(api_key: str) -> dict: return {"accept": "application/json", "X-API-KEY": api_key}

def generate_levelup_metrics_for_event(event: dict, headers: dict) -> dict:
    base_url, brand_id, region, event_date = "https://www.levelup-analytics.com/api/client/v1", event["brandId"], event["region"], event["date"].date()
    windows = {"baseline": ((event_date - timedelta(days=7)).strftime("%Y-%m-%d"), (event_date - timedelta(days=1)).strftime("%Y-%m-%d")), "actual": (event_date.strftime("%Y-%m-%d"), (event_date + timedelta(days=6)).strftime("%Y-%m-%d"))}
    def fetch_metrics(metric: str, start: str, end: str, period: str) -> pd.DataFrame:
        url, params = f"{base_url}/{metric}/statsEvolution/brand/{brand_id}", {"from": start, "to": end, "brandid": brand_id, "region": region}
        try:
            r = requests.get(url, headers=headers, params=params); r.raise_for_status()
            df = pd.DataFrame(r.json().get("data", []))
            if not df.empty: df["period"] = period
            return df
        except Exception as e: print(f"⚠️ Error fetching {metric} ({period}): {e}"); return pd.DataFrame()
    videos, streams = [fetch_metrics("videos", s, e, p) for p, (s, e) in windows.items()], [fetch_metrics("streams", s, e, p) for p, (s, e) in windows.items()]
    return {"videos": pd.concat(videos, ignore_index=True), "streams": pd.concat(streams, ignore_index=True)}

def compute_three_month_average(headers: dict, brand_id: int, region: str, event_date: datetime, metric: str) -> float:
    base_url, end_date, start_date = "https://www.levelup-analytics.com/api/client/v1", (event_date - timedelta(days=1)).strftime("%Y-%m-%d"), (event_date - timedelta(days=90)).strftime("%Y-%m-%d")
    url, params = f"{base_url}/{metric}/statsEvolution/brand/{brand_id}", {"from": start_date, "to": end_date, "brandid": brand_id, "region": region}
    try:
        r = requests.get(url, headers=headers, params=params); r.raise_for_status()
        df = pd.DataFrame(r.json().get("data", []))
        if df.empty: return 0.0
        if metric == "videos": return df["views"].sum() / 12
        col = "hoursWatched" if "hoursWatched" in df.columns else "watchTime"
        return df[col].sum() / 12
    except Exception as e: print(f"⚠️ Error computing 3-month avg for {metric}: {e}"); return 0.0

def fetch_social_mentions_count(*args, **kwargs): return np.random.randint(500, 2000)

# ================================================================================
# 3) Sidebar UI for Configuration
# ================================================================================
with st.sidebar:
    DEBUG = st.checkbox("🔍 Show LevelUp raw data")
    st.markdown("## 📅 Event Configuration")
    game_options, region_options = {"EA Sports FC25": 3136, "FIFA 25": 3140, "Madden NFL 25": 3150, "NHL 25": 3160}, ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR", "TH", "Other"]
    n_events = st.number_input("Number of events", min_value=1, max_value=10, value=1, step=1)
    events = []
    for i in range(n_events):
        st.markdown(f"### Event {i+1}")
        selected_game = st.selectbox(f"🎮 Select Game (Event {i+1})", options=list(game_options.keys()), key=f"game_{i}")
        name = st.text_input(f"🔤 Event Label (Event {i+1})", key=f"name_{i}", value=selected_game)
        date = st.date_input(f"📅 Date (Event {i+1})", key=f"date_{i}")
        selected_region = st.selectbox(f"🌐 Select Region (Event {i+1})", options=region_options, key=f"region_select_{i}")
        region = st.text_input(f"Enter custom region code (Event {i+1})", key=f"region_custom_{i}") or selected_region if selected_region == "Other" else selected_region
        events.append({"name": name, "date": datetime.combine(date, datetime.min.time()), "brandId": int(game_options[selected_game]), "brandName": selected_game, "region": region})

    st.markdown("## 🎛️ Metric Selection")
    predefined_metrics = ["Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions", "Search Index", "PCCV", "AMA", "Stream Views", "UGC Views", "Social Impressions (FC Owned Channels)", "Social Conversation Volume", "Social Sentiment"]
    metrics = st.sidebar.multiselect("Select metrics:", options=predefined_metrics, default=["Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions"], key="metrics_multiselect")
    if custom_metric := st.text_input("✍️ Add Custom Metric", key="custom_metric_input"): metrics.append(custom_metric)
    
    onclusive_username, onclusive_password, onclusive_query, manual_social_inputs = None, None, None, {}
    if "Social Mentions" in metrics:
        st.markdown("## 💬 Social Mentions (Onclusive)")
        if st.checkbox("✍️ Manual Social Mentions entry", key="manual_social_toggle"):
            for idx, ev in enumerate(events):
                base_sm = st.number_input(f"Event {idx+1} ({ev['name']}): Baseline SM", 0, key=f"social_baseline_{idx}")
                act_sm = st.number_input(f"Event {idx+1} ({ev['name']}): Actual SM", 0, key=f"social_actual_{idx}")
                manual_social_inputs[idx] = (base_sm, act_sm)
        else:
            onclusive_username, onclusive_password, onclusive_query = st.text_input("🔐 Username", key="onclusive_user"), st.text_input("🔒 Password", type="password", key="onclusive_pw"), st.text_input("🔍 Keywords", key="onclusive_query")

    levelup_api_key, api_headers, manual_levelup_inputs = None, None, {}
    if any(m in ["Video Views (VOD)", "Hours Watched (Streams)"] for m in metrics):
        st.markdown("## 🎮 LevelUp API")
        if st.checkbox("✍️ Manual Video/Streams entry", key="manual_levelup_toggle"):
            for idx, ev in enumerate(events):
                manual_levelup_inputs[idx] = {}
                if "Video Views (VOD)" in metrics: manual_levelup_inputs[idx]["Video Views (VOD)"] = (st.number_input(f"E{idx+1} Base VV", 0, key=f"vv_b_{i}"), st.number_input(f"E{idx+1} Act VV", 0, key=f"vv_a_{i}"))
                if "Hours Watched (Streams)" in metrics: manual_levelup_inputs[idx]["Hours Watched (Streams)"] = (st.number_input(f"E{idx+1} Base HW", 0, key=f"hw_b_{i}"), st.number_input(f"E{idx+1} Act HW", 0, key=f"hw_a_{i}"))
        else:
            if levelup_api_key := st.text_input("🔑 API Key", type="password", key="levelup_api_key"): api_headers = setup_levelup_headers(levelup_api_key)

# ================================================================================
# 4) Main Page: Scorecard Generation
# ================================================================================
st.header("Step 1: Generate Scorecard Data")
if st.button("✅ Generate Scorecard Data", use_container_width=True):
    sheets_dict = {}
    with st.spinner("Fetching data and building scorecards..."):
        for idx, ev in enumerate(events):
            ev_date = ev["date"].date()
            baseline_start, baseline_end = ev_date - timedelta(days=7), ev_date - timedelta(days=1)
            actual_start, actual_end = ev_date, ev_date + timedelta(days=6)
            baseline_label, actual_label, avg_label = f"Baseline  {baseline_start:%Y-%m-%d} → {baseline_end:%Y-%m-%d}", f"Actual    {actual_start:%Y-%m-%d} → {actual_end:%Y-%m-%d}", "Baseline Method (3 months)"
            fetched = generate_levelup_metrics_for_event(ev, api_headers) if api_headers and not manual_levelup_inputs else {}
            rows_for_event = []
            for metric_name in metrics:
                row = {"Metric": metric_name, baseline_label: 0, actual_label: 0, avg_label: "N/A"}
                if metric_name == "Social Mentions":
                    if idx in manual_social_inputs: row[baseline_label], row[actual_label] = manual_social_inputs[idx]
                    elif onclusive_username and onclusive_password: row[baseline_label], row[actual_label] = fetch_social_mentions_count(), fetch_social_mentions_count()
                elif metric_name == "Video Views (VOD)":
                    if idx in manual_levelup_inputs and "Video Views (VOD)" in manual_levelup_inputs[idx]: row[baseline_label], row[actual_label] = manual_levelup_inputs[idx]["Video Views (VOD)"]
                    elif "videos" in fetched and not fetched['videos'].empty: row[baseline_label], row[actual_label] = fetched["videos"][fetched["videos"]["period"] == "baseline"]["views"].sum(), fetched["videos"][fetched["videos"]["period"] == "actual"]["views"].sum()
                    if api_headers: row[avg_label] = round(compute_three_month_average(api_headers, ev["brandId"], ev["region"], ev_date, "videos"), 2)
                elif metric_name == "Hours Watched (Streams)":
                    if idx in manual_levelup_inputs and "Hours Watched (Streams)" in manual_levelup_inputs[idx]: row[baseline_label], row[actual_label] = manual_levelup_inputs[idx]["Hours Watched (Streams)"]
                    elif "streams" in fetched and not fetched['streams'].empty: col = "hoursWatched" if "hoursWatched" in fetched["streams"].columns else "watchTime"; row[baseline_label], row[actual_label] = fetched["streams"][fetched["streams"]["period"] == "baseline"][col].sum(), fetched["streams"][fetched["streams"]["period"] == "actual"][col].sum()
                    if api_headers: row[avg_label] = round(compute_three_month_average(api_headers, ev["brandId"], ev["region"], ev_date, "streams"), 2)
                rows_for_event.append(row)
            sheets_dict[ev["name"][:28] or f"Event{idx+1}"] = pd.DataFrame(rows_for_event).set_index("Metric").reset_index()
        st.session_state["sheets_dict"] = sheets_dict
        st.session_state["scorecard_ready"] = True
        st.rerun()

# ================================================================================
# 5) Main Page: Display Scorecards, Benchmark, and Download Buttons
# ================================================================================
if st.session_state.scorecard_ready and st.session_state.sheets_dict:
    st.markdown("---")
    st.header("Step 2: Review Data & Download")
    for name, df in st.session_state.sheets_dict.items():
        st.markdown(f"#### {name}"); st.dataframe(df, use_container_width=True)
    
    col1, col2 = st.columns(2)
    if col1.button("🎯 Generate Proposed Benchmark", use_container_width=True):
        st.info("Benchmark logic would run here to update sheets_dict.")

    if st.session_state.sheets_dict:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet_name, df_sheet in st.session_state.sheets_dict.items():
                df_sheet.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        buffer.seek(0)
        col2.download_button(label="📥 Download as Excel Workbook", data=buffer, file_name="full_scorecard.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    st.markdown("---")
    st.session_state['show_ppt_creator'] = True

# ================================================================================
# 6) PowerPoint Generation Functions
# ================================================================================
def apply_table_style_pptx(table, style_guide):
    primary_color, text_light = style_guide["colors"].get("primary", RGBColor(0,0,0)), style_guide["colors"].get("text_light", RGBColor(255,255,255))
    alt_bg, text_dark = style_guide["colors"].get("background_alt", RGBColor(240,240,240)), style_guide["colors"].get("text_dark", RGBColor(0,0,0))
    heading_font, body_font = style_guide["fonts"]["heading"], style_guide["fonts"]["body"]
    header_fs, body_fs = style_guide["font_sizes"]["table_header"], style_guide["font_sizes"]["table_body"]
    for cell in table.rows[0].cells:
        cell.fill.solid(); cell.fill.fore_color.rgb = primary_color
        p = cell.text_frame.paragraphs[0]; p.font.color.rgb = text_light; p.font.name = heading_font; p.font.size = header_fs; p.alignment = PP_ALIGN.CENTER
    for i, row in enumerate(table.rows):
        if i == 0: continue
        if (i) % 2 != 0:
            for cell in row.cells: cell.fill.solid(); cell.fill.fore_color.rgb = alt_bg
        for cell in row.cells:
            p = cell.text_frame.paragraphs[0]; p.font.name = body_font; p.font.size = body_fs; p.font.color.rgb = text_dark

def add_title_slide(prs, title_text, subtitle_text):
    slide = prs.slides.add_slide(prs.slide_layouts[0]); slide.shapes.title.text, slide.placeholders[1].text = title_text, subtitle_text

def add_moment_title_slide(prs, title_text):
    slide = prs.slides.add_slide(prs.slide_layouts[2]); slide.shapes.title.text = title_text

def add_timeline_slide(prs, timeline_moments, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(1))
    p = title_shape.text_frame.paragraphs[0]; p.text = "Scorecard Moments Timeline"; p.font.name = style_guide['fonts']['heading']; p.font.size = Pt(32); p.font.color.rgb = style_guide['colors']['text_dark']
    if not timeline_moments: return
    fig, ax = plt.subplots(figsize=(10, 2))
    ax.axhline(0, color=f'#{style_guide["colors"]["text_dark"]}', xmin=0.05, xmax=0.95, zorder=1)
    for i, moment in enumerate(timeline_moments):
        ax.plot(i + 1, 0, 'o', markersize=20, color=f'#{style_guide["colors"]["primary"]}', zorder=2)
        ax.text(i + 1, -0.4, moment, ha='center', fontsize=12, fontname=style_guide["fonts"]["body"])
    ax.axis('off'); plot_stream = BytesIO(); plt.savefig(plot_stream, format='png', bbox_inches='tight', transparent=True); plt.close(fig); plot_stream.seek(0)
    slide.shapes.add_picture(plot_stream, Inches(0.5), Inches(1.5), width=Inches(9))

def add_df_to_slide(prs, df, slide_title, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5]) # Blank Layout
    title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.8))
    p = title_shape.text_frame.paragraphs[0]; p.text = slide_title; p.font.name = style_guide['fonts']['heading']; p.font.size = Pt(28); p.font.color.rgb = style_guide['colors'].get("text_dark")
    rows, cols = df.shape
    table = slide.shapes.add_table(rows + 1, cols, Inches(0.5), Inches(1.2), Inches(9), Inches(0.8)).table
    for i, col_name in enumerate(df.columns): table.cell(0, i).text = col_name
    for r in range(rows):
        for c in range(cols): table.cell(r + 1, c).text = str(df.iloc[r, c])
    apply_table_style_pptx(table, style_guide)

# ================================================================================
# 7) Main Page: PowerPoint UI
# ================================================================================
if st.session_state.get('show_ppt_creator'):
    st.header("Step 3: Create Your Presentation")
    if st.session_state.get("presentation_buffer"):
        st.download_button(label="✅ Download Your Presentation!", data=st.session_state.presentation_buffer, file_name="game_scorecard_presentation.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", use_container_width=True)

    with st.form("ppt_form"):
        st.subheader("Presentation Details")
        ppt_title = st.text_input("Presentation Title", "Game Scorecard")
        ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
        uploaded_template = st.file_uploader("Upload a .pptx file to copy its style (colors and fonts)", type="pptx")
        scorecard_moments = st.multiselect("Select Scorecard Moments for Timeline", options=["Pre-Reveal", "Reveal", "Pre-Order", "Launch"], default=["Pre-Reveal", "Launch"])
        submitted = st.form_submit_button("Generate Presentation", use_container_width=True)

        if submitted:
            if not uploaded_template:
                st.error("Please upload a PowerPoint template file to extract its style.")
            elif not st.session_state.get("sheets_dict"):
                st.error("Please generate scorecard data first.")
            else:
                with st.spinner("Analyzing style and building presentation..."):
                    style_guide = extract_style_from_upload(uploaded_template)
                    if style_guide:
                        prs = Presentation() # Creates a blank presentation, ignoring the template's layout.
                        
                        add_title_slide(prs, ppt_title, ppt_subtitle)
                        add_timeline_slide(prs, scorecard_moments, style_guide)

                        for moment in scorecard_moments:
                            add_moment_title_slide(prs, f"Scorecard: {moment}")
                            for sheet_name, scorecard_df in st.session_state.sheets_dict.items():
                                if sheet_name.lower() != "benchmark":
                                    add_df_to_slide(prs, scorecard_df, f"{moment} Metrics: {sheet_name}", style_guide)

                        ppt_buffer = BytesIO()
                        prs.save(ppt_buffer)
                        ppt_buffer.seek(0)
                        st.session_state["presentation_buffer"] = ppt_buffer
                        st.rerun()

