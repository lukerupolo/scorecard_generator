from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from io import BytesIO
import matplotlib.pyplot as plt
import requests 
import streamlit as st
import pandas as pd

# (The main `create_presentation` function and other helpers remain the same)
# ...
def create_presentation(title, subtitle, scorecard_moments, sheets_dict, style_guide, region_prompt, openai_api_key):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(16), Inches(9)
    # ... (rest of the function)
    return BytesIO() # Placeholder

def generate_and_add_background_image(slide, region, style_guide, api_key, slide_width, slide_height, prompt_detail="football culture"):
    # ... (full implementation)
    pass
# ... (all other helper functions)


def add_df_to_slide(prs, df, slide_title, style_guide):
    """
    Adds a slide with a styled table of data, now with support for merged category cells.
    """
    slide = prs.slides.add_slide(prs.slide_layouts[5]) # Blank Layout
    slide.background.fill.solid(); slide.background.fill.fore_color.rgb = style_guide["colors"]["content_slide_bg"]
    
    title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(15), Inches(1))
    p = title_shape.text_frame.paragraphs[0]
    p.text = slide_title
    p.font.name = style_guide['fonts']['heading']
    p.font.size = style_guide['font_sizes']['content_title']
    p.font.color.rgb = style_guide['colors'].get("content_heading_text")

    # The table now needs one more column for the Category
    rows, cols = df.shape
    table = slide.shapes.add_table(rows + 1, cols, Inches(0.5), Inches(1.2), Inches(15), Inches(1.0)).table
    
    # --- Set Column Widths ---
    table.columns[0].width = Inches(2.0) # Category column
    table.columns[1].width = Inches(4.5) # Metric column
    for i in range(2, cols):
        table.columns[i].width = Inches(2.0)

    # --- Populate Header Row ---
    # Set the first header cell (Category) to blank
    table.cell(0, 0).text = ""
    for i, col_name in enumerate(df.columns[1:], start=1):
        table.cell(0, i).text = col_name

    # --- Populate Data Rows ---
    for r in range(rows):
        for c in range(cols):
            table.cell(r + 1, c).text = str(df.iloc[r, c])
    
    apply_table_style_pptx(table, style_guide) # Apply base styling first

    # --- NEW: Merge Category Cells ---
    # Identify groups of rows that belong to the same category
    df['category_group'] = (df['Category'] != '').cumsum()
    
    for group_id in df['category_group'].unique():
        group_rows = df[df['category_group'] == group_id]
        if len(group_rows) > 1:
            start_row_idx = group_rows.index[0] + 1 # +1 for header row
            end_row_idx = group_rows.index[-1] + 1
            
            # Merge the cells in the first column for this group
            start_cell = table.cell(start_row_idx, 0)
            end_cell = table.cell(end_row_idx, 0)
            start_cell.merge(end_cell)

    # --- Final Styling for Merged Category Cells ---
    for r in range(1, rows + 1):
        cell = table.cell(r, 0)
        if cell.text: # Only style cells that have category text
            p = cell.text_frame.paragraphs[0]
            p.font.bold = True
            p.font.size = Pt(14)
            p.alignment = PP_ALIGN.CENTER
            cell.vertical_anchor = 'middle' # Center text vertically
