from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from io import BytesIO
import matplotlib.pyplot as plt
import base64
import requests # Needed for API calls
import streamlit as st # To show progress

# ================================================================================
# Main Presentation Creation Function
# ================================================================================
def create_presentation(title, subtitle, scorecard_moments, sheets_dict, style_guide, region_prompt):
    """Creates and returns a PowerPoint presentation as a BytesIO buffer."""
    prs = Presentation()
    prs.slide_width = Inches(16)
    prs.slide_height = Inches(9)

    add_title_slide(prs, title, subtitle, style_guide)
    add_timeline_slide(prs, scorecard_moments, style_guide)

    # Use a progress bar for the image generation
    progress_text = "Generating AI background images... (This can take a moment)"
    image_progress_bar = st.progress(0, text=progress_text)
    total_moments = len(scorecard_moments)

    for i, moment in enumerate(scorecard_moments):
        # Pass the region_prompt for image generation
        add_moment_title_slide(prs, f"SCORECARD:\n{moment.upper()}", style_guide, region_prompt)
        
        # Update progress bar
        image_progress_bar.progress((i + 1) / total_moments, text=f"Generating image for '{moment}'...")

        for sheet_name, scorecard_df in sheets_dict.items():
            if sheet_name.lower() != "benchmark":
                add_df_to_slide(prs, scorecard_df, f"{moment.upper()} METRICS: {sheet_name.upper()}", style_guide)
    
    image_progress_bar.empty() # Clear the progress bar

    # Save to an in-memory buffer
    ppt_buffer = BytesIO()
    prs.save(ppt_buffer)
    ppt_buffer.seek(0)
    return ppt_buffer

# ================================================================================
# NEW: AI Background Image Generation with Gemini API
# ================================================================================
def generate_and_add_background_image(slide, region, style_guide):
    """Generates an image using the Gemini API and adds it as the slide background."""
    prompt = f"Dark, gritty, artistic representation of football culture in {region}, cinematic, ultra-realistic photo, dramatic lighting, epic style"
    
    try:
        # --- Gemini API Call ---
        api_key = "" # API key is handled by the execution environment
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={api_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1}
        }
        
        response = requests.post(api_url, json=payload)
        response.raise_for_status() # Raise an exception for bad status codes
        
        result = response.json()
        
        if result.get("predictions") and result["predictions"][0].get("bytesBase64Encoded"):
            image_b64 = result["predictions"][0]["bytesBase64Encoded"]
            image_bytes = base64.b64decode(image_b64)
            image_stream = BytesIO(image_bytes)

            # Add the picture to fill the entire slide
            left = top = Inches(0)
            pic = slide.shapes.add_picture(image_stream, left, top, width=slide.part.presentation.slide_width, height=slide.part.presentation.slide_height)
            
            # Send the image to the back to act as a background
            slide.shapes._spTree.remove(pic._element)
            slide.shapes._spTree.insert(2, pic._element)
            return
        else:
            print("API response did not contain image data. Falling back to solid color.")
            raise ValueError("Invalid API response")

    except Exception as e:
        print(f"Image generation failed: {e}. Falling back to solid color background.")
        # Fallback to black background if API call fails
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = style_guide["colors"]["title_slide_bg"]

# ================================================================================
# Helper functions for slide creation and styling
# ================================================================================
def apply_table_style_pptx(table, style_guide):
    header_bg = style_guide["colors"]["table_header_bg"]
    header_text = style_guide["colors"]["table_header_text"]
    body_text = style_guide["colors"]["content_body_text"]
    alt_bg = style_guide["colors"]["table_alt_row_bg"]
    heading_font, body_font = style_guide["fonts"]["heading"], style_guide["fonts"]["body"]
    header_fs, body_fs = style_guide["font_sizes"]["table_header"], style_guide["font_sizes"]["table_body"]
    
    for cell in table.rows[0].cells:
        cell.fill.solid(); cell.fill.fore_color.rgb = header_bg
        p = cell.text_frame.paragraphs[0]; p.font.color.rgb = header_text; p.font.name = heading_font; p.font.size = header_fs; p.alignment = PP_ALIGN.CENTER
    
    for i, row in enumerate(table.rows):
        if i == 0: continue
        if i % 2 != 0:
            for cell in row.cells: cell.fill.solid(); cell.fill.fore_color.rgb = alt_bg
        for cell in row.cells:
            p = cell.text_frame.paragraphs[0]; p.font.name = body_font; p.font.size = body_fs; p.font.color.rgb = body_text

