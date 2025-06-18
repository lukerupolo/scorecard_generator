from pptx.dml.color import RGBColor
from pptx.util import Pt

# This dictionary holds the hardcoded "Dark Mode" style.
# Edit these values to change the theme of the presentation.
BRAND_STYLE = {
    "colors": {
        "primary": RGBColor(0, 225, 0),          # A vibrant Green for headings/accents
        "accent": RGBColor(0, 200, 0),           # A slightly darker green
        "text_light": RGBColor(255, 255, 255),   # White for all text
        "background": RGBColor(0, 0, 0),         # Black for slide background
        "background_alt": RGBColor(40, 40, 40),  # Dark grey for table rows
    },
    "fonts": {"heading": "Inter", "body": "Inter"},
    "font_sizes": {
        "title": Pt(36),
        "subtitle": Pt(24),
        "body": Pt(12),
        "table_header": Pt(11),
        "table_body": Pt(10)
    }
}
