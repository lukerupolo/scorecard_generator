import streamlit as st
from io import BytesIO
from datetime import datetime
import pandas as pd

# --- Local Imports from our other files ---
from style import STYLE_PRESETS 
from ui import render_sidebar
from data_processing import process_scorecard_data, calculate_all_benchmarks, get_ai_metric_explanations
from powerpoint import create_presentation
from excel import create_excel_workbook

# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# Initialize session state keys
for key in ['api_key_entered', 'metrics_confirmed', 'benchmark_flow_complete', 'scorecard_ready', 'show_ppt_creator']:
    if key not in st.session_state: st.session_state[key] = False
for key in ['openai_api_key', 'metrics', 'benchmark_choice', 'benchmark_df', 'sheets_dict', 'presentation_buffer', 'events_config', 'proposed_benchmarks', 'metric_explanations']:
     if key not in st.session_state: st.session_state[key] = None

st.title("Event Marketing Scorecard & Presentation Generator")
app_config = render_sidebar()

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
# Step 1: Metric Selection (Restored Full Functionality)
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
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        # Button to get AI explanations
        if col1.form_submit_button("🤖 Get AI Explanation for Selected Metrics"):
             if selected_metrics:
                with st.spinner("Asking AI for explanations..."):
                    explanations = get_ai_metric_explanations(selected_metrics, st.session_state.openai_api_key)
                    st.session_state.metric_explanations = explanations
             else:
                st.warning("Please select at least one metric to get an explanation.")

        # Button to confirm and move to the next step
        if col2.form_submit_button("Confirm Metrics & Proceed →", type="primary"):
            if not selected_metrics:
                st.error("Please select at least one metric.")
            else:
                st.session_state.metrics = selected_metrics
                st.session_state.metrics_confirmed = True
                st.rerun()
            
    # Display AI explanations if they exist
    if st.session_state.metric_explanations:
        st.info("### AI Metric Explanations")
        for metric, explanation in st.session_state.metric_explanations.items():
            st.markdown(f"**{metric}:** {explanation}")

# ================================================================================
# The rest of the app flow remains unchanged
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Benchmark Calculation (Optional)")
    # ... (Benchmark calculation logic)

else:
    st.header("Step 3: Review & Edit Final Scorecard")
    # ... (Scorecard display and editing logic)
    
    if st.session_state.get('show_ppt_creator'):
        st.header("Step 4: Create Presentation")
        # ... (PPT creation logic)
