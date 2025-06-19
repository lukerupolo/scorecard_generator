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
for key in ['openai_api_key', 'metrics', 'benchmark_choice', 'benchmark_df', 'sheets_dict', 'presentation_buffer', 'events_config', 'proposed_benchmarks']:
     if key not in st.session_state: st.session_state[key] = None

st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar()

# ================================================================================
# Step 0 & 1: API Key and Metric Selection
# ================================================================================
if not st.session_state.api_key_entered:
    st.header("Step 0: Enter Your OpenAI API Key")
    with st.form("api_key_form"):
        api_key_input = st.text_input("🔑 OpenAI API Key", type="password")
        if st.form_submit_button("Submit API Key"):
            st.session_state.openai_api_key = api_key_input
            st.session_state.api_key_entered = True
            st.rerun()

elif not st.session_state.metrics_confirmed:
    st.header("Step 1: Metric Selection")
    with st.form("metrics_form"):
        selected_metrics = st.multiselect("Select metrics:", options=["Video views (Franchise)", "Social Impressions", "Press UMV (unique monthly views)"], default=["Video views (Franchise)"])
        if st.form_submit_button("Confirm Metrics & Proceed →", type="primary"):
            st.session_state.metrics = selected_metrics
            st.session_state.metrics_confirmed = True
            st.rerun()

# ================================================================================
# Step 2: Optional Benchmark Calculation (Corrected Workflow)
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Benchmark Calculation (Optional)")
    
    benchmark_choice = st.radio(
        "Would you like to calculate proposed benchmark values in this session using historical data?",
        ("No, I will enter benchmarks manually later.", "Yes, calculate benchmarks from past events."),
        key="benchmark_choice_radio"
    )

    if benchmark_choice == "Yes, calculate benchmarks from past events.":
        with st.form("benchmark_data_form"):
            st.info("For each metric below, enter the Baseline and Actual values from past events.")
            
            historical_data_input = {}
            for metric in st.session_state.metrics:
                st.markdown(f"#### Data for: **{metric}**")
                # Create a blank DataFrame for the user to fill in historical data for this metric
                df_template = pd.DataFrame([{"Event Name": f"Past Event {i+1}", "Baseline (7-day)": None, "Actual (7-day)": None} for i in range(2)]) # Start with 2 empty rows
                
                edited_df = st.data_editor(df_template, key=f"hist_editor_{metric}", num_rows="dynamic", use_container_width=True)
                historical_data_input[metric] = edited_df

            if st.form_submit_button("Calculate All Proposed Benchmarks & Proceed →", type="primary"):
                with st.spinner("Analyzing historical data..."):
                    # Pass the dictionary of metric data to the calculation function
                    benchmark_summary_df, proposed_benchmarks = calculate_all_benchmarks(historical_data_input)
                    st.session_state.benchmark_df = benchmark_summary_df
                    st.session_state.proposed_benchmarks = proposed_benchmarks
                    st.session_state.benchmark_flow_complete = True
                st.rerun()
    else:
        if st.button("Proceed to Event Configuration →", type="primary"):
            st.session_state.benchmark_flow_complete = True
            st.rerun()

# ================================================================================
# Step 3, 4, 5 - Main App Logic
# ================================================================================
else:
    app_config = {
        'openai_api_key': st.session_state.openai_api_key, 
        'metrics': st.session_state.metrics,
        'proposed_benchmarks': st.session_state.get('proposed_benchmarks')
    }
    
    st.header("Step 3: Configure Events & Generate Scorecard")
    # ... (Event config logic is unchanged)
    
    # ... The rest of the app logic remains the same
