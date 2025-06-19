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
for key in ['api_key_entered', 'metrics_confirmed', 'scorecard_ready', 'benchmark_df', 'show_ppt_creator', 'generate_benchmark_choice']:
    if key not in st.session_state: st.session_state[key] = False
for key in ['openai_api_key', 'metrics', 'sheets_dict', 'presentation_buffer', 'metric_explanations', 'events_config']:
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
# Step 2 & 3: Main App Logic
# ================================================================================
else:
    app_config = {'openai_api_key': st.session_state.openai_api_key, 'metrics': st.session_state.metrics}

    st.header("Step 2: Configure Events & Generate Scorecard Structure")
    with st.expander("Configure Events for this Scorecard", expanded=True):
        n_events = st.number_input("Number of events for this scorecard", min_value=1, max_value=10, value=1, step=1)
        events = []
        event_cols = st.columns(n_events)
        for i in range(n_events):
            with event_cols[i]:
                st.markdown(f"##### Event {i+1}")
                name = st.text_input(f"Label", key=f"name_{i}", value=f"Event {i+1}")
                events.append({"name": name, "date": datetime.now()})
    app_config['events'] = events
    
    if st.button("✅ Generate Scorecard Structure", use_container_width=True, type="primary"):
        with st.spinner("Categorizing metrics with AI and building scorecards..."):
            sheets_dict = process_scorecard_data(app_config)
            st.session_state["sheets_dict"] = sheets_dict
            st.session_state["scorecard_ready"] = True
        st.rerun()

    if st.session_state.scorecard_ready and st.session_state.sheets_dict:
        st.markdown("---"); st.header("Step 3: Edit Data & Generate Benchmark")
        
        # Display the main scorecard tables for manual editing
        for name, df in st.session_state.sheets_dict.items():
            if "Benchmark" not in name:
                 st.markdown(f"#### Edit Scorecard: {name}")
                 edited_df = st.data_editor(df, key=f"editor_{name}", use_container_width=True, num_rows="dynamic", column_config={"Category": st.column_config.TextColumn(width="medium"), "Actuals": st.column_config.NumberColumn("Actuals"), "Benchmark": st.column_config.NumberColumn("Benchmark")})
                 st.session_state.sheets_dict[name] = edited_df

        # --- NEW: Optional Benchmark Generation Workflow ---
        st.markdown("---")
        st.subheader("Generate Proposed Benchmark (Optional)")
        
        # Ask the user if they want to perform this step
        benchmark_choice = st.radio(
            "Would you like to calculate benchmark values in this session?",
            ("No, I will enter benchmarks manually or leave them blank", "Yes, let's calculate it"),
            key="benchmark_choice_radio"
        )

        if benchmark_choice == "Yes, let's calculate it":
            with st.form("benchmark_data_form"):
                st.info("To generate a proposed benchmark, enter the 'Actuals' and 'Benchmark' values for past events below.")
                n_benchmark_events = st.number_input("Number of past events to use for benchmark", min_value=1, max_value=5, value=1)
                
                benchmark_events_data = {}
                for i in range(n_benchmark_events):
                    st.markdown(f"##### Past Event {i+1}")
                    df_template = pd.DataFrame({"Metric": app_config['metrics'], "Actuals": None, "Benchmark": None}).set_index("Metric")
                    edited_benchmark_df = st.data_editor(df_template, key=f"benchmark_editor_{i}", use_container_width=True)
                    benchmark_events_data[f"Past Event {i+1}"] = edited_benchmark_df.reset_index()

                if st.form_submit_button("Calculate Proposed Benchmark", use_container_width=True):
                    with st.spinner("Analyzing past events to generate benchmarks..."):
                        benchmark_df = generate_proposed_benchmark(benchmark_events_data, app_config['metrics'])
                        st.session_state.benchmark_df = benchmark_df
                    st.rerun()
        
        if st.session_state.benchmark_df is not None and not st.session_state.benchmark_df.empty:
            st.markdown("#### ✨ Proposed Benchmark Table")
            st.dataframe(st.session_state.benchmark_df, use_container_width=True)

        st.markdown("---")
        st.session_state['show_ppt_creator'] = True

    if st.session_state.get('show_ppt_creator'):
        st.header("Step 4: Create Presentation")
        # ... (PPT creation logic remains the same)
        if st.session_state.get("presentation_buffer"):
            st.download_button(label="✅ Download Your Presentation!", data=st.session_state.presentation_buffer, file_name="game_scorecard_presentation.pptx", use_container_width=True)
        with st.form("ppt_form_final"):
            # ... (form details)
            if st.form_submit_button("Generate Presentation", use_container_width=True):
                # ... (presentation generation logic)
                pass
