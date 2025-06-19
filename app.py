import streamlit as st
from io import BytesIO
from datetime import datetime
import pandas as pd

# --- Local Imports from our other files ---
from style import STYLE_PRESETS 
from ui import render_sidebar
from data_processing import process_scorecard_data, calculate_all_benchmarks
from powerpoint import create_presentation
from excel import create_excel_workbook

# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# Initialize session state keys
for key in ['api_key_entered', 'metrics_confirmed', 'benchmark_flow_complete', 'scorecard_ready', 'show_ppt_creator']:
    if key not in st.session_state: st.session_state[key] = False
for key in ['openai_api_key', 'metrics', 'benchmark_choice', 'benchmark_df', 'sheets_dict', 'presentation_buffer', 'proposed_benchmarks', 'saved_moments']:
     if key not in st.session_state: st.session_state[key] = None

# Initialize saved_moments as a dictionary if it's None
if st.session_state.saved_moments is None:
    st.session_state.saved_moments = {}

st.title("Event Marketing Scorecard & Presentation Generator")
app_config = render_sidebar()

# ================================================================================
# Step 0 & 1: API Key and Metric Selection
# ================================================================================
if not st.session_state.api_key_entered:
    st.header("Step 0: Enter Your OpenAI API Key")
    # ... (API Key form logic)
elif not st.session_state.metrics_confirmed:
    st.header("Step 1: Metric Selection")
    # ... (Metric Selection form logic)

# ================================================================================
# Step 2: Optional Benchmark Calculation
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Benchmark Calculation (Optional)")
    # ... (Benchmark calculation logic)

# ================================================================================
# Step 3, 4, 5 - Main App Logic
# ================================================================================
else:
    app_config['openai_api_key'] = st.session_state.openai_api_key
    app_config['metrics'] = st.session_state.metrics
    app_config['proposed_benchmarks'] = st.session_state.get('proposed_benchmarks')
    
    # --- NEW Step 3: Build & Save Scorecard Moments ---
    st.header("Step 3: Build & Save Scorecard Moments")
    
    # Create a single scorecard structure to be filled out
    if st.session_state.sheets_dict is None:
        app_config['events'] = [{"name": "Current Moment"}] # Create a temporary event
        st.session_state.sheets_dict = process_scorecard_data(app_config)

    st.info("Fill in the 'Actuals' for the current scorecard moment, give it a name, and save it. You can create multiple moments.")

    # Get the current (and only) scorecard DataFrame to edit
    current_scorecard_df = st.session_state.sheets_dict.get("Current Moment - 1")

    if current_scorecard_df is not None:
        edited_df = st.data_editor(
            current_scorecard_df,
            key="moment_editor",
            use_container_width=True,
            num_rows="dynamic"
        )
        # Recalculate difference on edit
        edited_df['Actuals'] = pd.to_numeric(edited_df['Actuals'], errors='coerce')
        edited_df['Benchmark'] = pd.to_numeric(edited_df['Benchmark'], errors='coerce')
        edited_df['% Difference'] = ((edited_df['Actuals'] - edited_df['Benchmark']) / edited_df['Benchmark']).apply(lambda x: f"{x:.1%}" if pd.notna(x) else None)
        
        # --- UI for Saving the Moment ---
        col1, col2 = st.columns([3, 1])
        moment_name = col1.text_input("Name for this Scorecard Moment", placeholder="e.g., Pre-Reveal, Launch Week")
        
        if col2.button("💾 Save Moment", use_container_width=True, type="primary"):
            if moment_name:
                st.session_state.saved_moments[moment_name] = edited_df
                st.success(f"Saved moment: '{moment_name}'")
                # Clear the current scorecard so a new one can be created
                st.session_state.sheets_dict = None
                st.rerun()
            else:
                st.error("Please enter a name for the moment before saving.")

    # Display the list of saved moments
    if st.session_state.saved_moments:
        st.markdown("---")
        st.subheader("Saved Scorecard Moments")
        for name, df in st.session_state.saved_moments.items():
            with st.expander(f"View Moment: {name}"):
                st.dataframe(df, use_container_width=True)
        st.session_state.show_ppt_creator = True

    # --- Step 4: Create Presentation ---
    if st.session_state.get('show_ppt_creator'):
        st.markdown("---")
        st.header("Step 4: Create Your Presentation")
        
        if st.session_state.get("presentation_buffer"):
            st.download_button(label="✅ Download Your Presentation!", data=st.session_state.presentation_buffer, file_name="game_scorecard_presentation.pptx", use_container_width=True)

        with st.form("ppt_form"):
            st.subheader("Presentation Style & Details")
            
            # --- NEW: Select saved moments for the presentation ---
            if st.session_state.saved_moments:
                selected_moments = st.multiselect(
                    "Select which saved moments to include in the presentation:",
                    options=list(st.session_state.saved_moments.keys()),
                    default=list(st.session_state.saved_moments.keys())
                )
            else:
                st.warning("No scorecard moments saved yet. Please save at least one moment above.")
                selected_moments = []

            col1, col2 = st.columns(2)
            selected_style_name = col1.radio("Select Style Preset:", options=list(STYLE_PRESETS.keys()), horizontal=True)
            image_region_prompt = col2.text_input("Region for AI Background Image", "Brazil")
            ppt_title = st.text_input("Presentation Title", "Game Scorecard")
            ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
            
            submitted = st.form_submit_button("Generate Presentation", use_container_width=True)

            if submitted:
                if not selected_moments:
                    st.error("Please select at least one saved moment to include in the presentation.")
                else:
                    with st.spinner(f"Building presentation with {selected_style_name} style..."):
                        # Create a dictionary containing only the data for the selected moments
                        presentation_data = {name: st.session_state.saved_moments[name] for name in selected_moments}
                        
                        style_guide = STYLE_PRESETS[selected_style_name]
                        ppt_buffer = create_presentation(
                            title=ppt_title,
                            subtitle=ppt_subtitle,
                            scorecard_moments=selected_moments, # The list of names for the timeline
                            sheets_dict=presentation_data,     # The dict of DataFrames for the slides
                            style_guide=style_guide,
                            region_prompt=image_region_prompt,
                            openai_api_key=st.session_state.openai_api_key 
                        )
                        st.session_state["presentation_buffer"] = ppt_buffer
                        st.rerun()
