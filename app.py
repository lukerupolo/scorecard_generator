import streamlit as st
from io import BytesIO
from datetime import datetime
import pandas as pd

# --- Local Imports from our other files ---
from style import STYLE_PRESETS 
from ui import render_sidebar
from data_processing import process_scorecard_data, calculate_benchmark_summary
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
        selected_metrics = st.multiselect("Select metrics:", options=["Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions"], default=["Video Views (VOD)"])
        if st.form_submit_button("Confirm Metrics & Proceed →", type="primary"):
            st.session_state.metrics = selected_metrics
            st.session_state.metrics_confirmed = True
            st.rerun()

# ================================================================================
# Step 2: Optional Benchmark Calculation
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Benchmark Calculation (Optional)")
    
    benchmark_choice = st.radio(
        "Would you like to calculate proposed benchmark values in this session using historical data?",
        ("No, I will enter benchmarks manually later.", "Yes, calculate benchmarks from past events."),
        key="benchmark_choice_radio"
    )
    st.session_state.benchmark_choice = benchmark_choice

    if benchmark_choice == "Yes, calculate benchmarks from past events.":
        with st.form("benchmark_data_form"):
            st.info("For each metric, enter the Baseline and Actual values from past events to calculate a new proposed benchmark.")
            
            # This dictionary will hold the user's input for each metric
            historical_data_input = {}

            for metric in st.session_state.metrics:
                st.markdown(f"#### Data for: **{metric}**")
                n_rows = st.number_input(f"Number of past events for '{metric}'", min_value=1, max_value=10, value=2, key=f"rows_{metric}")
                
                # Create a blank DataFrame for the user to fill in
                df_template = pd.DataFrame([{"Baseline (7-day)": None, "Actual (7-day)": None} for _ in range(n_rows)])
                
                edited_df = st.data_editor(df_template, key=f"editor_{metric}", num_rows="dynamic")
                historical_data_input[metric] = edited_df

            if st.form_submit_button("Calculate All Proposed Benchmarks & Proceed →", type="primary"):
                proposed_benchmarks = {}
                summary_rows = []
                with st.spinner("Analyzing historical data..."):
                    for metric, df_input in historical_data_input.items():
                        summary = calculate_benchmark_summary(df_input)
                        if summary:
                            summary['Metric'] = metric
                            summary_rows.append(summary)
                            proposed_benchmarks[metric] = summary.get("Proposed Benchmark")
                
                # Store the results in session state
                st.session_state.benchmark_df = pd.DataFrame(summary_rows)
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
    # ... (Event config and scorecard generation logic remains the same)
    
    if st.session_state.get('show_ppt_creator'):
        st.header("Step 5: Create Presentation")
        # ... (PPT creation logic remains the same)
