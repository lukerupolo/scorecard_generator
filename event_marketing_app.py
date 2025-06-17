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
# 1) App State & Hardcoded Style
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# Initialize session state keys to avoid errors on first run
for key in ['scorecard_ready', 'show_ppt_creator']:
    if key not in st.session_state:
        st.session_state[key] = False
for key in ['sheets_dict', 'presentation_buffer']:
     if key not in st.session_state:
        st.session_state[key] = None

# NEW: Hardcoded "Dark Mode" style as requested
BRAND_STYLE = {
    "colors": {
        "primary": RGBColor(0, 255, 0),          # Green for headings
        "accent": RGBColor(0, 200, 0),           # A slightly darker green
        "text_light": RGBColor(255, 255, 255),   # White for all text
        "background": RGBColor(0, 0, 0),         # Black for slide background
        "background_alt": RGBColor(40, 40, 40),  # Dark grey for table rows
    },
    "fonts": {"heading": "Inter", "body": "Inter"},
    "font_sizes": {"title": Pt(36), "subtitle": Pt(24), "body": Pt(12), "table_header": Pt(11), "table_body": Pt(10)}
}

st.title("Event Marketing Scorecard & Presentation Generator")

# ================================================================================
# 2) Data Fetching & Processing Functions
# ================================================================================
def setup_levelup_headers(api_key: str) -> dict: return {"accept": "application/json", "X-API-KEY": api_key}
def generate_levelup_metrics_for_event(event: dict, headers: dict) -> dict: return {} # Dummy function
def compute_three_month_average(headers: dict, brand_id: int, region: str, event_date: datetime, metric: str) -> float: return 0.0 # Dummy
def fetch_social_mentions_count(*args, **kwargs): return np.random.randint(500, 2000)

# ================================================================================
# 3) Sidebar UI for Configuration
# ================================================================================
with st.sidebar:
    st.markdown("## 📅 Event Configuration")
    game_options = {"EA Sports FC25": 3136, "FIFA 25": 3140, "Madden NFL 25": 3150}
    n_events = st.number_input("Number of events", min_value=1, max_value=10, value=1, step=1)
    events = [{"name": st.text_input(f"🔤 Event {i+1} Label", key=f"name_{i}", value=f"Event {i+1}")} for i in range(n_events)]
    
    st.markdown("## 🎛️ Metric Selection")
    metrics = st.multiselect("Select metrics:", options=["Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions"], default=["Video Views (VOD)"])

# ================================================================================
# 4) Main Page: Scorecard Generation
# ================================================================================
st.header("Step 1: Generate Scorecard Data")
if st.button("✅ Generate Scorecard Data", use_container_width=True):
    with st.spinner("Building scorecards..."):
        sheets_dict = {}
        for ev in events:
            df = pd.DataFrame({
                "Metric": metrics,
                "Baseline": np.random.randint(1000, 5000, size=len(metrics)),
                "Actual": np.random.randint(1500, 7500, size=len(metrics)),
            })
            sheets_dict[ev["name"]] = df.set_index("Metric").reset_index()
        st.session_state["sheets_dict"] = sheets_dict
        st.session_state["scorecard_ready"] = True
    st.rerun()

