import streamlit as st

def render_sidebar():
    """
    Renders the sidebar. Currently empty as all UI elements have been
    moved to the main application page for a sequential workflow.
    """
    # This function is kept for potential future use (e.g., adding a debug toggle)
    # but currently does not add any items to the sidebar.
    config = {}
    with st.sidebar:
        st.info("Configure your scorecard on the main page.")
    return config
