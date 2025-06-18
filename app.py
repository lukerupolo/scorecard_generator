import streamlit as st
from io import BytesIO

# --- Local Imports from our other files ---
from style import STYLE_PRESETS # Import the dictionary of presets
from ui import render_sidebar
from data_processing import process_scorecard_data
from powerpoint import create_presentation
from excel import create_excel_workbook

# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# Initialize session state keys to avoid errors on first run
for key in ['scorecard_ready', 'show_ppt_creator']:
    if key not in st.session_state:
        st.session_state[key] = False
for key in ['sheets_dict', 'presentation_buffer']:
     if key not in st.session_state:
        st.session_state[key] = None

st.title("Event Marketing Scorecard & Presentation Generator")

# ================================================================================
# 2) Sidebar & Input Configuration
# ================================================================================
app_config = render_sidebar()

# ================================================================================
# 3) Main Page: Scorecard Generation
# ================================================================================
st.header("Step 1: Generate Scorecard Data")
if st.button("✅ Generate Scorecard Data", use_container_width=True):
    with st.spinner("Fetching data and building scorecards..."):
        sheets_dict = process_scorecard_data(app_config)
        st.session_state["sheets_dict"] = sheets_dict
        st.session_state["scorecard_ready"] = True
    st.rerun()

# ================================================================================
# 4) Main Page: Display Scorecards, Benchmark, and Download Buttons
# ================================================================================
if st.session_state.scorecard_ready and st.session_state.sheets_dict:
    st.markdown("---")
    st.header("Step 2: Review Data & Download")
    for name, df in st.session_state.sheets_dict.items():
        st.markdown(f"#### {name}"); st.dataframe(df, use_container_width=True)
    
    col1, col2 = st.columns(2)
    if col1.button("🎯 Generate Proposed Benchmark", use_container_width=True):
        st.info("Benchmark logic would run here to update sheets_dict.")

    if st.session_state.sheets_dict:
        excel_buffer = create_excel_workbook(st.session_state.sheets_dict)
        col2.download_button(
            label="📥 Download as Excel Workbook",
            data=excel_buffer,
            file_name="full_scorecard.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    st.markdown("---")
    st.session_state['show_ppt_creator'] = True

# ================================================================================
# 5) Main Page: PowerPoint UI
# ================================================================================
if st.session_state.get('show_ppt_creator'):
    st.header("Step 3: Create Your Presentation")
    if st.session_state.get("presentation_buffer"):
        st.download_button(
            label="✅ Download Your Presentation!",
            data=st.session_state.presentation_buffer,
            file_name="game_scorecard_presentation.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True
        )

    with st.form("ppt_form"):
        st.subheader("Presentation Style & Details")
        
        # NEW: Radio buttons to select the style preset
        selected_style_name = st.radio(
            "Select Presentation Style:",
            options=list(STYLE_PRESETS.keys()),
            horizontal=True,
            key="style_selector"
        )
        
        ppt_title = st.text_input("Presentation Title", "Game Scorecard")
        ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
        
        # NEW: Text area for custom timeline moments
        moments_input = st.text_area(
            "Scorecard Moments for Timeline (one per line)",
            "Pre-Reveal\nReveal\nLaunch\nPost-Launch",
            height=100
        )

        submitted = st.form_submit_button("Generate Presentation", use_container_width=True)

        if submitted:
            if not st.session_state.get("sheets_dict"):
                st.error("Please generate scorecard data first.")
            else:
                with st.spinner(f"Building presentation with {selected_style_name} style..."):
                    # Get the selected style dictionary
                    style_guide = STYLE_PRESETS[selected_style_name]
                    
                    # Parse the custom moments from the text area
                    scorecard_moments = [moment.strip() for moment in moments_input.split('\n') if moment.strip()]

                    ppt_buffer = create_presentation(
                        title=ppt_title,
                        subtitle=ppt_subtitle,
                        scorecard_moments=scorecard_moments,
                        sheets_dict=st.session_state.sheets_dict,
                        style_guide=style_guide
                    )
                    st.session_state["presentation_buffer"] = ppt_buffer
                    st.rerun()
