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
# NEW: Function to extract style directly from an uploaded file
# ================================================================================
def extract_style_from_upload(uploaded_file):
    """
    Analyzes an in-memory .pptx file and returns its style guide.
    """
    try:
        # Use BytesIO to read the uploaded file in memory
        file_stream = BytesIO(uploaded_file.getvalue())
        prs = Presentation(file_stream)
        
        # --- 1. Extract Theme Colors ---
        color_scheme = prs.theme.theme_elements.clr_scheme
        color_map = {
            'accent1': 'primary', 'accent2': 'accent', 'dk1': 'text_dark',
            'lt1': 'text_light', 'accent3': 'accent3', 'accent4': 'accent4'
        }
        extracted_colors = {}
        for name, key in color_map.items():
            color_obj = getattr(color_scheme, name)
            if hasattr(color_obj, 'rgb'):
                extracted_colors[key] = color_obj.rgb
        
        # Add a default for alt background if needed
        extracted_colors.setdefault('background_alt', RGBColor(242, 242, 242))

        # --- 2. Extract Theme Fonts ---
        font_scheme = prs.theme.theme_elements.font_scheme
        fonts = {
            "heading": font_scheme.major_font.latin or "Arial",
            "body": font_scheme.minor_font.latin or "Calibri",
        }

        # --- 3. Define Font Sizes ---
        font_sizes = {
            "title": Pt(36), "subtitle": Pt(24), "body": Pt(12),
            "table_header": Pt(11), "table_body": Pt(10),
        }
        
        # --- 4. Assemble the Brand Style Dictionary ---
        brand_style = {
            "colors": extracted_colors,
            "fonts": fonts,
            "font_sizes": font_sizes,
        }
        st.success(f"Successfully extracted style from '{uploaded_file.name}'!")
        return brand_style

    except Exception as e:
        st.error(f"Could not read or parse the presentation file. Please try another file. Error: {e}")
        return None

# ================================================================================

st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# --- Initialize session state ---
if 'style_uploaded' not in st.session_state:
    st.session_state['style_uploaded'] = False
if 'brand_style' not in st.session_state:
    st.session_state['brand_style'] = None
if 'template_file' not in st.session_state:
    st.session_state['template_file'] = None

st.title("Event Marketing Scorecard & Presentation Generator")

# --------------------------------------------------------------------------------
# NEW: Step 1 - Style Uploader
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
                st.rerun() # Rerun the app to show the next sections

