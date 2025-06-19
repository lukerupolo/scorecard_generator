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
for key in ['openai_api_key', 'metrics', 'benchmark_choice', 'benchmark_df', 'sheets_dict', 'presentation_buffer', 'proposed_benchmarks']:
     if key not in st.session_state: st.session_state[key] = None

st.title("Event Marketing Scorecard & Presentation Generator")
app_config = render_sidebar()

# ================================================================================
# Step 0 & 1: API Key and Metric Selection
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
# Step 2: Optional Benchmark Calculation (Corrected Workflow)
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Benchmark Calculation (Optional)")
    
    benchmark_choice = st.radio(
        "Would you like to calculate proposed benchmark values using historical data?",
        ("No, I will proceed without calculating benchmarks.", "Yes, calculate benchmarks from past events."),
        key="benchmark_choice_radio"
    )

    if benchmark_choice == "Yes, calculate benchmarks from past events.":
        with st.form("benchmark_data_form"):
            st.info("For each metric below, enter the Baseline and Actual values from past events.")
            
            historical_data_input = {}
            for metric in st.session_state.metrics:
                st.markdown(f"#### Data for: **{metric}**")
                df_template = pd.DataFrame([
                    {"Event Name": "Past Event 1", "Baseline (7-day)": None, "Actual (7-day)": None},
                    {"Event Name": "Past Event 2", "Baseline (7-day)": None, "Actual (7-day)": None}
                ])
                edited_df = st.data_editor(df_template, key=f"hist_editor_{metric}", num_rows="dynamic", use_container_width=True)
                historical_data_input[metric] = edited_df

            if st.form_submit_button("Calculate All Proposed Benchmarks & Proceed →", type="primary"):
                with st.spinner("Analyzing historical data..."):
                    summary_df, proposed_benchmarks = calculate_all_benchmarks(historical_data_input)
                    st.session_state.benchmark_df = summary_df
                    st.session_state.proposed_benchmarks = proposed_benchmarks
                    st.session_state.benchmark_flow_complete = True
                st.rerun()
    else:
        if st.button("Proceed to Scorecard Creation →", type="primary"):
            st.session_state.benchmark_flow_complete = True
            st.rerun()

# ================================================================================
# Step 3, 4 - Main App Logic
# ================================================================================
else:
    app_config['openai_api_key'] = st.session_state.openai_api_key
    app_config['metrics'] = st.session_state.metrics
    app_config['proposed_benchmarks'] = st.session_state.get('proposed_benchmarks')
    
    if not st.session_state.scorecard_ready:
        with st.spinner("Building final scorecard..."):
            app_config['events'] = [{"name": "Final Scorecard"}]
            sheets_dict = process_scorecard_data(app_config)
            st.session_state.sheets_dict = sheets_dict
            st.session_state.scorecard_ready = True
            st.rerun()
            
    if st.session_state.scorecard_ready and st.session_state.sheets_dict:
        st.header("Step 3: Review & Edit Final Scorecard")

        if st.session_state.benchmark_df is not None and not st.session_state.benchmark_df.empty:
            st.markdown("#### ✨ Proposed Benchmark Summary")
            st.dataframe(st.session_state.benchmark_df.set_index("Metric"), use_container_width=True)
            st.markdown("---")
        
        for name, df in st.session_state.sheets_dict.items():
            st.markdown(f"#### {name}")
            edited_df = st.data_editor(df, key=f"editor_{name}", use_container_width=True, num_rows="dynamic")
            
            edited_df['Actuals'] = pd.to_numeric(edited_df['Actuals'], errors='coerce')
            edited_df['Benchmark'] = pd.to_numeric(edited_df['Benchmark'], errors='coerce')
            edited_df['% Difference'] = ((edited_df['Actuals'] - edited_df['Benchmark']) / edited_df['Benchmark']).apply(lambda x: f"{x:.1%}" if pd.notna(x) else None)
            st.session_state.sheets_dict[name] = edited_df
        
        st.markdown("---")
        if st.session_state.sheets_dict:
            excel_buffer = create_excel_workbook(st.session_state.sheets_dict)
            st.download_button(label="📥 Download as Excel Workbook", data=excel_buffer, file_name="full_scorecard.xlsx", use_container_width=True)
        st.markdown("---")
        st.session_state['show_ppt_creator'] = True

    if st.session_state.get('show_ppt_creator'):
        st.header("Step 4: Create Presentation")
        # ... (PPT creation logic remains the same)
