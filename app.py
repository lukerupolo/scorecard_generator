# app.py
import streamlit as st
import pandas as pd
import sys
import os

# This is the crucial part: Add the project's root directory to the Python path
# This allows the app to find the 'steps' and 'strategy' modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Local Imports
from ui import render_sidebar
from steps import (
    step_0_api_key,
    step_1_metric_selection,
    step_2_benchmark_strategy,
    step_3_benchmark_calculation,
    step_4_build_moments,
    step_5_create_presentation
)

# --- App State Initialization ---
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")
APP_VERSION = "5.0.1" # Incremented version

def initialize_state():
    """Initializes all session state variables."""
    api_key = st.session_state.get('openai_api_key')
    
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    st.session_state.app_version = APP_VERSION
    st.session_state.api_key_entered = True if api_key else False
    st.session_state.openai_api_key = api_key
    st.session_state.metrics_confirmed = False
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

if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    initialize_state()

# --- Main App Flow ---
st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar()

# Use the session state to determine which step to display
if not st.session_state.api_key_entered:
    step_0_api_key.render()

elif not st.session_state.metrics_confirmed:
    step_1_metric_selection.render()

elif not st.session_state.comparability_analysis_complete:
    step_2_benchmark_strategy.render()

elif not st.session_state.benchmark_flow_complete:
    step_3_benchmark_calculation.render()

else:
    # Steps 4 and 5 are combined in the final screen
    step_4_build_moments.render()
    step_5_create_presentation.render()
