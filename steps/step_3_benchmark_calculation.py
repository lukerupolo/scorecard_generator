import streamlit as st
import pandas as pd
from data_processing import calculate_all_benchmarks

def render():
    st.header("Step 3: Benchmark Calculation (Optional)")

    if st.session_state.strategy_profile:
        with st.container(border=True):
            st.subheader("Your Recommended Profile for Comparable Events")
            st.markdown(f"**_{st.session_state.strategy_profile['ideal_profile_description']}_**")
            st.markdown("---")
            st.markdown("**How to Choose Your Past Events (Comparison Hierarchy):**")
            for note in st.session_state.strategy_profile['guidance_notes']:
                st.markdown(f"**{note['title']}**: {note['text']}")
    st.markdown("---")

    benchmark_choice = st.radio(
        "Would you like to calculate proposed benchmark values using historical data?",
        ("No, I will enter benchmarks manually later.", "Yes, calculate benchmarks from past events."),
        key="benchmark_choice_radio"
    )

    if benchmark_choice == "Yes, calculate benchmarks from past events.":
        with st.form("benchmark_data_form"):
            st.info("For each metric, provide its 3-month average, then enter the Baseline and Actual values from past events that MATCH the profile defined above.")

            historical_inputs = {}
            for metric in st.session_state.metrics:
                st.markdown(f"--- \n #### Data for: **{metric}**")

                three_month_avg = st.number_input(f"3-Month Average for '{metric}'", min_value=0.0, format="%.2f", key=f"3m_avg_{metric}")
                df_template = pd.DataFrame([{"Event Name": "Past Event 1", "Baseline (7-day)": None, "Actual (7-day)": None}])
                edited_df = st.data_editor(df_template, key=f"hist_editor_{metric}", num_rows="dynamic", use_container_width=True)

                historical_inputs[metric] = {"historical_df": edited_df, "three_month_avg": three_month_avg}

            if st.form_submit_button("Calculate All Proposed Benchmarks & Proceed →", type="primary"):
                with st.spinner("Analyzing historical data..."):
                    summary_df, proposed, actuals = calculate_all_benchmarks(historical_inputs)
                    st.session_state.benchmark_df = summary_df
                    st.session_state.proposed_benchmarks = proposed
                    st.session_state.avg_actuals = actuals
                    st.session_state.benchmark_flow_complete = True
                st.rerun()
    else:
        if st.button("Proceed to Scorecard Creation →", type="primary"):
            st.session_state.benchmark_flow_complete = True
            st.rerun()
