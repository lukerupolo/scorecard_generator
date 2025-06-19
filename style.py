from pptx.dml.color import RGBColor
from pptx.util import Pt

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return RGBColor.from_string(hex_color)

STYLE_PRESETS = {
    "FC_Custom": {
        "colors": {
            "title_slide_bg": hex_to_rgb("000000"),
            "title_slide_text": hex_to_rgb("EEEEEE"),
            "content_slide_bg": hex_to_rgb("000000"),
            "content_heading_text": hex_to_rgb("00F468"),
            "content_body_text": hex_to_rgb("FFFFFF"),
            "table_header_bg": hex_to_rgb("00F468"),
            "table_header_text": hex_to_rgb("000000"),
            # NEW: Single background color for all table rows
            "table_row_bg": hex_to_rgb("4E4E4E"),
        },
        "fonts": {"heading": "Inter", "body": "Inter"},
    },
    "Battlefield": {
        # ... (other presets remain the same)
    },
    "Apex": {
        # ... (other presets remain the same)
    }
}

SHARED_FONT_SIZES = {
    "title": Pt(44), "subtitle": Pt(24), "moment_title": Pt(54),
    "content_title": Pt(32), "table_header": Pt(11), "table_body": Pt(10)
}

for preset in STYLE_PRESETS.values():
    preset["font_sizes"] = SHARED_FONT_SIZES
