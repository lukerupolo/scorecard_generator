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
# NEW: Helper Function for Predictive Calculations
# ================================================================================
def calculate_predictions(creators):
    """
    Calculates the predicted reach and weighted engagement score for each post
    and aggregates the totals for the campaign.

    Args:
        creators (list): A list of creator dictionaries.

    Returns:
        tuple: A tuple containing the updated list of creators with predictions,
               the total predicted reach, and the total weighted engagement score.
    """
    total_predicted_reach = 0
    total_weighted_engagement = 0

    # Platform and format-specific weights for the formulas
    # These would ideally be derived from historical data analysis
    reach_weights = {
        'Instagram': {'Reel': 1.2, 'Story': 0.4, 'Static Post': 0.9, 'Long-form Video': 0.7},
        'TikTok': {'Reel': 1.5, 'Story': 0.5, 'Static Post': 0.8, 'Long-form Video': 0.9}, # Note: 'Reel' for consistency
        'YouTube': {'Long-form Video': 0.8, 'Reel': 1.3} # Note: 'Reel' for Shorts
    }
    engagement_weights = {
        'Instagram': {'likes': 1, 'comments': 3, 'shares': 5},
        'TikTok': {'likes': 1, 'comments': 2, 'shares': 4},
        'YouTube': {'likes': 1, 'comments': 4, 'shares': 2}
    }

    for creator in creators:
        follower_count = creator.get('follower_count', 1) # Use 1 to avoid division by zero
        # Use the new avg_historical_reach field for a more accurate RER
        avg_historical_reach = creator.get('avg_historical_reach', follower_count * 0.6) # Default to 60% if not provided

        # Calculate the Historical Reach Efficiency Rate (RER)
        historical_rer = avg_historical_reach / follower_count if follower_count > 0 else 0

        if 'posts' in creator and creator['posts']:
            for post in creator['posts']:
                platform = creator.get('platform', 'Instagram')
                post_format = post.get('format', 'Reel')
                expected_er = post.get('expected_engagement_rate', 0) / 100.0

                # --- UPDATED: Calculate Predicted Reach for the post using RER ---
                platform_format_weight = reach_weights.get(platform, {}).get(post_format, 1.0)
                predicted_reach = (follower_count * historical_rer) * platform_format_weight
                post['predicted_reach'] = predicted_reach
                total_predicted_reach += predicted_reach

                # --- Calculate Weighted Engagement Score for the post ---
                estimated_interactions = predicted_reach * expected_er
                
                # Assume a simple interaction split for this example
                likes = estimated_interactions * 0.8
                comments = estimated_interactions * 0.15
                shares = estimated_interactions * 0.05
                
                platform_eng_weights = engagement_weights.get(platform, {})
                weighted_score = (
                    likes * platform_eng_weights.get('likes', 1) +
                    comments * platform_eng_weights.get('comments', 1) +
                    shares * platform_eng_weights.get('shares', 1)
                )
                post['weighted_engagement_score'] = weighted_score
                total_weighted_engagement += weighted_score

    return creators, total_predicted_reach, total_weighted_engagement

# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

APP_VERSION = "5.0.8" # Version for RER-based Predictive Formulas

if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    api_key = st.session_state.get('openai_api_key')
    # Clear all state to ensure a clean start
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state.app_version = APP_VERSION
    st.session_state.api_key_entered = True if api_key else False
    st.session_state.openai_api_key = api_key
    st.session_state.metrics_confirmed = False
    st.session_state.comparison_profile_complete = False
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
    # State for managing dynamic creator and post lists
    if 'creators' not in st.session_state:
        st.session_state.creators = [
            {'handle': 'creator_a', 'platform': 'Instagram', 'follower_count': 75000, 'avg_historical_reach': 45000, 'niche_category': 'Gaming', 'audience_authenticity_score': 0.95, 'posts': [
                {'format': 'Reel', 'cost': 1500, 'expected_engagement_rate': 5.5},
                {'format': 'Story', 'cost': 500, 'expected_engagement_rate': 2.0}
            ]}
        ]


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
# NEW Step 2: Define Campaign Profile for Comparison
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
# Step 3: Optional Benchmark Calculation 
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 3: Auto-Generate Benchmarks")
    st.info("This section is now placeholder. Benchmarks would be calculated from the campaigns found in Step 2.")
    if st.button("Proceed to Scorecard Creation →", type="primary"):
        st.session_state.benchmark_flow_complete = True
        st.rerun()

# ================================================================================
# Step 4 & 5 - Main App Logic
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
