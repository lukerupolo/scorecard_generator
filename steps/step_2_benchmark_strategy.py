import streamlit as st
from strategy import define_comparable_profile

def render():
    st.header("Step 2: Define a Comparable Event Profile")
    st.info("To ensure your benchmarks are meaningful, first profile your current event. This will help you select truly comparable past events in the next step.")

    with st.form("strategy_form"):
        st.subheader("Please profile your current event:")
        objective = st.selectbox(
            "Primary Objective: What is the single most important goal?",
            options=["Brand Awareness / Reach", "Audience Engagement / Depth", "Conversion / Action"],
            help="Select the goal that best describes what you want to achieve."
        )
        scale = st.selectbox(
            "Campaign Scale & Investment: What is the relative size and budget?",
            options=["Major", "Standard", "Niche"],
            help="""
            - **Major**: A huge, top-tier event (e.g., a full game launch).
            - **Standard**: A significant, but not massive, marketing beat (e.g., a new season).
            - **Niche**: A smaller, focused effort (e.g., a creator campaign).
            """
        )
        audience = st.selectbox(
            "Target Audience: Who are you trying to reach?",
            options=["New Customer Acquisition", "Existing Customer Re-engagement"],
            help="Are you primarily trying to reach new people or re-engage your existing fans?"
        )

        submitted = st.form_submit_button("Define Profile & Proceed →", type="primary")
        if submitted:
            st.session_state.strategy_profile = define_comparable_profile(objective, scale, audience)
            st.session_state.comparability_analysis_complete = True
            st.rerun()
