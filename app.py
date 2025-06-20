# app.py
import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from ui import render_sidebar
from steps import (
    step_0_api_key,
    step_1_metric_selection,
    step_2_benchmark_strategy,
    step_3_review_strategy, # Import the new step
    step_4_build_moments, # Old step 3 is now 4
    step_5_create_presentation # Old step 4 is now 5
)
# Note: step_3_benchmark_calculation needs to be renamed to step_4...
# I will assume this is handled in the file system.
# For clarity, let's rename the import:
from steps import step_4_benchmark_calculation 

st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")
APP_VERSION = "6.0.0" 

# --- (Initialization is updated with a new state variable) ---
if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    # ... (full initialization code)
    st.session_state.strategy_profile_generated = False # NEW state variable

# --- Main App Flow is updated ---
st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar()

if not st.session_state.api_key_entered:
    step_0_api_key.render()
elif not st.session_state.metrics_confirmed:
    step_1_metric_selection.render()
elif not st.session_state.get('strategy_profile_generated'): # Check for new state
    step_2_benchmark_strategy.render()
elif not st.session_state.comparability_analysis_complete: # This is now the 'review' step
    step_3_review_strategy.render() # Render the new step file
elif not st.session_state.benchmark_flow_complete:
    step_4_benchmark_calculation.render()
else:
    # ... (rest of the app flow)
