from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from io import BytesIO
import matplotlib.pyplot as plt
import requests 
import streamlit as st

# ================================================================================
# Main Presentation Creation Function
# ================================================================================
def create_presentation(title, subtitle, scorecard_moments, sheets_dict, style_guide, region_prompt, openai_api_key):
    """Creates and returns a PowerPoint presentation as a BytesIO buffer."""
    prs = Presentation()
    prs.slide_width = Inches(16)
    prs.slide_height = Inches(9)

    add_title_slide(prs, title, subtitle, style_guide, region_prompt, openai_api_key)
    add_timeline_slide(prs, scorecard_moments, style_guide)

    total_moments = len(scorecard_moments)
    if total_moments > 0:
        progress_text = "Generating AI background images... (This can take a moment)"
        image_progress_bar = st.progress(0, text=progress_text)

        for i, moment in enumerate(scorecard_moments):
            image_progress_bar.progress((i + 1) / total_moments, text=f"Generating image for '{moment}'...")
            add_moment_title_slide(prs, f"SCORECARD:\n{moment.upper()}", style_guide, region_prompt, openai_api_key)
            for sheet_name, scorecard_df in sheets_dict.items():
                if sheet_name.lower() != "benchmark":
                    add_df_to_slide(prs, scorecard_df, f"{moment.upper()} METRICS: {sheet_name.upper()}", style_guide)
        
        image_progress_bar.empty()

    ppt_buffer = BytesIO()
    prs.save(ppt_buffer)
    ppt_buffer.seek(0)
    return ppt_buffer

# ================================================================================
# AI Background Image Generation
# ================================================================================
def generate_and_add_background_image(slide, region, style_guide, api_key, slide_width, slide_height, prompt_detail="football culture"):
    """Generates an image using the OpenAI API and adds it as the slide background."""
    prompt = f"Dark, gritty, artistic representation of {prompt_detail} in {region}, cinematic, ultra-realistic photo, dramatic lighting, epic style"
    
    if not api_key:
        st.warning("OpenAI API key is missing. Using a solid background.")
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb = style_guide["colors"]["title_slide_bg"]
        return

    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1792x1024", "response_format": "url"}
        api_url = "https://api.openai.com/v1/images/generations"
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        
        image_url = response.json()['data'][0]['url']
        image_response = requests.get(image_url, timeout=15); image_response.raise_for_status()
        image_stream = BytesIO(image_response.content)

        pic = slide.shapes.add_picture(image_stream, Inches(0), Inches(0), width=slide_width, height=slide_height)
        slide.shapes._spTree.remove(pic._element)
        slide.shapes._spTree.insert(2, pic._element)

    except requests.exceptions.RequestException as e:
        st.error(f"Image generation for '{region}' failed: {e}. Using a solid background.")
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb = style_guide["colors"]["title_slide_bg"]

# ================================================================================
# Helper functions for slide creation and styling
# ================================================================================
def add_title_slide(prs, title_text, subtitle_text, style_guide, region, api_key):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    generate_and_add_background_image(slide, region, style_guide, api_key, prs.slide_width, prs.slide_height, prompt_detail="a cinematic football stadium")
    
    title_shape = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(14), Inches(2))
    p = title_shape.text_frame.paragraphs[0]; p.text = title_text.upper(); p.font.name = style_guide["fonts"]["heading"]; p.font.bold = True; p.font.size = style_guide["font_sizes"]["title"]; p.font.color.rgb = style_guide["colors"]["title_slide_text"]; p.alignment = PP_ALIGN.CENTER

    subtitle_shape = slide.shapes.add_textbox(Inches(1), Inches(4.5), Inches(14), Inches(1.5))
    p = subtitle_shape.text_frame.paragraphs[0]; p.text = subtitle_text; p.font.name = style_guide["fonts"]["body"]; p.font.size = style_guide["font_sizes"]["subtitle"]; p.font.color.rgb = style_guide["colors"]["title_slide_text"]; p.alignment = PP_ALIGN.CENTER

