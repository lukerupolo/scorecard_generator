from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import matplotlib.pyplot as plt
from io import BytesIO

def create_presentation(title, subtitle, scorecard_moments, sheets_dict, style_guide):
    """Creates and returns a PowerPoint presentation as a BytesIO buffer."""
    prs = Presentation() # Creates a blank presentation

    # Build the presentation slide by slide
    add_title_slide(prs, title, subtitle, style_guide)
    add_timeline_slide(prs, scorecard_moments, style_guide)

    for moment in scorecard_moments:
        add_moment_title_slide(prs, f"Scorecard: {moment}", style_guide)
        for sheet_name, scorecard_df in sheets_dict.items():
            if sheet_name.lower() != "benchmark":
                add_df_to_slide(prs, scorecard_df, f"{moment} Metrics: {sheet_name}", style_guide)

    # Save to an in-memory buffer
    ppt_buffer = BytesIO()
    prs.save(ppt_buffer)
    ppt_buffer.seek(0)
    return ppt_buffer

# --- Helper functions for slide creation ---

def set_slide_background(slide, style_guide):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = style_guide["colors"]["background"]

def apply_table_style_pptx(table, style_guide):
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
        if i % 2 != 0:
            for cell in row.cells: cell.fill.solid(); cell.fill.fore_color.rgb = alt_bg
        for cell in row.cells:
            p = cell.text_frame.paragraphs[0]; p.font.name = body_font; p.font.size = body_fs; p.font.color.rgb = text_light

def add_title_slide(prs, title_text, subtitle_text, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    set_slide_background(slide, style_guide)
    slide.shapes.title.text, slide.placeholders[1].text = title_text, subtitle_text
    for shape in [slide.shapes.title, slide.placeholders[1]]:
        for p in shape.text_frame.paragraphs:
            p.font.name = style_guide["fonts"]["heading"]; p.font.color.rgb = style_guide["colors"]["text_light"]

def add_moment_title_slide(prs, title_text, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[2])
    set_slide_background(slide, style_guide)
    slide.shapes.title.text = title_text
    p = slide.shapes.title.text_frame.paragraphs[0]
    p.font.name = style_guide["fonts"]["heading"]
    p.font.color.rgb = style_guide["colors"]["primary"]

def add_timeline_slide(prs, timeline_moments, style_guide):
    # ... (Full implementation as before)
    pass

def add_df_to_slide(prs, df, slide_title, style_guide):
    # ... (Full implementation as before)
    pass