# Only show the rest of the app if a style has been set
if st.session_state.style_uploaded:
    
    # All other code (sidebar, scorecard generation, etc.) is nested inside this block
    DEBUG = st.sidebar.checkbox("🔍 Show LevelUp raw data")

    # (Your other helper functions for LevelUp, etc., would go here)
    # ...
    
    # ────────────────────────────────────────────────────────────────────────────────
    # Sidebar Configuration
    # ────────────────────────────────────────────────────────────────────────────────
    st.sidebar.markdown("## 📅 Event Configuration")
    # ... (Your sidebar UI code for events and metrics goes here) ...
    
    # For demonstration, we'll create dummy data
    if "sheets_dict" not in st.session_state or not st.session_state["sheets_dict"]:
        dummy_df = pd.DataFrame({
            'Metric': ['Video Views (VOD)', 'Hours Watched (Streams)', 'Social Mentions'],
            'Baseline': [1000, 500, 200],
            'Actual': [1500, 750, 300]
        })
        st.session_state["sheets_dict"] = {"Dummy Event": dummy_df}
    
    # ────────────────────────────────────────────────────────────────────────────────
    # PowerPoint and Excel Styling Functions (Now use the style_guide parameter)
    # ────────────────────────────────────────────────────────────────────────────────
    def apply_table_style_pptx(table, style_guide):
        """Applies branding from the provided style guide to a pptx table."""
        # ... (rest of the function is the same, using `style_guide` variable)
        primary_color = style_guide["colors"].get("primary", RGBColor(0,0,0))
        text_light_color = style_guide["colors"].get("text_light", RGBColor(255,255,255))
        alt_bg_color = style_guide["colors"].get("background_alt", RGBColor(240,240,240))
        text_dark_color = style_guide["colors"].get("text_dark", RGBColor(0,0,0))
        heading_font = style_guide["fonts"]["heading"]
        body_font = style_guide["fonts"]["body"]
        header_font_size = style_guide["font_sizes"]["table_header"]
        body_font_size = style_guide["font_sizes"]["table_body"]

        for cell in table.rows[0].cells:
            cell.fill.solid()
            cell.fill.fore_color.rgb = primary_color
            p = cell.text_frame.paragraphs[0]
            p.font.color.rgb = text_light_color
            p.font.name = heading_font
            p.font.size = header_font_size
            p.alignment = PP_ALIGN.CENTER

        for row_idx, row in enumerate(table.rows[1:], start=1):
            if row_idx % 2 != 0:
                for cell in row.cells:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = alt_bg_color
            for cell in row.cells:
                p = cell.text_frame.paragraphs[0]
                p.font.name = body_font
                p.font.size = body_font_size
                p.font.color.rgb = text_dark_color

    def add_df_to_slide(prs, df, slide_title, style_guide):
        # ... (This function now takes style_guide as a parameter)
        slide_layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        # ... (Styling uses the style_guide parameter)
        rows, cols = df.shape
        table = slide.shapes.add_table(rows + 1, cols, Inches(0.5), Inches(1.2), Inches(9), Inches(0.8)).table
        # ... (Populate table)
        for i, col_name in enumerate(df.columns):
            table.cell(0, i).text = col_name
        for r in range(rows):
            for c in range(cols):
                table.cell(r + 1, c).text = str(df.iloc[r, c])
        # Apply style at the end
        apply_table_style_pptx(table, style_guide)
        
    # (Other PowerPoint functions: add_title_slide, add_timeline_slide, etc.)
    # ... These would also need to take `style_guide` as a parameter if they do styling.

    # ────────────────────────────────────────────────────────────────────────────────
    # Main Application Logic
    # ────────────────────────────────────────────────────────────────────────────────
    st.header("Step 2: Generate Scorecard Data")
    # ... (Your scorecard generation button and logic would go here) ...
    st.dataframe(st.session_state["sheets_dict"]["Dummy Event"])

    st.header("Step 3: Create Your Presentation")
    if "presentation_buffer" in st.session_state and st.session_state["presentation_buffer"]:
        st.download_button(
            label="✅ Download Your Presentation!",
            data=st.session_state["presentation_buffer"],
            file_name="game_scorecard_presentation.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    with st.form("ppt_form"):
        st.subheader("Presentation Details")
        ppt_title = st.text_input("Presentation Title", "Game Scorecard")
        ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
        
        scorecard_moments = st.multiselect(
            "Select Scorecard Moments for Timeline",
            options=["Pre-Reveal", "Reveal", "Pre-Order", "Launch", "Post-Launch"],
            default=["Pre-Reveal", "Reveal", "Launch"]
        )
        submitted = st.form_submit_button("Generate Presentation")

        if submitted:
            # Use the uploaded file as the template
            template_stream = BytesIO(st.session_state.template_file.getvalue())
            prs = Presentation(template_stream)
            
            # Retrieve the extracted style from session state
            style_guide = st.session_state.brand_style

            # Slide 1: Title Slide (uses the template's layout)
            title_slide_layout = prs.slide_layouts[0]
            slide = prs.slides.add_slide(title_slide_layout)
            slide.shapes.title.text = ppt_title
            slide.placeholders[1].text = ppt_subtitle
            
            # Add other slides using the extracted style
            for moment in scorecard_moments:
                # Add moment title slide
                moment_title_layout = prs.slide_layouts[1]
                slide = prs.slides.add_slide(moment_title_layout)
                slide.shapes.title.text = f"Scorecard: {moment}"

                # Add data table slide
                for sheet_name, scorecard_df in st.session_state["sheets_dict"].items():
                    if sheet_name.lower() != "benchmark":
                        add_df_to_slide(prs, scorecard_df, f"{moment} Metrics: {sheet_name}", style_guide)

            # Save presentation to a BytesIO object for download
            ppt_buffer = BytesIO()
            prs.save(ppt_buffer)
            ppt_buffer.seek(0)
            st.session_state["presentation_buffer"] = ppt_buffer
            st.rerun()
