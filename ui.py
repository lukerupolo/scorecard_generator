# ui.py
import streamlit as st

def render_sidebar():
    with st.sidebar:
        st.markdown("## 📋 Scorecard Progress")

        step = 0
        if st.session_state.get('api_key_entered'): step = 1
        if st.session_state.get('metrics_confirmed'): step = 2
        if st.session_state.get('strategy_profile_generated'): step = 3 # New Step
        if st.session_state.get('comparability_analysis_complete'): step = 4 # Review Step
        if st.session_state.get('benchmark_flow_complete'): step = 5
        if st.session_state.get('saved_moments'): step = 6
        
        steps_list = [
            "API Key",
            "Metric Selection",
            "Define Event Profile",     # Step 2
            "Review Strategy Profile",  # Step 3
            "Benchmark Calculation",    # Step 4
            "Build & Save Moments",     # Step 5
            "Create Presentation"       # Step 6
        ]

        progress_value = step / (len(steps_list) - 1)
        st.progress(progress_value)
        
        for i, s in enumerate(steps_list):
            if i < step:
                st.markdown(f"✅ ~~{s}~~")
            elif i == step:
                st.markdown(f"**➡️ {s}**")
            else:
                st.markdown(f"◻️ {s}")
        
        st.markdown("---")
        # --- (Reset button logic updated to include new state) ---
        if st.button("♻️ Start New Scorecard Moment", use_container_width=True):
            st.session_state.metrics_confirmed = False
            st.session_state.strategy_profile_generated = False # NEW
            st.session_state.comparability_analysis_complete = False
            # ... (rest of the reset logic)
            st.rerun()
