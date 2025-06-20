# In steps/step_3_review_strategy.py
import streamlit as st
import pandas as pd

def render():
    st.header("Step 3: Review Strategy Profile")
    profile = st.session_state.get("strategy_profile")
    if not profile: st.warning("Strategy profile not generated. Please return to the previous step."); return
    st.subheader("Your Strategic Recommendation")
    if profile.get("prioritized_metrics"):
        st.markdown("#### Metric Prioritization")
        st.write("Based on your primary objective, here are your prioritized metrics:")
        st.dataframe(pd.DataFrame(profile["prioritized_metrics"]), use_container_width=True)
    if profile.get("strategic_considerations"):
        st.markdown("#### Strategic Considerations")
        for item in profile["strategic_considerations"]:
            if item['type'] == 'Warning': st.warning(item['text'])
            else: st.info(item['text'])
    if profile.get("ideal_profile_description"):
        with st.expander("View Guidance on Selecting Comparable Past Events"): st.markdown(f"**_{profile['ideal_profile_description']}_**")
    st.markdown("---")
    if st.button("Proceed to Benchmark Calculation →", type="primary"):
        st.session_state.comparability_analysis_complete = True
        st.rerun()
