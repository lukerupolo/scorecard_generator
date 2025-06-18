from pptx.dml.color import RGBColor
from pptx.util import Pt

def hex_to_rgb(hex_color):
    """Converts a hex color string to an RGBColor object."""
    hex_color = hex_color.lstrip('#')
    return RGBColor.from_string(hex_color)

# This dictionary holds all the available style presets for the presentation.

STYLE_PRESETS = {
    "FC_Custom": {
        "colors": {
            # Colors for Section Title Slides (black background)
            "title_slide_bg": hex_to_rgb("000000"),
            "title_slide_text": hex_to_rgb("EEEEEE"),

            # Colors for Content Slides (e.g., tables, timeline)
            "content_slide_bg": hex_to_rgb("000000"),
            "content_heading_text": hex_to_rgb("00F468"),
            "content_body_text": hex_to_rgb("FFFFFF"),
            
            # Colors for Tables
            "table_header_bg": hex_to_rgb("00F468"),
            "table_header_text": hex_to_rgb("000000"), # Black text on green header
            "table_alt_row_bg": hex_to_rgb("282828"),   # Dark grey for alternating rows
        },
        "fonts": {
            "heading": "Inter", 
            "body": "Inter"
        },
    },
    # --- You can keep the other presets for easy switching ---
    "Battlefield": {
        "colors": {
            "title_slide_bg": hex_to_rgb("1B1C1E"), "title_slide_text": hex_to_rgb("FF8700"),
            "content_slide_bg": hex_to_rgb("1B1C1E"), "content_heading_text": hex_to_rgb("FF8700"), "content_body_text": hex_to_rgb("FFFFFF"),
            "table_header_bg": hex_to_rgb("FF8700"), "table_header_text": hex_to_rgb("000000"), "table_alt_row_bg": hex_to_rgb("323438"),
        },
        "fonts": {"heading": "Arial Black", "body": "Arial"},
    },
    "Apex": {
        "colors": {
            "title_slide_bg": hex_to_rgb("222222"), "title_slide_text": hex_to_rgb("DA292A"),
            "content_slide_bg": hex_to_rgb("222222"), "content_heading_text": hex_to_rgb("DA292A"), "content_body_text": hex_to_rgb("FFFFFF"),
            "table_header_bg": hex_to_rgb("DA292A"), "table_header_text": hex_to_rgb("FFFFFF"), "table_alt_row_bg": hex_to_rgb("3C3C3C"),
        },
        "fonts": {"heading": "Verdana", "body": "Verdana"},
    }
}

# --- Shared Font Sizes ---
SHARED_FONT_SIZES = {
    "title": Pt(44),
    "subtitle": Pt(24),
    "moment_title": Pt(54),
    "content_title": Pt(32),
    "table_header": Pt(11),
    "table_body": Pt(10)
}

# Add the shared font sizes to each preset
for preset in STYLE_PRESETS.values():
    preset["font_sizes"] = SHARED_FONT_SIZES
