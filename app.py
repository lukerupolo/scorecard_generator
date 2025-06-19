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
        selected_metrics = st.multiselect("Select metrics:", options=["Video views (Franchise)", "Social Impressions", "Press UMV (unique monthly views)"], default=["Video views (Franchise)"])
        if st.form_submit_button("Confirm Metrics & Proceed →", type="primary"):
            st.session_state.metrics = selected_metrics
            st.session_state.metrics_confirmed = True
            st.rerun()

# ================================================================================
# Step 2: Optional Benchmark Calculation from File
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Benchmark Calculation (Optional)")
    
    benchmark_choice = st.radio(
        "Would you like to calculate proposed benchmark values by uploading historical data?",
        ("No, I will enter benchmarks manually later.", "Yes, calculate benchmarks from a file."),
        key="benchmark_choice_radio"
    )

    if benchmark_choice == "Yes, calculate benchmarks from a file.":
        with st.form("benchmark_file_form"):
            st.info("Upload a CSV file with past event data. It should contain columns for 'Metric', 'Baseline', and 'Actual'.")
            uploaded_benchmark_file = st.file_uploader("Upload your benchmark data source file", type=["csv"])
            
            if st.form_submit_button("Calculate Proposed Benchmark & Proceed →", type="primary"):
                if uploaded_benchmark_file is not None:
                    with st.spinner("Analyzing historical data..."):
                        try:
                            benchmark_source_df = pd.read_csv(uploaded_benchmark_file)
                            # Generate the summary table
                            benchmark_summary_df = generate_proposed_benchmark(benchmark_source_df, st.session_state.metrics)
                            st.session_state.benchmark_df = benchmark_summary_df
                            # Extract the 'Proposed Benchmark' values to use later
                            st.session_state.proposed_benchmarks = benchmark_summary_df.set_index('Metric')['Proposed Benchmark'].to_dict()
                            st.session_state.benchmark_flow_complete = True
                        except Exception as e:
                            st.error(f"Failed to process file: {e}")
                    st.rerun()
                else:
                    st.error("Please upload a file to calculate benchmarks.")
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
    
    if st.button("✅ Generate Scorecard Structure", use_container_width=True, type="primary"):
        with st.spinner("Building scorecards..."):
            sheets_dict = process_scorecard_data(app_config)
            st.session_state["sheets_dict"] = sheets_dict
            st.session_state["scorecard_ready"] = True
        st.rerun()

    if st.session_state.scorecard_ready and st.session_state.sheets_dict:
        st.markdown("---"); st.header("Step 4: Review & Edit Data")
        
        # Display the calculated benchmark summary table if it exists
        if st.session_state.benchmark_df is not None and not st.session_state.benchmark_df.empty:
            st.markdown("#### ✨ Proposed Benchmark Summary")
            st.dataframe(st.session_state.benchmark_df, use_container_width=True)
            st.markdown("---")

        for name, df in st.session_state.sheets_dict.items():
            st.markdown(f"#### Edit Scorecard: {name}")
            edited_df = st.data_editor(df, key=f"editor_{name}", use_container_width=True, num_rows="dynamic")
            
            # Recalculate difference column on edit
            edited_df['Actuals'] = pd.to_numeric(edited_df['Actuals'], errors='coerce')
            edited_df['Benchmark'] = pd.to_numeric(edited_df['Benchmark'], errors='coerce')
            edited_df['% Difference'] = ((edited_df['Actuals'] - edited_df['Benchmark']) / edited_df['Benchmark']).apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
            
            st.session_state.sheets_dict[name] = edited_df
        
        st.markdown("---")
        st.session_state['show_ppt_creator'] = True

    if st.session_state.get('show_ppt_creator'):
        st.header("Step 5: Create Presentation")
        # ... (PPT creation logic remains the same)