def add_moment_title_slide(prs, title_text, style_guide, region, api_key):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    generate_and_add_background_image(slide, region, style_guide, api_key, prs.slide_width, prs.slide_height)
    
    txBox = slide.shapes.add_textbox(Inches(1), Inches(3.5), Inches(14), Inches(3))
    p = txBox.text_frame.paragraphs[0]; p.text = title_text; p.font.name = style_guide["fonts"]["heading"]; p.font.bold = True; p.font.size = style_guide["font_sizes"]["moment_title"]; p.font.color.rgb = style_guide["colors"]["title_slide_text"]; p.alignment = PP_ALIGN.CENTER

def add_timeline_slide(prs, timeline_moments, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.background.fill.solid(); slide.background.fill.fore_color.rgb = style_guide["colors"]["content_slide_bg"]
    
    title_shape = slide.shapes.add_textbox(Inches(1), Inches(0.5), Inches(14), Inches(1.5))
    p = title_shape.text_frame.paragraphs[0]; p.text = "TIMELINE"; p.font.name = style_guide["fonts"]["heading"]; p.font.bold = True; p.font.size = style_guide["font_sizes"]["title"]; p.font.color.rgb = style_guide["colors"]["content_heading_text"]; p.alignment = PP_ALIGN.CENTER

    if not timeline_moments: return
    
    fig, ax = plt.subplots(figsize=(14, 2.5)) # Increased height slightly
    fig.patch.set_facecolor(f'#{style_guide["colors"]["content_slide_bg"]}')
    ax.set_facecolor(f'#{style_guide["colors"]["content_slide_bg"]}')
    ax.axhline(0, color=f'#{style_guide["colors"]["content_body_text"]}', xmin=0.05, xmax=0.95, zorder=1, linewidth=2)
    
    for i, moment in enumerate(timeline_moments):
        ax.plot(i + 1, 0, 'o', markersize=20, color=f'#{style_guide["colors"]["content_heading_text"]}', zorder=2)
        
        # --- FIXED TEXT RENDERING ---
        # 1. Use a standard 'sans-serif' font for compatibility.
        # 2. Add a semi-transparent background box to ensure text is always visible.
        text_props = dict(boxstyle='round,pad=0.4', facecolor='black', alpha=0.5, edgecolor='none')
        ax.text(
            x=i + 1, y=-0.2, s=moment.upper(),
            ha='center', va='top', fontsize=14,
            fontname='sans-serif', # Use a safe, standard font
            color=f'#{style_guide["colors"]["content_body_text"]}', # White text
            bbox=text_props
        )
        # --- END FIX ---
    
    ax.axis('off')
    plt.tight_layout(pad=0)
    plot_stream = BytesIO()
    plt.savefig(plot_stream, format='png', facecolor=fig.get_facecolor(), transparent=False)
    plt.close(fig)
    plot_stream.seek(0)
    
    slide.shapes.add_picture(plot_stream, Inches(1), Inches(3), width=Inches(14))

def apply_table_style_pptx(table, style_guide):
    header_bg, header_text = style_guide["colors"]["table_header_bg"], style_guide["colors"]["table_header_text"]
    body_text, alt_bg = style_guide["colors"]["content_body_text"], style_guide["colors"]["table_alt_row_bg"]
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

def add_df_to_slide(prs, df, slide_title, style_guide):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.background.fill.solid(); slide.background.fill.fore_color.rgb = style_guide["colors"]["content_slide_bg"]
    
    title_shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(15), Inches(1))
    p = title_shape.text_frame.paragraphs[0]; p.text = slide_title; p.font.name = style_guide['fonts']['heading']; p.font.size = style_guide['font_sizes']['content_title']; p.font.color.rgb = style_guide['colors'].get("content_heading_text")

    rows, cols = df.shape; table = slide.shapes.add_table(rows + 1, cols, Inches(0.5), Inches(1.2), Inches(15), Inches(0.8)).table
    table.columns[0].width = Inches(3.5)
    for i in range(1, cols): table.columns[i].width = Inches(2.0)
    for i, col_name in enumerate(df.columns): table.cell(0, i).text = col_name
    for r in range(rows):
        for c in range(cols): table.cell(r + 1, c).text = str(df.iloc[r, c])
    apply_table_style_pptx(table, style_guide)
