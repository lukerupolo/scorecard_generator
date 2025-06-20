import streamlit as st
from io import BytesIO
from datetime import datetime
import pandas as pd

# --- Local Imports from our other files ---
from style import STYLE_PRESETS 
from ui import render_sidebar
from data_processing import process_scorecard_data, generate_benchmark_summary
from powerpoint import create_presentation
from excel import create_excel_workbook

# ================================================================================
# 1) App State Initialization (Robust Version)
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# This versioning system forces the app state to reset when you update the code.
APP_VERSION = "1.0.1" 

if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    # Preserve the API key if it exists
    api_key = st.session_state.get('openai_api_key')
    
    # Clear all keys from the session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # Now, initialize all keys to their default values
    st.session_state.app_version = APP_VERSION
    st.session_state.api_key_entered = True if api_key else False
    st.session_state.openai_api_key = api_key
    st.session_state.metrics_confirmed = False
    st.session_state.benchmark_flow_complete = False
    st.session_state.scorecard_ready = False
    st.session_state.show_ppt_creator = False
    st.session_state.metrics = []
    st.session_state.benchmark_choice = "No, I will enter benchmarks manually later."
    st.session_state.benchmark_df = pd.DataFrame()
    st.session_state.sheets_dict = {}
    st.session_state.presentation_buffer = None
    st.session_state.events_config = []
    st.session_state.proposed_benchmarks = {}
    st.session_state.saved_moments = {}


st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar()

# ================================================================================
# Step 0: API Key Entry
# ================================================================================
if not st.session_state.api_key_entered:
    st.header("Step 0: Enter Your OpenAI API Key")
    with st.form("api_key_form"):
        api_key_input = st.text_input("🔑 OpenAI API Key", type="password")
        if st.form_submit_button("Submit API Key"):
            if api_key_input:
                st.session_state.openai_api_key = api_key_input
                st.session_state.api_key_entered = True
                st.rerun()
            else:
                st.error("Please enter a valid OpenAI API key.")

# ================================================================================
# Step 1: Metric Selection
# ================================================================================
elif not st.session_state.metrics_confirmed:
    st.header("Step 1: Metric Selection")
    with st.form("metrics_form"):
        selected_metrics = st.multiselect("Select metrics:", options=["Video views (Franchise)", "Social Impressions", "Press UMV (unique monthly views)"], default=["Video views (Franchise)"])
        if st.form_submit_button("Confirm Metrics & Proceed →", type="primary"):
            if not selected_metrics:
                st.error("Please select at least one metric.")
            else:
                st.session_state.metrics = selected_metrics
                st.session_state.metrics_confirmed = True
                st.rerun()

# ================================================================================
# Step 2: Optional Benchmark Calculation
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Benchmark Calculation (Optional)")
    
    benchmark_choice = st.radio(
        "Would you like to calculate proposed benchmark values using historical data?",
        ("No, I will enter benchmarks manually later.", "Yes, calculate benchmarks from past events."),
        key="benchmark_choice_radio"
    )

    if benchmark_choice == "Yes, calculate benchmarks from past events.":
        with st.form("benchmark_data_form"):
            st.info("For each past event, enter the Baseline and Actual values for all selected metrics.")
            n_benchmark_events = st.number_input("Number of past events to use for benchmark", min_value=1, max_value=10, value=1)
            
            historical_data_input = {}
            for i in range(n_benchmark_events):
                st.markdown(f"--- \n ##### Data for Past Event {i+1}")
                df_template = pd.DataFrame({
                    "Metric": st.session_state.metrics,
                    "Baseline (7-day)": [None] * len(st.session_state.metrics),
                    "Actual (7-day)": [None] * len(st.session_state.metrics)
                }).set_index("Metric")
                
                edited_df = st.data_editor(df_template, key=f"hist_editor_{i}", use_container_width=True)
                historical_data_input[f"Past Event {i+1}"] = edited_df.reset_index()

            if st.form_submit_button("Calculate Proposed Benchmark & Proceed →", type="primary"):
                with st.spinner("Analyzing historical data..."):
                    summary_df, proposed_benchmarks, avg_actuals = generate_benchmark_summary(historical_data_input, st.session_state.metrics)
                    st.session_state.benchmark_df = summary_df
                    st.session_state.proposed_benchmarks = proposed_benchmarks
                    st.session_state.avg_actuals = avg_actuals
                    st.session_state.benchmark_flow_complete = True
                st.rerun()
    else:
        if st.button("Proceed to Scorecard Creation →", type="primary"):
            st.session_state.benchmark_flow_complete = True
            st.rerun()

# ================================================================================
# Step 3, 4, 5 - Main App Logic
# ================================================================================
else:
    app_config = {
        'openai_api_key': st.session_state.openai_api_key, 
        'metrics': st.session_state.metrics,
        'proposed_benchmarks': st.session_state.get('proposed_benchmarks'),
        'avg_actuals': st.session_state.get('avg_actuals')
    }
    
    # --- Step 3: Build & Save Scorecard Moments ---
    st.header("Step 3: Build & Save Scorecard Moments")
    
    # Generate a blank scorecard structure if one isn't already being edited
    if st.session_state.sheets_dict is None:
        app_config['events'] = [{"name": "Current Moment"}] # A placeholder name
        st.session_state.sheets_dict = process_scorecard_data(app_config)

    st.info("Fill in the 'Actuals' for the current scorecard moment, give it a name, and save it. You can create multiple moments.")

    current_scorecard_df = next(iter(st.session_state.sheets_dict.values()), None)

    if current_scorecard_df is not None:
        edited_df = st.data_editor(
            current_scorecard_df, key="moment_editor",
            use_container_width=True, num_rows="dynamic"
        )
        edited_df['Actuals'] = pd.to_numeric(edited_df['Actuals'], errors='coerce')
        edited_df['Benchmark'] = pd.to_numeric(edited_df['Benchmark'], errors='coerce')
        edited_df['% Difference'] = ((edited_df['Actuals'] - edited_df['Benchmark']) / edited_df['Benchmark']).apply(lambda x: f"{x:.1%}" if pd.notna(x) else None)
        
        col1, col2 = st.columns([3, 1])
        moment_name = col1.text_input("Name for this Scorecard Moment", placeholder="e.g., Pre-Reveal, Launch Week")
        
        if col2.button("💾 Save Moment", use_container_width=True, type="primary"):
            if moment_name:
                st.session_state.saved_moments[moment_name] = edited_df
                st.success(f"Saved moment: '{moment_name}'")
                st.session_state.sheets_dict = None # Clear the editor for the next moment
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
            
            if st.session_state.saved_moments:
                selected_moments = st.multiselect("Select which saved moments to include in the presentation:",
                    options=list(st.session_state.saved_moments.keys()),
                    default=list(st.session_state.saved_moments.keys()))
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
                        presentation_data = {name: st.session_state.saved_moments[name] for name in selected_moments}
                        style_guide = STYLE_PRESETS[selected_style_name]
                        ppt_buffer = create_presentation(
                            title=ppt_title,
                            subtitle=ppt_subtitle,
                            scorecard_moments=selected_moments,
                            sheets_dict=presentation_data,
                            style_guide=style_guide,
                            region_prompt=image_region_prompt,
                            openai_api_key=st.session_state.openai_api_key 
                        )
                        st.session_state["presentation_buffer"] = ppt_buffer
                        st.rerun()
