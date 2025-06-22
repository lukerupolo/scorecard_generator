import streamlit as st
from io import BytesIO
from datetime import datetime
import pandas as pd

# --- Local Imports from our other files ---
# Assuming these files exist and are correct from your project setup
from style import STYLE_PRESETS
from ui import render_sidebar
from data_processing import process_scorecard_data, calculate_all_benchmarks, get_ai_metric_categories
from powerpoint import create_presentation
from excel import create_excel_workbook

# ================================================================================
# WORLD-CLASS PREDICTION ENGINE
# ================================================================================
def calculate_predictions_advanced(creators):
    """
    Calculates predicted reach and depth using a multi-factor model that accounts
    for paid media, content freshness, and creator saturation.

    Args:
        creators (list): A list of creator dictionaries with post details.

    Returns:
        tuple: Updated creators list, total reach, total weighted engagement.
    """
    total_predicted_reach = 0
    total_weighted_engagement = 0

    # --- Model Coefficients (World-Class Nuance) ---
    reach_weights = {
        'Instagram': {'Reel': 1.25, 'Story': 0.35, 'Static Post': 0.85, 'Long-form Video': 0.7},
        'TikTok': {'Reel': 1.6, 'Story': 0.4, 'Static Post': 0.7, 'Long-form Video': 0.9},
        'YouTube': {'Long-form Video': 0.8, 'Reel': 1.4}
    }
    engagement_weights = {
        'Instagram': {'likes': 1, 'comments': 4, 'shares': 6, 'saves': 5},
        'TikTok': {'likes': 1, 'comments': 3, 'shares': 5, 'saves': 4},
        'YouTube': {'likes': 1, 'comments': 5, 'shares': 3}
    }
    # Penalty/Bonus coefficients
    PAID_BOOST_FACTOR = 0.02 # 2% reach boost per $1000 spent
    FRESHNESS_BONUS = 0.15 # 15% bonus for new content
    SATURATION_PENALTY = {'Medium': 0.10, 'High': 0.25} # 10-25% penalty
    CTA_ENGAGEMENT_PENALTY = {'Soft CTA': 0, 'Hard CTA': 0.15} # Hard CTAs reduce organic ER by 15%

    for creator in creators:
        creator_saturation = creator.get('saturation', 'Low')

        if 'posts' in creator and creator['posts']:
            for post in creator['posts']:
                platform = creator.get('platform', 'Instagram')
                post_format = post.get('format', 'Reel')
                
                # --- 1. Calculate Predicted Reach ---
                baseline_reach = post.get('historical_reach_for_format', 0)
                
                paid_boost = (post.get('paid_amplification', 0) / 1000) * PAID_BOOST_FACTOR
                freshness_boost = FRESHNESS_BONUS if post.get('is_new_content', True) else 0
                saturation_penalty = SATURATION_PENALTY.get(creator_saturation, 0)

                adjustment_factor = 1 + paid_boost + freshness_boost - saturation_penalty
                predicted_reach = baseline_reach * adjustment_factor
                post['predicted_reach'] = predicted_reach
                total_predicted_reach += predicted_reach

                # --- 2. Calculate Weighted Engagement Score (Depth) ---
                base_er = post.get('historical_er_for_format', 0) / 100.0
                cta_penalty = CTA_ENGAGEMENT_PENALTY.get(post.get('cta_type', 'Soft CTA'), 0)
                adjusted_er = base_er * (1 - cta_penalty)

                estimated_interactions = predicted_reach * adjusted_er
                
                likes = estimated_interactions * 0.75
                comments = estimated_interactions * 0.15
                shares = estimated_interactions * 0.05
                saves = estimated_interactions * 0.05
                
                platform_eng_weights = engagement_weights.get(platform, {})
                weighted_score = (
                    likes * platform_eng_weights.get('likes', 1) +
                    comments * platform_eng_weights.get('comments', 1) +
                    shares * platform_eng_weights.get('shares', 1) +
                    saves * platform_eng_weights.get('saves', 1)
                )
                post['weighted_engagement_score'] = weighted_score
                total_weighted_engagement += weighted_score

    return creators, total_predicted_reach, total_weighted_engagement


# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")
APP_VERSION = "7.0.0" # Final Integrated Version

if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    api_key = st.session_state.get('openai_api_key')
    for key in list(st.session_state.keys()): del st.session_state[key]
    
    st.session_state.app_version = APP_VERSION
    st.session_state.api_key_entered = True if api_key else False
    st.session_state.openai_api_key = api_key
    st.session_state.metrics_confirmed = False
    st.session_state.comparison_profile_complete = False # New state for the advanced Step 2
    st.session_state.benchmark_flow_complete = False
    st.session_state.scorecard_ready = False
    st.session_state.show_ppt_creator = False
    st.session_state.metrics = []
    st.session_state.benchmark_df = pd.DataFrame()
    st.session_state.sheets_dict = None
    st.session_state.presentation_buffer = None
    st.session_state.proposed_benchmarks = {}
    st.session_state.avg_actuals = {}
    st.session_state.saved_moments = {}
    st.session_state.campaign_profile = {}
    st.session_state.creators = [{'handle': 'creator_a', 'platform': 'Instagram', 'follower_count': 150000, 'saturation': 'Medium', 'posts': [
        {'format': 'Reel', 'cost': 2500, 'historical_reach_for_format': 80000, 'historical_er_for_format': 4.5, 'paid_amplification': 500, 'is_new_content': True, 'cta_type': 'Hard CTA'},
        {'format': 'Story', 'cost': 500, 'historical_reach_for_format': 20000, 'historical_er_for_format': 1.8, 'paid_amplification': 0, 'is_new_content': True, 'cta_type': 'Soft CTA'}
    ]}]


st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar()

# ================================================================================
# Step 0: API Key Entry
# ================================================================================
if not st.session_state.api_key_entered:
    st.header("Step 0: Enter Your OpenAI API Key")
    with st.form("api_key_form"):
        api_key_input = st.text_input("🔑 OpenAI API Key", type="password")
        if st.form_submit_button("Submit API Key"):
            if api_key_input:
                st.session_state.openai_api_key = api_key_input
                st.session_state.api_key_entered = True
                st.rerun()
            else:
                st.error("Please enter a valid OpenAI API key.")

# ================================================================================
# Step 1: Metric Selection
# ================================================================================
elif not st.session_state.metrics_confirmed:
    st.header("Step 1: Select Your Core Scorecard Metrics (RDA)")
    st.info("Select metrics from the dropdown, or add your own below. Press Enter to add a custom metric.")
    
    predefined_metrics = [
        "Video views (Franchise)", "Social Impressions", "Press UMV (unique monthly views)",
        "Social Conversation Volume", "Views trailer", "UGC Views", 
        "Social Impressions-Posts with trailer (FB, IG, X)", "Social Impressions-All posts",
        "Nb. press articles", "Social Sentiment (Franchise)", "Trailer avg % viewed (Youtube)",
        "Email Open Rate (OR)", "Email Click Through Rate (CTR)", "Labs program sign-ups",
        "Discord channel sign-ups", "% Trailer views from Discord (Youtube)",
        "Labs sign up click-through Web", "Sessions", "DAU", "Hours Watched (Streams)"
    ]

    if 'current_metrics' not in st.session_state:
        st.session_state.current_metrics = ["Video views (Franchise)", "Social Impressions"]

    all_possible_metrics = sorted(list(set(predefined_metrics + st.session_state.current_metrics)))

    def update_selections():
        st.session_state.current_metrics = st.session_state.multiselect_key

    st.multiselect(
        "Select metrics:", 
        options=all_possible_metrics, 
        default=st.session_state.current_metrics,
        key="multiselect_key",
        on_change=update_selections
    )
    
    def add_custom_metric():
        custom_metric = st.session_state.custom_metric_input.strip()
        if custom_metric and custom_metric not in st.session_state.current_metrics:
            st.session_state.current_metrics.append(custom_metric)
        st.session_state.custom_metric_input = ""

    st.text_input(
        "✍️ Add Custom Metric (and press Enter)", 
        key="custom_metric_input", 
        on_change=add_custom_metric
    )

    st.markdown("---")

    if st.button("Confirm Metrics & Proceed →", type="primary"):
        if not st.session_state.current_metrics:
            st.error("Please select at least one metric.")
        else:
            st.session_state.metrics = st.session_state.current_metrics
            st.session_state.metrics_confirmed = True
            st.rerun()

