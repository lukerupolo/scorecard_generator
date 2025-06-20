# ui.py (Original Version)
import streamlit as st
import pandas as pd

def render_sidebar():
    """
    Renders the sidebar, showing the user's progress through the steps
    and providing a button to restart the process without losing saved work.
    """
    with st.sidebar:
        st.markdown("## 📋 Scorecard Progress")

        # Determine the current step based on session state flags
        step = 0
        if st.session_state.get('api_key_entered'): step = 1
        if st.session_state.get('metrics_confirmed'): step = 2
        if st.session_state.get('benchmark_flow_complete'): step = 3
        if st.session_state.get('saved_moments'): step = 4
        
        steps_list = [
            "API Key",
            "Metric Selection",
            "Benchmark Calculation",
            "Build & Save Moments",
            "Create Presentation"
        ]

        # Display progress bar and step names
        progress_value = step / (len(steps_list) - 1) if step < len(steps_list) else 1.0
        st.progress(progress_value)
        
        for i, s in enumerate(steps_list):
            if i < step:
                st.markdown(f"✅ ~~{s}~~")
            elif i == step:
                st.markdown(f"**➡️ {s}**")
            else:
                st.markdown(f"◻️ {s}")
        
        st.markdown("---")
        
        # --- FIXED: This button now correctly RESETS the workflow without deleting state ---
        if st.button("♻️ Start New Scorecard Moment", use_container_width=True):
            
            # Reset workflow state variables to their default values
            st.session_state.metrics_confirmed = False
            st.session_state.benchmark_flow_complete = False
            st.session_state.scorecard_ready = False
            st.session_state.show_ppt_creator = False
            st.session_state.metrics = None
            st.session_state.benchmark_df = None
            st.session_state.sheets_dict = None
            st.session_state.presentation_buffer = None
            st.session_state.proposed_benchmarks = None
            
            # The 'saved_moments', 'openai_api_key', and 'api_key_entered' keys
            # are intentionally left untouched to preserve them across runs.
            
            st.rerun()

    return {}
