import streamlit as st
from io import BytesIO
from datetime import datetime
import pandas as pd

# --- Local Imports from our other files ---
from style import STYLE_PRESETS 
from ui import render_sidebar
from data_processing import process_scorecard_data, generate_proposed_benchmark
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
        key="benchmark_choice_radio",
        index=0 if st.session_state.benchmark_choice is None else 1 # Keep selection
    )
    st.session_state.benchmark_choice = benchmark_choice

    if benchmark_choice == "Yes, calculate benchmarks from past events.":
        with st.form("benchmark_data_form"):
            st.info("Enter the Baseline and Actual values for each metric across your past events.")
            n_benchmark_events = st.number_input("Number of past events to use for benchmark", min_value=1, max_value=5, value=1)
            
            benchmark_events_data = {}
            for i in range(n_benchmark_events):
                st.markdown(f"##### Data for Past Event {i+1}")
                # Create a DataFrame with metrics as rows
                df_template = pd.DataFrame({
                    "Metric": st.session_state.metrics,
                    "Baseline (7-day)": [None] * len(st.session_state.metrics),
                    "Actual (7-day)": [None] * len(st.session_state.metrics)
                }).set_index("Metric")
                
                # Use data_editor for this event's table
                edited_benchmark_df = st.data_editor(df_template, key=f"benchmark_editor_{i}", use_container_width=True)
                benchmark_events_data[f"Past Event {i+1}"] = edited_benchmark_df.reset_index()

            if st.form_submit_button("Calculate Proposed Benchmark & Proceed →", type="primary"):
                with st.spinner("Analyzing past events to generate benchmarks..."):
                    # Pass the dictionary of event DataFrames to the calculation function
                    benchmark_df = generate_proposed_benchmark(benchmark_events_data, st.session_state.metrics)
                    st.session_state.benchmark_df = benchmark_df
                    # Extract the 'Proposed Benchmark' column to pre-fill the main scorecards
                    st.session_state.proposed_benchmarks = benchmark_df.set_index('Metric')['Proposed Benchmark'].to_dict()
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
    # ... The rest of the app logic remains the same
