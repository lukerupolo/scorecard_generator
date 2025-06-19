import streamlit as st

def render_sidebar():
    """
    Renders the sidebar, showing the user's progress through the steps
    and providing a button to restart the process.
    """
    with st.sidebar:
        st.markdown("## 📋 Scorecard Progress")

        # Determine the current step based on session state flags
        step = 0
        if st.session_state.get('api_key_entered'):
            step = 1
        if st.session_state.get('metrics_confirmed'):
            step = 2
        if st.session_state.get('benchmark_flow_complete'):
            step = 3
        if st.session_state.get('show_ppt_creator'): # This is set when scorecards are ready
            step = 4
        
        steps_list = [
            "API Key",
            "Metric Selection",
            "Benchmark Calculation",
            "Build & Save Moments",
            "Create Presentation"
        ]

        # Display progress bar and step names
        st.progress(step / (len(steps_list) -1))
        
        for i, s in enumerate(steps_list):
            if i < step:
                st.markdown(f"✅ ~~{s}~~")
            elif i == step:
                # Highlight the current step
                st.markdown(f"**➡️ {s}**")
            else:
                st.markdown(f"◻️ {s}")
        
        st.markdown("---")
        
        # The "Start New" button will clear the session state and rerun the app
        if st.button("♻️ Start New Scorecard", use_container_width=True):
            # Keep the API key but clear everything else
            api_key = st.session_state.get('openai_api_key')
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            # Restore the API key so the user doesn't have to enter it again
            st.session_state.openai_api_key = api_key
            st.session_state.api_key_entered = True if api_key else False
            st.rerun()

    # This dictionary is kept for potential future use but is not currently needed
    return {}
