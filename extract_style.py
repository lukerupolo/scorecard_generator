from pptx import Presentation
from pptx.dml.color import RGBColor

def extract_presentation_style(pptx_file):
    """
    Analyzes a .pptx file and prints its theme colors and fonts.
    """
    try:
        prs = Presentation(pptx_file)
        print(f"🎨 Style analysis for: {pptx_file}\n")

        # --- 1. Extract Theme Colors ---
        print("="*10 + " THEME COLORS " + "="*10)
        color_scheme = prs.theme.theme_elements.clr_scheme
        
        # Dictionary to hold the extracted colors
        colors = {}

        color_map = {
            'dk1': 'Text/Background - Dark 1',
            'lt1': 'Text/Background - Light 1',
            'dk2': 'Text/Background - Dark 2',
            'lt2': 'Text/Background - Light 2',
            'accent1': 'Accent 1',
            'accent2': 'Accent 2',
            'accent3': 'Accent 3',
            'accent4': 'Accent 4',
            'accent5': 'Accent 5',
            'accent6': 'Accent 6',
            'hlink': 'Hyperlink',
            'folHlink': 'Followed Hyperlink',
        }
        
        for color_name, mapped_name in color_map.items():
            color_obj = getattr(color_scheme, color_name)
            if hasattr(color_obj, 'rgb'):
                rgb = color_obj.rgb
                colors[color_name] = rgb
                print(f"- {mapped_name:<28} | RGB: ({rgb.r:3}, {rgb.g:3}, {rgb.b:3}) | Hex: #{rgb}")

        # --- 2. Extract Theme Fonts ---
        print("\n" + "="*10 + " THEME FONTS " + "="*12)
        font_scheme = prs.theme.theme_elements.font_scheme
        major_font = font_scheme.major_font.latin
        minor_font = font_scheme.minor_font.latin
        
        print(f"- Heading Font (Major): {major_font}")
        print(f"- Body Font (Minor):    {minor_font}")
        
        print("\n✨ Analysis complete. Use the RGB values and font names below to update your BRAND_STYLE dictionary.")
        
        return colors, major_font, minor_font

    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None, None

if __name__ == "__main__":
    # =================================================================
    # TODO: IMPORTANT! Replace this with the name of your presentation
    # =================================================================
    presentation_file_to_copy = "FC 26 MENA SCORECARDS OVERVIEW (1).pptx"
    # =================================================================
    
    
    extracted_colors, heading_font, body_font = extract_presentation_style(presentation_file_to_copy)
