from pptx.dml.color import RGBColor
from pptx.util import Pt

# This dictionary holds all the available style presets for the presentation.

STYLE_PRESETS = {
    "FC": {
        "colors": {
            "primary": RGBColor(0, 225, 0),          # A vibrant Green for headings/accents
            "accent": RGBColor(0, 200, 0),           # A slightly darker green
            "text_light": RGBColor(255, 255, 255),   # White for all text
            "background": RGBColor(0, 0, 0),         # Black for slide background
            "background_alt": RGBColor(40, 40, 40),  # Dark grey for table rows
        },
        "fonts": {"heading": "Inter", "body": "Inter"},
    },
    "Battlefield": {
        "colors": {
            "primary": RGBColor(255, 135, 0),        # Battlefield Orange
            "accent": RGBColor(0, 153, 221),         # Battlefield Blue
            "text_light": RGBColor(255, 255, 255),   # White text
            "background": RGBColor(27, 28, 30),      # Very dark grey background
            "background_alt": RGBColor(50, 52, 56),  # Lighter dark grey for table rows
        },
        "fonts": {"heading": "Arial Black", "body": "Arial"},
    },
    "Apex": {
        "colors": {
            "primary": RGBColor(218, 41, 42),        # Apex Red
            "accent": RGBColor(255, 255, 255),       # White accent
            "text_light": RGBColor(255, 255, 255),   # White text
            "background": RGBColor(34, 34, 34),      # Dark charcoal background
            "background_alt": RGBColor(60, 60, 60),  # Lighter charcoal for table rows
        },
        "fonts": {"heading": "Verdana", "body": "Verdana"},
    }
}

# --- Shared Font Sizes ---
# You can also move these into each preset if you want different sizes per theme.
SHARED_FONT_SIZES = {
    "title": Pt(36),
    "subtitle": Pt(24),
    "body": Pt(12),
    "table_header": Pt(11),
    "table_body": Pt(10)
}

# Add the shared font sizes to each preset
for preset in STYLE_PRESETS.values():
    preset["font_sizes"] = SHARED_FONT_SIZES

