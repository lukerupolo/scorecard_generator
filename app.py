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
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# Initialize session state keys
for key in ['api_key_entered', 'metrics_confirmed', 'benchmark_flow_complete', 'scorecard_ready', 'show_ppt_creator']:
    if key not in st.session_state: st.session_state[key] = False
for key in ['openai_api_key', 'metrics', 'benchmark_choice', 'benchmark_df', 'sheets_dict', 'presentation_buffer', 'events_config', 'proposed_benchmarks']:
     if key not in st.session_state: st.session_state[key] = None

st.title("Event Marketing Scorecard & Presentation Generator")
app_config = render_sidebar() # Renders sidebar and gets initial config

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
        # The selected metrics are stored in a temporary variable first
        selected_metrics = st.multiselect("Select metrics:", options=["Video views (Franchise)", "Social Impressions", "Press UMV (unique monthly views)"], default=["Video views (Franchise)"])
        
        # When this button is clicked, we save the selection to session_state
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
        "Would you like to calculate proposed benchmark values for this session using historical data?",
        ("No, I will enter benchmarks manually later.", "Yes, calculate benchmarks from past events."),
        key="benchmark_choice_radio"
    )

    if benchmark_choice == "Yes, calculate benchmarks from past events.":
        with st.form("benchmark_data_form"):
            st.info("For each past event, enter the Baseline and Actual values for all metrics.")
            n_benchmark_events = st.number_input("Number of past events to use for benchmark", min_value=1, max_value=10, value=1)
            
            historical_data_input = {}
            for i in range(n_benchmark_events):
                st.markdown(f"##### Data for Past Event {i+1}")
                # FIXED: This now correctly uses st.session_state.metrics, which is guaranteed to exist at this step
                df_template = pd.DataFrame({
                    "Metric": st.session_state.metrics,
                    "Baseline (7-day)": [None] * len(st.session_state.metrics),
                    "Actual (7-day)": [None] * len(st.session_state.metrics)
                }).set_index("Metric")
                
                edited_df = st.data_editor(df_template, key=f"hist_editor_{i}", use_container_width=True)
                historical_data_input[f"Past Event {i+1}"] = edited_df.reset_index()

            if st.form_submit_button("Calculate Proposed Benchmark & Proceed →", type="primary"):
                with st.spinner("Analyzing historical data..."):
                    summary_df, proposed_benchmarks = generate_benchmark_summary(historical_data_input)
                    st.session_state.benchmark_df = summary_df
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
    # This section now runs only after all previous steps are complete
    app_config['openai_api_key'] = st.session_state.openai_api_key
    app_config['metrics'] = st.session_state.metrics
    app_config['proposed_benchmarks'] = st.session_state.get('proposed_benchmarks')
    
    st.header("Step 3: Configure Events & Generate Scorecard")
    # ... (Rest of the app logic remains unchanged)
    # ...