# ================================================================================
# NEW ADVANCED Step 2: Define Campaign Profile for Comparison
# ================================================================================
elif not st.session_state.comparison_profile_complete:
    st.header("Step 2: Define Campaign Profile for Comparison")
    
    with st.form("campaign_profile_form"):
        st.subheader("Core Campaign Details")
        campaign_name = st.text_input("Campaign Name", "Q4 Product Launch")
        total_budget = st.number_input("Total Budget ($)", min_value=1, format="%d", value=250000)
        
        st.markdown("---")
        st.subheader("Live Predictive Summary")
        _, total_reach, total_engagement = calculate_predictions_advanced(st.session_state.creators)
        total_creator_cost = sum(post.get('cost', 0) for creator in st.session_state.creators for post in creator.get('posts', []))
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Defined Cost", f"${total_creator_cost:,.0f}")
        c2.metric("Total Predicted Reach", f"{total_reach:,.0f}")
        c3.metric("Total Weighted Engagement Score", f"{total_engagement:,.0f}")

        submitted = st.form_submit_button("Save Profile & Proceed to Benchmarking →", type="primary")
        if submitted:
            final_creators, total_reach, total_engagement = calculate_predictions_advanced(st.session_state.creators)
            st.session_state.campaign_profile = {
                "CoreDetails": {"CampaignName": campaign_name, "TotalBudget": total_budget},
                "InfluencerStrategy": {"CreatorList": final_creators, "TotalPredictedReach": total_reach, "TotalWeightedEngagement": total_engagement}
            }
            st.session_state.comparison_profile_complete = True
            st.rerun()

    st.markdown("---")
    st.subheader("Define Creator Activations")
    for i, creator in enumerate(st.session_state.creators):
        with st.expander(f"Creator {i+1}: {creator.get('handle', 'New Creator')}", expanded=True):
            creator['handle'] = st.text_input("Handle", value=creator.get('handle', ''), key=f"handle_{i}")
            c1, c2, c3 = st.columns(3)
            creator['platform'] = c1.selectbox("Platform", ["Instagram", "TikTok", "YouTube"], key=f"platform_{i}")
            creator['follower_count'] = c2.number_input("Followers", min_value=0, format="%d", key=f"followers_{i}")
            creator['saturation'] = c3.selectbox("Creator Saturation", ["Low", "Medium", "High"], help="How frequently does this creator post sponsored content?", key=f"saturation_{i}")

            st.markdown("**Creator Posts:**")
            for j, post in enumerate(creator.get('posts', [])):
                st.markdown(f"**Post {j+1}**")
                p1, p2, p3 = st.columns(3)
                post['format'] = p1.selectbox("Format", ['Reel', 'Story', 'Static Post', 'Long-form Video'], key=f"post_format_{i}_{j}")
                post['cost'] = p2.number_input("Cost ($)", min_value=0, format="%d", key=f"post_cost_{i}_{j}")
                post['paid_amplification'] = p3.number_input("Paid Amplification ($)", min_value=0, format="%d", key=f"paid_{i}_{j}")
                
                p4, p5, p6 = st.columns(3)
                post['historical_reach_for_format'] = p4.number_input("Historical Reach for this Format", min_value=0, format="%d", key=f"post_hist_reach_{i}_{j}")
                post['historical_er_for_format'] = p5.number_input("Historical ER for this Format (%)", format="%.2f", key=f"post_hist_er_{i}_{j}")
                post['cta_type'] = p6.selectbox("CTA Type", ["Soft CTA", "Hard CTA"], help="A 'Hard CTA' may slightly lower organic engagement.", key=f"cta_{i}_{j}")
                
                post['is_new_content'] = st.toggle("First-Use Content", value=True, key=f"new_{i}_{j}")
                
                st.markdown("---")
                temp_data = {'follower_count': creator['follower_count'], 'saturation': creator['saturation'], 'posts': [post]}
                _, post_reach, post_wes = calculate_predictions_advanced([temp_data])
                pr1, pr2 = st.columns(2)
                pr1.metric("Predicted Post Reach", f"{post_reach:,.0f}")
                pr2.metric("Predicted Post Depth (WES)", f"{post_wes:,.0f}")

                if st.button("Remove Post", key=f"remove_post_{i}_{j}"):
                    st.session_state.creators[i]['posts'].pop(j)
                    st.rerun()
            
            if st.button("Add Post", key=f"add_post_{i}"):
                if 'posts' not in st.session_state.creators[i]: st.session_state.creators[i]['posts'] = []
                st.session_state.creators[i]['posts'].append({})
                st.rerun()

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("Add Creator"): st.session_state.creators.append({}); st.rerun()
    if c2.button("Remove Last Creator"): 
        if st.session_state.creators: st.session_state.creators.pop(); st.rerun()