def add_title_slide(prs, title_text, subtitle_text, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5]) # Blank layout
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = style_guide["colors"]["title_slide_bg"]
    
    title_shape = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(14), Inches(2))
    p = title_shape.text_frame.paragraphs[0]; p.text = title_text.upper(); p.font.name = style_guide["fonts"]["heading"]; p.font.bold = True; p.font.size = style_guide["font_sizes"]["title"]; p.font.color.rgb = style_guide["colors"]["title_slide_text"]; p.alignment = PP_ALIGN.CENTER

    subtitle_shape = slide.shapes.add_textbox(Inches(1), Inches(4.5), Inches(14), Inches(1.5))
    p = subtitle_shape.text_frame.paragraphs[0]; p.text = subtitle_text; p.font.name = style_guide["fonts"]["body"]; p.font.size = style_guide["font_sizes"]["subtitle"]; p.font.color.rgb = style_guide["colors"]["title_slide_text"]; p.alignment = PP_ALIGN.CENTER

def add_moment_title_slide(prs, title_text, style_guide, region):
    slide = prs.slides.add_slide(prs.slide_layouts[5]) # Blank layout
    generate_and_add_background_image(slide, region, style_guide)
    
    txBox = slide.shapes.add_textbox(Inches(1), Inches(3.5), Inches(14), Inches(3))
    p = txBox.text_frame.paragraphs[0]; p.text = title_text; p.font.name = style_guide["fonts"]["heading"]; p.font.bold = True; p.font.size = style_guide["font_sizes"]["moment_title"]; p.font.color.rgb = style_guide["colors"]["title_slide_text"]; p.alignment = PP_ALIGN.CENTER

def add_timeline_slide(prs, timeline_moments, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = style_guide["colors"]["content_slide_bg"]
    
    title_shape = slide.shapes.add_textbox(Inches(1), Inches(0.5), Inches(14), Inches(1.5))
    p = title_shape.text_frame.paragraphs[0]; p.text = "TIMELINE"; p.font.name = style_guide["fonts"]["heading"]; p.font.bold = True; p.font.size = style_guide["font_sizes"]["title"]; p.font.color.rgb = style_guide["colors"]["content_heading_text"]; p.alignment = PP_ALIGN.CENTER

    if not timeline_moments: return
    fig, ax = plt.subplots(figsize=(14, 2)); fig.patch.set_facecolor(f'#{style_guide["colors"]["content_slide_bg"]}'); ax.set_facecolor(f'#{style_guide["colors"]["content_slide_bg"]}')
    ax.axhline(0, color=f'#{style_guide["colors"]["content_body_text"]}', xmin=0.05, xmax=0.95, zorder=1)
    for i, moment in enumerate(timeline_moments):
        ax.plot(i + 1, 0, 'o', markersize=20, color=f'#{style_guide["colors"]["content_heading_text"]}', zorder=2)
        ax.text(i + 1, -0.4, moment.upper(), ha='center', fontsize=14, fontname=style_guide["fonts"]["body"], color=f'#{style_guide["colors"]["content_body_text"]}')
    ax.axis('off'); plot_stream = BytesIO(); plt.savefig(plot_stream, format='png', bbox_inches='tight', transparent=True); plt.close(fig); plot_stream.seek(0)
    slide.shapes.add_picture(plot_stream, Inches(1), Inches(3), width=Inches(14))

def add_df_to_slide(prs, df, slide_title, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = style_guide["colors"]["content_slide_bg"]
    
    title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(15), Inches(1))
    p = title_shape.text_frame.paragraphs[0]; p.text = slide_title; p.font.name = style_guide['fonts']['heading']; p.font.size = style_guide['font_sizes']['content_title']; p.font.color.rgb = style_guide['colors'].get("content_heading_text")

    rows, cols = df.shape; table = slide.shapes.add_table(rows + 1, cols, Inches(0.5), Inches(1.2), Inches(15), Inches(0.8)).table
    table.columns[0].width = Inches(3.5)
    for i in range(1, cols): table.columns[i].width = Inches(2.0)
    for i, col_name in enumerate(df.columns): table.cell(0, i).text = col_name
    for r in range(rows):
        for c in range(cols): table.cell(r + 1, c).text = str(df.iloc[r, c])
    apply_table_style_pptx(table, style_guide)
