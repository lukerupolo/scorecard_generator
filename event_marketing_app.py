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

# ================================================================================
# 1) App State & Style Functions
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# Initialize session state keys
for key in ['scorecard_ready', 'show_ppt_creator']:
    if key not in st.session_state: st.session_state[key] = False
for key in ['sheets_dict', 'presentation_buffer']:
     if key not in st.session_state: st.session_state[key] = None

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
            extracted_colors = default_style['colors']
            fonts = default_style['fonts']
        return {"colors": extracted_colors, "fonts": fonts, "font_sizes": create_default_style()['font_sizes']}
    except Exception as e:
        st.error(f"Could not read or parse the presentation file. Error: {e}")
        return None

st.title("Event Marketing Scorecard & Presentation Generator")
# (Sidebar and Data Fetching code would be here - omitted for brevity in this view)
# ...

# ================================================================================
# 6) PowerPoint Generation Functions
# ================================================================================
def apply_table_style_pptx(table, style_guide):
    """Styles a table in PowerPoint using the provided style guide."""
    primary_color = style_guide["colors"].get("primary", RGBColor(0,0,0))
    text_light = style_guide["colors"].get("text_light", RGBColor(255,255,255))
    alt_bg = style_guide["colors"].get("background_alt", RGBColor(240,240,240))
    text_dark = style_guide["colors"].get("text_dark", RGBColor(0,0,0))
    heading_font, body_font = style_guide["fonts"]["heading"], style_guide["fonts"]["body"]
    header_fs, body_fs = style_guide["font_sizes"]["table_header"], style_guide["font_sizes"]["table_body"]
    
    # Style header
    for cell in table.rows[0].cells:
        cell.fill.solid(); cell.fill.fore_color.rgb = primary_color
        p = cell.text_frame.paragraphs[0]; p.font.color.rgb = text_light; p.font.name = heading_font; p.font.size = header_fs; p.alignment = PP_ALIGN.CENTER
    
    # Style data rows
    for i, row in enumerate(table.rows):
        if i == 0: continue
        if i % 2 != 0:
            for cell in row.cells: cell.fill.solid(); cell.fill.fore_color.rgb = alt_bg
        for cell in row.cells:
            p = cell.text_frame.paragraphs[0]; p.font.name = body_font; p.font.size = body_fs; p.font.color.rgb = text_dark

def add_title_slide(prs, title_text, subtitle_text):
    """Adds a standard title slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title_text
    slide.placeholders[1].text = subtitle_text

def add_moment_title_slide(prs, title_text):
    """Adds a standard section header slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[2])
    title = slide.shapes.title
    title.text = title_text

def add_timeline_slide(prs, timeline_moments, style_guide):
    """Adds a slide with a timeline visualization."""
    slide = prs.slides.add_slide(prs.slide_layouts[5]) # Blank layout
    title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(1))
    p = title_shape.text_frame.paragraphs[0]
    p.text = "Scorecard Moments Timeline"
    p.font.name = style_guide['fonts']['heading']; p.font.size = Pt(32); p.font.color.rgb = style_guide['colors']['text_dark']

    if not timeline_moments: return
    fig, ax = plt.subplots(figsize=(10, 2))
    ax.axhline(0, color=f'#{style_guide["colors"]["text_dark"]}', xmin=0.05, xmax=0.95, zorder=1)
    for i, moment in enumerate(timeline_moments):
        ax.plot(i + 1, 0, 'o', markersize=20, color=f'#{style_guide["colors"]["primary"]}', zorder=2)
        ax.text(i + 1, -0.4, moment, ha='center', fontsize=12, fontname=style_guide["fonts"]["body"])
    ax.axis('off')
    plot_stream = BytesIO(); plt.savefig(plot_stream, format='png', bbox_inches='tight', transparent=True); plt.close(fig); plot_stream.seek(0)
    slide.shapes.add_picture(plot_stream, Inches(0.5), Inches(1.5), width=Inches(9))

def add_df_to_slide(prs, df, slide_title, style_guide):
    """Adds a slide with a styled table of data."""
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
# 7) Main Page: UI for Presentation Generation
# ================================================================================
# This assumes scorecard data has been generated and is in st.session_state.sheets_dict
if not st.session_state.sheets_dict:
    st.session_state.sheets_dict = {"Dummy Event": pd.DataFrame({'Metric': ['A', 'B'], 'Value': [1,2]})}

st.header("Create Your Presentation")
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
        else:
            with st.spinner("Analyzing style and building presentation..."):
                style_guide = extract_style_from_upload(uploaded_template)
                if style_guide:
                    # CHANGED: Create a blank presentation, ignoring the uploaded file's layout.
                    prs = Presentation() 

                    # Build the presentation using the original, desired structure
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
