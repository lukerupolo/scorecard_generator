import streamlit as st
from io import BytesIO

# --- Local Imports from our other files ---
from style import STYLE_PRESETS 
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
# The render_sidebar function from ui.py handles all sidebar logic
# and returns the user's configurations.
app_config = render_sidebar()

# ================================================================================
# 3) Main Page: Scorecard Generation
# ================================================================================
st.header("Step 1: Generate Scorecard Data")
if st.button("✅ Generate Scorecard Data", use_container_width=True):
    with st.spinner("Fetching data and building scorecards..."):
        # This function now correctly processes all events from the sidebar
        sheets_dict = process_scorecard_data(app_config)
        st.session_state["sheets_dict"] = sheets_dict
        st.session_state["scorecard_ready"] = True
    st.rerun()

# ================================================================================
# 4) Main Page: Display and EDIT Scorecards
# ================================================================================
if st.session_state.scorecard_ready and st.session_state.sheets_dict:
    st.markdown("---")
    st.header("Step 2: Review & Edit Data")
    
    # Create a copy of the dictionary to avoid issues while iterating
    sheets_copy = st.session_state.sheets_dict.copy()

    for name, df in sheets_copy.items():
        st.markdown(f"#### Edit Scorecard: {name}")
        
        # Use st.data_editor to make the table interactive
        edited_df = st.data_editor(
            df,
            key=f"editor_{name}", # A unique key for each data editor
            use_container_width=True,
            num_rows="dynamic",
            # Configure the Category column to be wider
            column_config={
                "Category": st.column_config.TextColumn(width="medium"),
            }
        )
        
        # Update the main session state with any edits made by the user
        st.session_state.sheets_dict[name] = edited_df
    
    st.markdown("---")

    # --- Benchmark and Download Buttons ---
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
            use_container_width=True
        )

    with st.form("ppt_form"):
        st.subheader("Presentation Style & Details")
        
        col1, col2 = st.columns(2)
        selected_style_name = col1.radio("Select Style Preset:", options=list(STYLE_PRESETS.keys()), horizontal=True)
        image_region_prompt = col2.text_input("Region for AI Background Image", "Brazil")

        ppt_title = st.text_input("Presentation Title", "Game Scorecard")
        ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
        moments_input = st.text_area("Scorecard Moments (one per line)", "Pre-Reveal\nLaunch", height=100)
        submitted = st.form_submit_button("Generate Presentation", use_container_width=True)

        if submitted:
            if not app_config.get('openai_api_key'):
                st.error("Please enter your OpenAI API key in the sidebar to generate images.")
            elif not st.session_state.get("sheets_dict"):
                st.error("Please generate scorecard data first.")
            else:
                with st.spinner(f"Building presentation with {selected_style_name} style..."):
                    style_guide = STYLE_PRESETS[selected_style_name]
                    scorecard_moments = [moment.strip() for moment in moments_input.split('\n') if moment.strip()]

                    # The create_presentation function will now use the edited data from the session state
                    ppt_buffer = create_presentation(
                        title=ppt_title,
                        subtitle=ppt_subtitle,
                        scorecard_moments=scorecard_moments,
                        sheets_dict=st.session_state.sheets_dict,
                        style_guide=style_guide,
                        region_prompt=image_region_prompt,
                        openai_api_key=app_config['openai_api_key'] 
                    )
                    st.session_state["presentation_buffer"] = ppt_buffer
                    st.rerun()
