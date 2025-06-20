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

# This versioning system helps reset the state when you update the code.
APP_VERSION = "3.0.0" 

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

st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar() # Renders the sidebar with progress and reset button

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
        st.info("Select the metrics you want to measure for this scorecard.")
        predefined_metrics = [
            "Video views (Franchise)", "Social Impressions", "Press UMV (unique monthly views)",
            "Social Conversation Volume", "Views trailer", "UGC Views", 
            "Social Impressions-Posts with trailer (FB, IG, X)", "Social Impressions-All posts",
            "Nb. press articles", "Social Sentiment (Franchise)", "Trailer avg % viewed (Youtube)",
            "Email Open Rate (OR)", "Email Click Through Rate (CTR)", "Labs program sign-ups",
            "Discord channel sign-ups", "% Trailer views from Discord (Youtube)",
            "Labs sign up click-through Web", "Sessions", "DAU", "Hours Watched (Streams)"
        ]
        selected_metrics = st.multiselect("Select metrics:", options=predefined_metrics, default=["Video views (Franchise)", "Social Impressions"])
        
        if custom_metric := st.text_input("✍️ Add Custom Metric (and press Enter)"):
            if custom_metric not in selected_metrics:
                selected_metrics.append(custom_metric)
        
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
            st.info("For each metric, provide its 3-month average from your external tool, then enter the Baseline and Actual values from past events to calculate the expected uplift.")
            
            historical_inputs = {}
            for metric in st.session_state.metrics:
                st.markdown(f"--- \n #### Data for: **{metric}**")
                
                three_month_avg = st.number_input(f"3-Month Average (Baseline Method) for '{metric}'", min_value=0.0, format="%.2f", key=f"3m_avg_{metric}")
                df_template = pd.DataFrame([{"Event Name": "Past Event 1", "Baseline (7-day)": None, "Actual (7-day)": None}])
                edited_df = st.data_editor(df_template, key=f"hist_editor_{metric}", num_rows="dynamic", use_container_width=True)
                
                historical_inputs[metric] = {"historical_df": edited_df, "three_month_avg": three_month_avg}

            if st.form_submit_button("Calculate All Proposed Benchmarks & Proceed →", type="primary"):
                with st.spinner("Analyzing historical data..."):
                    summary_df, proposed_benchmarks, avg_actuals = calculate_all_benchmarks(historical_inputs)
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
    
    # --- Step 3: Configure Events & Generate Scorecard ---
    st.header("Step 3: Configure Events & Generate Scorecard")
    with st.expander("Configure Events for this Scorecard", expanded=True):
        n_events = st.number_input("Number of events for this scorecard", min_value=1, max_value=10, value=1)
        events = []
        event_cols = st.columns(n_events)
        for i in range(n_events):
            with event_cols[i]:
                st.markdown(f"##### Event {i+1}")
                name = st.text_input(f"Label", key=f"name_{i}", value=f"Event {i+1}")
                events.append({"name": name})
    app_config['events'] = events

    if st.button("✅ Generate Scorecard Structure", use_container_width=True, type="primary"):
        with st.spinner("Building scorecards..."):
            sheets_dict = process_scorecard_data(app_config)
            st.session_state.sheets_dict = sheets_dict
            st.session_state.scorecard_ready = True
        st.rerun()

    # --- Step 4: Review, Edit, and Download ---
    if st.session_state.scorecard_ready and st.session_state.sheets_dict:
        st.markdown("---")
        st.header("Step 4: Review & Edit Data")

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

    # --- Step 5: Create Presentation ---
    if st.session_state.get('show_ppt_creator'):
        st.header("Step 5: Create Presentation")
        if st.session_state.get("presentation_buffer"):
            st.download_button(label="✅ Download Your Presentation!", data=st.session_state.presentation_buffer, file_name="game_scorecard_presentation.pptx", use_container_width=True)

        with st.form("ppt_form"):
            st.subheader("Presentation Style & Details")
            col1, col2 = st.columns(2)
            selected_style_name = col1.radio("Select Style Preset:", options=list(STYLE_PRESETS.keys()), horizontal=True)
            image_region_prompt = col2.text_input("Region for AI Background Image", "Brazil")
            ppt_title = st.text_input("Presentation Title", "Game Scorecard")
            ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
            moments_input = st.text_area("Scorecard Moments (one per line)", "Pre-Reveal\nLaunch", height=100)
            submitted = st.form_submit_button("Generate Presentation", use_container_width=True)

            if submitted:
                if not st.session_state.get("sheets_dict"):
                    st.error("Please generate scorecard data first.")
                else:
                    with st.spinner(f"Building presentation with {selected_style_name} style..."):
                        style_guide = STYLE_PRESETS[selected_style_name]
                        scorecard_moments = [moment.strip() for moment in moments_input.split('\n') if moment.strip()]
                        # Note: This version passes the entire sheets_dict to the presentation.
                        ppt_buffer = create_presentation(
                            title=ppt_title,
                            subtitle=ppt_subtitle,
                            scorecard_moments=scorecard_moments,
                            sheets_dict=st.session_state.sheets_dict,
                            style_guide=style_guide,
                            region_prompt=image_region_prompt,
                            openai_api_key=st.session_state.openai_api_key 
                        )
                        st.session_state["presentation_buffer"] = ppt_buffer
                        st.rerun()