# ================================================================================
# Step 3: Original Benchmark Calculation
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 3: Benchmark Calculation (Optional)")
    
    st.info("The predictions from Step 2 are now available. You can also use this section to calculate benchmarks from historical data for non-influencer metrics.")

    benchmark_choice = st.radio(
        "Would you like to calculate proposed benchmark values using historical data?",
        ("No, I will enter benchmarks manually later.", "Yes, calculate benchmarks from past events."),
        key="benchmark_choice_radio"
    )

    if benchmark_choice == "Yes, calculate benchmarks from past events.":
        with st.form("benchmark_data_form"):
            historical_inputs = {}
            for metric in st.session_state.metrics:
                st.markdown(f"--- \n #### Data for: **{metric}**")
                three_month_avg = st.number_input(f"3-Month Average (Baseline Method) for '{metric}'", min_value=0.0, format="%.2f", key=f"3m_avg_{metric}")
                df_template = pd.DataFrame([{"Event Name": "Past Event 1", "Baseline (7-day)": None, "Actual (7-day)": None}])
                edited_df = st.data_editor(df_template, key=f"hist_editor_{metric}", num_rows="dynamic", use_container_width=True)
                historical_inputs[metric] = {"historical_df": edited_df, "three_month_avg": three_month_avg}

            if st.form_submit_button("Calculate All Proposed Benchmarks & Proceed →", type="primary"):
                with st.spinner("Analyzing historical data..."):
                    summary_df, proposed_benchmarks, avg_actuals = calculate_all_benchmarks(historical_inputs)
                    st.session_state.benchmark_df = summary_df
                    st.session_state.proposed_benchmarks = proposed_benchmarks
                    st.session_state.avg_actuals = avg_actuals
                    st.session_state.benchmark_flow_complete = True
                st.rerun()
    else:
        if st.button("Proceed to Scorecard Creation →", type="primary"):
            st.session_state.benchmark_flow_complete = True
            st.rerun()

