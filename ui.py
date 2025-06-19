import streamlit as st

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
        if st.session_state.get('saved_moments'): step = 4 # Progress when at least one moment is saved
        
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
        
        # --- FIXED: This button now correctly resets the workflow without deleting saved moments ---
        if st.button("♻️ Start New Scorecard Moment", use_container_width=True):
            # Define which keys to reset to start a new scorecard flow
            keys_to_reset = [
                'metrics_confirmed', 'benchmark_flow_complete', 'scorecard_ready', 
                'show_ppt_creator', 'metrics', 'benchmark_choice', 'benchmark_df',
                'sheets_dict', 'presentation_buffer', 'events_config', 
                'proposed_benchmarks', 'metric_explanations'
            ]
            
            # Reset the workflow keys
            for key in keys_to_reset:
                if key in st.session_state:
                    del st.session_state[key]
            
            # The 'saved_moments', 'openai_api_key', and 'api_key_entered' keys
            # are intentionally left untouched.
            
            st.rerun()

    # This dictionary is kept for potential future use but is not currently needed
    return {}
