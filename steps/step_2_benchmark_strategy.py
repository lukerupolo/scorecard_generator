
# steps/step_2_benchmark_strategy.py
import streamlit as st
import pandas as pd
from strategy import generate_strategy

def render():
    st.header("Step 2: Benchmark Strategy")
    st.info("Profile your event to receive strategic guidance and metric prioritization.")

    with st.form("strategy_form"):
        st.subheader("Please profile your current event:")
        
        c1, c2 = st.columns(2)
        objective = c1.selectbox(
            "Primary Objective:",
            options=["Brand Awareness / Reach", "Audience Engagement / Depth", "Conversion / Action"]
        )
        scale = c2.selectbox(
            "Campaign Scale:",
            options=["Major", "Standard", "Niche"]
        )
        c3, c4 = st.columns(2)
        audience = c3.selectbox(
            "Target Audience:",
            options=["New Customer Acquisition", "Existing Customer Re-engagement"]
        )
        # --- NEW: Investment Level Input ---
        investment = c4.selectbox(
            "Campaign Investment Level:",
            options=["Low (<$50k)", "Medium ($50k - $250k)", "High ($250k - $1M)", "Major (>$1M)"]
        )

        submitted = st.form_submit_button("Generate Strategy Profile →", type="primary")
        if submitted:
            # Use the new, more powerful strategy function
            st.session_state.strategy_profile = generate_strategy(
                objective, 
                scale, 
                audience, 
                investment,
                st.session_state.metrics,
                st.session_state.ai_categories
            )
            st.session_state.comparability_analysis_complete = True
            st.rerun()

    # --- NEW: Display the full strategy profile after submission ---
    if st.session_state.get("strategy_profile"):
        profile = st.session_state.strategy_profile
        
        st.markdown("---")
        st.subheader("Your Strategic Recommendation")

        # Display Prioritized Metrics
        if profile.get("prioritized_metrics"):
            st.markdown("#### Metric Prioritization")
            st.write("Based on your primary objective, here are your prioritized metrics:")
            st.dataframe(pd.DataFrame(profile["prioritized_metrics"]), use_container_width=True)

        # Display Strategic Considerations
        if profile.get("strategic_considerations"):
            st.markdown("#### Strategic Considerations")
            for item in profile["strategic_considerations"]:
                if item['type'] == 'Warning':
                    st.warning(item['text'])
                else:
                    st.info(item['text'])

        # Display guidance for comparable events (as before)
        if profile.get("ideal_profile_description"):
             with st.expander("View Guidance on Selecting Comparable Past Events"):
                st.markdown(f"**_{profile['ideal_profile_description']}_**")
        
        if st.button("Proceed to Benchmark Calculation →"):
            # This button doesn't need to do anything but the rerun will
            # be handled by the main app logic switching to the next step.
            # We just need a button to feel like we're moving forward.
            # A cleaner way would be to just advance state, but this works for Streamlit.
            pass
