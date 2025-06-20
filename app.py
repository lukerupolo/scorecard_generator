# app.py
import streamlit as st
import pandas as pd

# The 'sys' and 'os' path fixes are removed as they are no longer needed
# with the correct package structure (__init__.py files).

from ui import render_sidebar
from steps import (
    step_0_api_key,
    step_1_metric_selection,
    step_2_benchmark_strategy,
    step_3_review_strategy,
    step_4_benchmark_calculation,
    step_5_create_presentation,
    step_6_build_moments 
)

st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")
APP_VERSION = "6.0.3" # Incremented version

def initialize_state():
    """Initializes all session state variables."""
    api_key = st.session_state.get('openai_api_key')
    
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    st.session_state.app_version = APP_VERSION
    st.session_state.api_key_entered = True if api_key else False
    st.session_state.openai_api_key = api_key
    st.session_state.metrics_confirmed = False
    st.session_state.strategy_profile_generated = False 
    st.session_state.comparability_analysis_complete = False
    st.session_state.benchmark_flow_complete = False
    st.session_state.scorecard_ready = False
    st.session_state.show_ppt_creator = False
    st.session_state.metrics = []
    st.session_state.benchmark_choice = "No, I will enter benchmarks manually later."
    st.session_state.benchmark_df = pd.DataFrame()
    st.session_state.sheets_dict = None
    st.session_state.presentation_buffer = None
    st.session_state.proposed_benchmarks = {}
    st.session_state.strategy_profile = {}
    st.session_state.saved_moments = {}

# --- Initialization Check ---
if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    initialize_state()

# --- Main App Flow ---
st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar()

if not st.session_state.api_key_entered:
    step_0_api_key.render()
elif not st.session_state.metrics_confirmed:
    step_1_metric_selection.render()
elif not st.session_state.get('strategy_profile_generated'):
    step_2_benchmark_strategy.render()
elif not st.session_state.comparability_analysis_complete:
    step_3_review_strategy.render()
elif not st.session_state.benchmark_flow_complete:
    step_4_benchmark_calculation.render()
else:
    # This block now contains the actual function calls, fixing the error.
    step_6_build_moments.render()
    step_5_create_presentation.render()
