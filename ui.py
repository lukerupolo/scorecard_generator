import streamlit as st

def render_sidebar():
    """Renders the sidebar UI for global settings."""
    config = {}
    with st.sidebar:
        st.info("Configure your scorecard on the main page.")
        # Any future global settings can go here.
    return config