# ================================================================================
# 5) Main Page: Display Scorecards and Download Buttons
# ================================================================================
if st.session_state.scorecard_ready and st.session_state.sheets_dict:
    st.markdown("---")
    st.header("Step 2: Review Data & Download")
    for name, df in st.session_state.sheets_dict.items():
        st.markdown(f"#### {name}"); st.dataframe(df, use_container_width=True)
    
    if st.session_state.sheets_dict:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet_name, df_sheet in st.session_state.sheets_dict.items():
                df_sheet.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        buffer.seek(0)
        st.download_button(label="📥 Download as Excel Workbook", data=buffer, file_name="full_scorecard.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    st.markdown("---")
    st.session_state['show_ppt_creator'] = True

# ================================================================================
# 6) PowerPoint Generation Functions
# ================================================================================
def set_slide_background(slide, style_guide):
    """Sets the slide background to black."""
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = style_guide["colors"]["background"]

def apply_table_style_pptx(table, style_guide):
    """Styles a table in PowerPoint using the provided style guide."""
    primary_color = style_guide["colors"].get("primary")
    text_light = style_guide["colors"].get("text_light")
    alt_bg = style_guide["colors"].get("background_alt")
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
            p = cell.text_frame.paragraphs[0]; p.font.name = body_font; p.font.size = body_fs; p.font.color.rgb = text_light

def add_title_slide(prs, title_text, subtitle_text, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    set_slide_background(slide, style_guide)
    slide.shapes.title.text, slide.placeholders[1].text = title_text, subtitle_text
    # Style the text
    for shape in [slide.shapes.title, slide.placeholders[1]]:
        for p in shape.text_frame.paragraphs:
            p.font.name = style_guide["fonts"]["heading"]
            p.font.color.rgb = style_guide["colors"]["text_light"]

def add_moment_title_slide(prs, title_text, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[2])
    set_slide_background(slide, style_guide)
    slide.shapes.title.text = title_text
    p = slide.shapes.title.text_frame.paragraphs[0]
    p.font.name = style_guide["fonts"]["heading"]
    p.font.color.rgb = style_guide["colors"]["primary"]

def add_timeline_slide(prs, timeline_moments, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    set_slide_background(slide, style_guide)
    title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(1))
    p = title_shape.text_frame.paragraphs[0]; p.text = "Scorecard Moments Timeline"; p.font.name = style_guide['fonts']['heading']; p.font.size = Pt(32); p.font.color.rgb = style_guide['colors']['primary']
    if not timeline_moments: return
    # Create plot with dark theme
    fig, ax = plt.subplots(figsize=(10, 2)); fig.patch.set_facecolor('black')
    ax.set_facecolor('black')
    ax.axhline(0, color=f'#{style_guide["colors"]["text_light"]}', xmin=0.05, xmax=0.95, zorder=1)
    for i, moment in enumerate(timeline_moments):
        ax.plot(i + 1, 0, 'o', markersize=20, color=f'#{style_guide["colors"]["primary"]}', zorder=2)
        ax.text(i + 1, -0.4, moment, ha='center', fontsize=12, fontname=style_guide["fonts"]["body"], color=f'#{style_guide["colors"]["text_light"]}')
    ax.axis('off'); plot_stream = BytesIO(); plt.savefig(plot_stream, format='png', bbox_inches='tight', transparent=True); plt.close(fig); plot_stream.seek(0)
    slide.shapes.add_picture(plot_stream, Inches(0.5), Inches(1.5), width=Inches(9))

def add_df_to_slide(prs, df, slide_title, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    set_slide_background(slide, style_guide)
    title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.8))
    p = title_shape.text_frame.paragraphs[0]; p.text = slide_title; p.font.name = style_guide['fonts']['heading']; p.font.size = Pt(28); p.font.color.rgb = style_guide['colors'].get("primary")
    rows, cols = df.shape; table = slide.shapes.add_table(rows + 1, cols, Inches(0.5), Inches(1.2), Inches(9), Inches(0.8)).table
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
        scorecard_moments = st.multiselect("Select Scorecard Moments for Timeline", options=["Pre-Reveal", "Reveal", "Pre-Order", "Launch"], default=["Pre-Reveal", "Launch"])
        submitted = st.form_submit_button("Generate Presentation", use_container_width=True)

        if submitted:
            if not st.session_state.get("sheets_dict"):
                st.error("Please generate scorecard data first.")
            else:
                with st.spinner("Building presentation with dark mode style..."):
                    prs = Presentation() # Creates a blank presentation
                    
                    # Apply hardcoded style to all generated slides
                    add_title_slide(prs, ppt_title, ppt_subtitle, BRAND_STYLE)
                    add_timeline_slide(prs, scorecard_moments, BRAND_STYLE)

                    for moment in scorecard_moments:
                        add_moment_title_slide(prs, f"Scorecard: {moment}", BRAND_STYLE)
                        for sheet_name, scorecard_df in st.session_state.sheets_dict.items():
                            if sheet_name.lower() != "benchmark":
                                add_df_to_slide(prs, scorecard_df, f"{moment} Metrics: {sheet_name}", BRAND_STYLE)

                    ppt_buffer = BytesIO()
                    prs.save(ppt_buffer)
                    ppt_buffer.seek(0)
                    st.session_state["presentation_buffer"] = ppt_buffer
                    st.rerun()
