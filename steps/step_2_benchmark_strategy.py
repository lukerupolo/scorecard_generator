# In steps/step_2_benchmark_strategy.py
import streamlit as st
from strategy import generate_strategy

def render():
    st.header("Step 2: Define Event Profile")
    st.info("Profile your event to receive strategic guidance in the next step.")
    with st.form("strategy_form"):
        st.subheader("Please profile your current event:")
        c1, c2 = st.columns(2)
        objective = c1.selectbox("Primary Objective:", options=["Brand Awareness / Reach", "Audience Engagement / Depth", "Conversion / Action"])
        scale = c2.selectbox("Campaign Scale:", options=["Major", "Standard", "Niche"])
        c3, c4 = st.columns(2)
        audience = c3.selectbox("Target Audience:", options=["New Customer Acquisition", "Existing Customer Re-engagement"])
        investment = c4.selectbox("Campaign Investment Level:", options=["Low (<$50k)", "Medium ($50k - $250k)", "High ($250k - $1M)", "Major (>$1M)"])
        submitted = st.form_submit_button("Generate Strategy Profile →", type="primary")
        if submitted:
            st.session_state.strategy_profile = generate_strategy(objective, scale, audience, investment, st.session_state.metrics, st.session_state.ai_categories)
            st.session_state.strategy_profile_generated = True
            st.rerun()
