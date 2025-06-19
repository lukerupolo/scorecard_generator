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
# Step 2: Optional Benchmark Calculation (Updated UI)
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
            st.info("For each metric, provide its 3-month average from your external tool, then enter the Baseline and Actual values from past events.")
            
            historical_inputs = {}
            for metric in st.session_state.metrics:
                st.markdown(f"#### Data for: **{metric}**")
                
                # NEW: Input for the 3-month average from the external tool
                three_month_avg = st.number_input(
                    f"3-Month Average for '{metric}'", 
                    min_value=0.0, 
                    format="%.2f", 
                    key=f"3m_avg_{metric}"
                )
                
                # Table for historical event data
                df_template = pd.DataFrame([{"Event Name": "Past Event 1", "Baseline (7-day)": None, "Actual (7-day)": None}])
                edited_df = st.data_editor(df_template, key=f"hist_editor_{metric}", num_rows="dynamic", use_container_width=True)
                
                # Store both the historical data and the 3-month average
                historical_inputs[metric] = {
                    "historical_df": edited_df,
                    "three_month_avg": three_month_avg
                }

            if st.form_submit_button("Calculate All Proposed Benchmarks & Proceed →", type="primary"):
                with st.spinner("Analyzing historical data..."):
                    summary_df, proposed_benchmarks = calculate_all_benchmarks(historical_inputs)
                    st.session_state.benchmark_df = summary_df
                    st.session_state.proposed_benchmarks = proposed_benchmarks
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
    # ... (Rest of the app logic remains the same)
    pass