# ================================================================================
# Step 4 & 5 - Main App Logic (Original)
# ================================================================================
else:
    app_config = {
        'openai_api_key': st.session_state.openai_api_key, 
        'metrics': st.session_state.metrics,
        'proposed_benchmarks': st.session_state.get('proposed_benchmarks'),
        'avg_actuals': st.session_state.get('avg_actuals')
    }
    
    st.header("Step 4: Build & Save Scorecard Moments")
    if 'sheets_dict' not in st.session_state or st.session_state.sheets_dict is None:
        st.session_state.sheets_dict = process_scorecard_data(app_config)

    st.info("Fill in the 'Actuals' and 'Benchmark' columns, give the scorecard a name, and save it as a 'moment'.")
    current_scorecard_df = next(iter(st.session_state.sheets_dict.values()), None)

    if current_scorecard_df is not None:
        edited_df = st.data_editor(current_scorecard_df, key="moment_editor", use_container_width=True, num_rows="dynamic")
        if 'Benchmark' in edited_df.columns and edited_df['Benchmark'].notna().any():
            edited_df['% Difference'] = ((pd.to_numeric(edited_df['Actuals'], errors='coerce') - pd.to_numeric(edited_df['Benchmark'], errors='coerce')) / pd.to_numeric(edited_df['Benchmark'], errors='coerce').replace(0, pd.NA)).apply(lambda x: f"{x:.1%}" if pd.notna(x) else None)
        else:
            edited_df['% Difference'] = None
        col1, col2 = st.columns([3, 1])
        moment_name = col1.text_input("Name for this Scorecard Moment", placeholder="e.g., Pre-Reveal, Launch Week")
        if col2.button("💾 Save Moment", use_container_width=True, type="primary"):
            if moment_name:
                st.session_state.saved_moments[moment_name] = edited_df
                st.success(f"Saved moment: '{moment_name}'")
                st.session_state.sheets_dict = None
                st.rerun()
            else:
                st.error("Please enter a name for the moment before saving.")

    if st.session_state.saved_moments:
        st.markdown("---")
        st.subheader("Saved Scorecard Moments")
        if 'benchmark_df' in st.session_state and st.session_state.benchmark_df is not None and not st.session_state.benchmark_df.empty:
            with st.expander("View Benchmark Calculation Summary"):
                st.dataframe(st.session_state.benchmark_df.set_index("Metric"), use_container_width=True)
        for name, df in st.session_state.saved_moments.items():
            with st.expander(f"View Moment: {name}"):
                st.dataframe(df, use_container_width=True)
        st.session_state.show_ppt_creator = True

    if st.session_state.get('show_ppt_creator'):
        st.markdown("---")
        st.header("Step 5: Create Presentation")
        if st.session_state.get("presentation_buffer"):
            st.download_button(label="✅ Download Your Presentation!", data=st.session_state.presentation_buffer, file_name="game_scorecard_presentation.pptx", use_container_width=True)
        with st.form("ppt_form"):
            st.subheader("Presentation Style & Details")
            if st.session_state.saved_moments:
                selected_moments = st.multiselect("Select which saved moments to include in the presentation:",
                    options=list(st.session_state.saved_moments.keys()),
                    default=list(st.session_state.saved_moments.keys()))
            else:
                selected_moments = []
                st.warning("No scorecard moments saved yet. Please save at least one moment above.")
            col1, col2 = st.columns(2)
            selected_style_name = col1.radio("Select Style Preset:", options=list(STYLE_PRESETS.keys()), horizontal=True)
            image_region_prompt = col2.text_input("Region for AI Background Image", "Brazil")
            ppt_title = st.text_input("Presentation Title", "Game Scorecard")
            ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
            submitted = st.form_submit_button("Generate Presentation", use_container_width=True)
            if submitted:
                if not selected_moments:
                    st.error("Please select at least one saved moment to include in the presentation.")
                else:
                    with st.spinner(f"Building presentation with {selected_style_name} style..."):
                        presentation_data = {name: st.session_state.saved_moments[name] for name in selected_moments}
                        style_guide = STYLE_PRESETS[selected_style_name]
                        ppt_buffer = create_presentation(
                            title=ppt_title,
                            subtitle=ppt_subtitle,
                            scorecard_moments=selected_moments,
                            sheets_dict=presentation_data,
                            style_guide=style_guide,
                            region_prompt=image_region_prompt,
                            openai_api_key=st.session_state.openai_api_key 
                        )
                        st.session_state["presentation_buffer"] = ppt_buffer
                        st.rerun()
