import streamlit as st
from io import BytesIO
from datetime import datetime
import pandas as pd
import requests
import json
from pptx import Presentation

# --- Local Imports from our other files ---
# Assuming these files exist and are correct from your project setup
from style import STYLE_PRESETS
from ui import render_sidebar
from data_processing import process_scorecard_data, calculate_all_benchmarks, get_ai_metric_categories
from powerpoint import create_presentation
from excel import create_excel_workbook

# ================================================================================
# NEW: AI & Presentation Parsing Functions
# ================================================================================
def extract_text_from_ppt(uploaded_file):
    """Extracts all text from an uploaded .pptx file."""
    try:
        prs = Presentation(uploaded_file)
        text_runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        text_runs.append(run.text)
        return "\n".join(text_runs)
    except Exception as e:
        st.error(f"Error reading PowerPoint file: {e}")
        return ""

def get_creator_data_from_text(text, api_key):
    """Uses OpenAI API to extract structured creator data from text."""
    if not api_key:
        st.error("OpenAI API key is required for this feature.")
        return None
        
    prompt = f"""
    You are an expert marketing analyst. Your task is to read the following text extracted from a campaign planning presentation and identify all the influencer/creator activations mentioned.
    For each creator, extract their handle, platform, follower count, and saturation level.
    For each post by that creator, extract the format, cost, historical reach for that format, historical engagement rate for that format, any paid amplification budget, whether it's new content, and the CTA type.
    Return the data as a single JSON object with a single key "creators" which is a list of creator objects.

    Here is the text:
    ---
    {text}
    ---

    Respond ONLY with the JSON object. Example format:
    {{
      "creators": [
        {{
          "handle": "creator_a",
          "platform": "Instagram",
          "follower_count": 150000,
          "saturation": "Medium",
          "posts": [
            {{ "format": "Reel", "cost": 2500, "historical_reach_for_format": 80000, "historical_er_for_format": 4.5, "paid_amplification": 500, "is_new_content": true, "cta_type": "Hard CTA" }}
          ]
        }}
      ]
    }}
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "gpt-4-turbo", "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}, "temperature": 0.1}
    
    try:
        api_url = "https://api.openai.com/v1/chat/completions"
        response = requests.post(api_url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        return json.loads(response.json()['choices'][0]['message']['content'])
    except Exception as e:
        st.error(f"AI data extraction failed: {e}")
        return None

# ================================================================================
# WORLD-CLASS PREDICTION ENGINE
# ================================================================================
def calculate_predictions_advanced(creators):
    """
    Calculates predicted reach and depth using a multi-factor model that accounts
    for paid media, content freshness, and creator saturation.
    """
    total_predicted_reach = 0
    total_weighted_engagement = 0

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
    PAID_BOOST_FACTOR = 0.02
    FRESHNESS_BONUS = 0.15
    SATURATION_PENALTY = {'Medium': 0.10, 'High': 0.25}
    CTA_ENGAGEMENT_PENALTY = {'Soft CTA': 0, 'Hard CTA': 0.15}

    for creator in creators:
        creator_saturation = creator.get('saturation', 'Low')
        if 'posts' in creator and creator['posts']:
            for post in creator['posts']:
                baseline_reach = post.get('historical_reach_for_format', 0)
                paid_boost = (post.get('paid_amplification', 0) / 1000) * PAID_BOOST_FACTOR
                freshness_boost = FRESHNESS_BONUS if post.get('is_new_content', True) else 0
                saturation_penalty = SATURATION_PENALTY.get(creator_saturation, 0)
                adjustment_factor = 1 + paid_boost + freshness_boost - saturation_penalty
                predicted_reach = baseline_reach * adjustment_factor
                post['predicted_reach'] = predicted_reach
                total_predicted_reach += predicted_reach

                base_er = post.get('historical_er_for_format', 0) / 100.0
                cta_penalty = CTA_ENGAGEMENT_PENALTY.get(post.get('cta_type', 'Soft CTA'), 0)
                adjusted_er = base_er * (1 - cta_penalty)
                estimated_interactions = predicted_reach * adjusted_er
                likes, comments, shares, saves = estimated_interactions * 0.75, estimated_interactions * 0.15, estimated_interactions * 0.05, estimated_interactions * 0.05
                platform_eng_weights = engagement_weights.get(creator.get('platform', 'Instagram'), {})
                weighted_score = (likes * platform_eng_weights.get('likes', 1) + comments * platform_eng_weights.get('comments', 1) + shares * platform_eng_weights.get('shares', 1) + saves * platform_eng_weights.get('saves', 1))
                post['weighted_engagement_score'] = weighted_score
                total_weighted_engagement += weighted_score
    return creators, total_predicted_reach, total_weighted_engagement

# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")
APP_VERSION = "7.1.0" # Version with AI PPT Parsing

if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    api_key = st.session_state.get('openai_api_key')
    for key in list(st.session_state.keys()): del st.session_state[key]
    
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
    st.session_state.creators = []

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
    # This section is simplified for the advanced workflow
    st.info("Select the final metrics you want to track on your scorecard.")
    default_metrics = ["Impressions", "Reach", "Engagement", "WES", "Conversions"]
    st.session_state.metrics = st.multiselect("Select your primary scorecard metrics:", options=default_metrics, default=["Reach", "WES"])
    
    if st.button("Confirm Metrics & Proceed →", type="primary"):
        st.session_state.metrics_confirmed = True
        st.rerun()

# ================================================================================
# NEW ADVANCED Step 2: Define Campaign Profile for Comparison
# ================================================================================
elif not st.session_state.comparison_profile_complete:
    st.header("Step 2: Define Campaign Profile for Comparison")
    
    # --- NEW: AI-Powered Auto-Population Section ---
    with st.expander("🚀 Auto-Populate from Presentation"):
        st.info("Upload a .pptx file containing your campaign plan. The AI will attempt to extract creator details and populate the form below.")
        uploaded_file = st.file_uploader("Choose a PowerPoint file", type="pptx")
        
        if st.button("Analyze Presentation and Populate Form"):
            if uploaded_file is not None and st.session_state.openai_api_key:
                with st.spinner("Reading presentation and contacting OpenAI..."):
                    extracted_text = extract_text_from_ppt(uploaded_file)
                    if extracted_text:
                        ai_data = get_creator_data_from_text(extracted_text, st.session_state.openai_api_key)
                        if ai_data and "creators" in ai_data:
                            st.session_state.creators = ai_data["creators"]
                            st.success("Successfully populated creator data from presentation!")
                            st.rerun()
                        else:
                            st.error("AI could not extract valid creator data. Please check the presentation content or enter details manually.")
            else:
                st.warning("Please upload a file and ensure your OpenAI API key is entered.")
    
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
            creator['platform'] = c1.selectbox("Platform", ["Instagram", "TikTok", "YouTube"], index=["Instagram", "TikTok", "YouTube"].index(creator.get('platform', 'Instagram')), key=f"platform_{i}")
            creator['follower_count'] = c2.number_input("Followers", min_value=0, value=creator.get('follower_count',0), format="%d", key=f"followers_{i}")
            creator['saturation'] = c3.selectbox("Creator Saturation", ["Low", "Medium", "High"], index=["Low", "Medium", "High"].index(creator.get('saturation', 'Low')), help="How frequently does this creator post sponsored content?", key=f"saturation_{i}")

            st.markdown("**Creator Posts:**")
            for j, post in enumerate(creator.get('posts', [])):
                st.markdown(f"**Post {j+1}**")
                p1, p2, p3 = st.columns(3)
                post['format'] = p1.selectbox("Format", ['Reel', 'Story', 'Static Post', 'Long-form Video'], index=['Reel', 'Story', 'Static Post', 'Long-form Video'].index(post.get('format', 'Reel')), key=f"post_format_{i}_{j}")
                post['cost'] = p2.number_input("Cost ($)", min_value=0, value=post.get('cost',0), format="%d", key=f"post_cost_{i}_{j}")
                post['paid_amplification'] = p3.number_input("Paid Amplification ($)", min_value=0, value=post.get('paid_amplification',0), format="%d", key=f"paid_{i}_{j}")
                
                p4, p5, p6 = st.columns(3)
                post['historical_reach_for_format'] = p4.number_input("Historical Reach for this Format", min_value=0, value=post.get('historical_reach_for_format',0), format="%d", key=f"post_hist_reach_{i}_{j}")
                post['historical_er_for_format'] = p5.number_input("Historical ER for this Format (%)", value=post.get('historical_er_for_format',0.0), format="%.2f", key=f"post_hist_er_{i}_{j}")
                post['cta_type'] = p6.selectbox("CTA Type", ["Soft CTA", "Hard CTA"], index=["Soft CTA", "Hard CTA"].index(post.get('cta_type', 'Soft CTA')), help="A 'Hard CTA' may slightly lower organic engagement.", key=f"cta_{i}_{j}")
                
                post['is_new_content'] = st.toggle("First-Use Content", value=post.get('is_new_content', True), key=f"new_{i}_{j}")
                
                st.markdown("---")
                temp_data = {'saturation': creator['saturation'], 'posts': [post], 'platform': creator['platform']}
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
    with st.expander("View Predictive Benchmarks"):
        st.json(st.session_state.campaign_profile.get("InfluencerStrategy", {}))

    if st.button("Proceed to Scorecard Creation →", type="primary"):
        # We can pre-populate the benchmarks here if needed
        # For now, we proceed to the manual entry/final scorecard
        st.session_state.benchmark_flow_complete = True
        st.rerun()

# ================================================================================
# Step 4 & 5 - Main App Logic (Original)
# ================================================================================
else:
    st.header("Step 4: Build & Save Scorecard Moments")
    # This section is now a placeholder as the main logic is in the predictive step
    st.info("This is the final scorecard creation step. The benchmarks would be populated from the predictions made in Step 2.")
    
    # Create a dummy dataframe for demonstration
    if 'sheets_dict' not in st.session_state:
        # Use predicted benchmarks to populate the scorecard
        reach_benchmark = st.session_state.campaign_profile.get("InfluencerStrategy", {}).get("TotalPredictedReach", 0)
        wes_benchmark = st.session_state.campaign_profile.get("InfluencerStrategy", {}).get("TotalWeightedEngagement", 0)
        
        scorecard_data = {
            'Category': ['Reach', 'Depth'],
            'Metric': ['Predicted Reach', 'Weighted Engagement Score (WES)'],
            'Actuals': [None, None],
            'Benchmark': [f"{reach_benchmark:,.0f}", f"{wes_benchmark:,.0f}"],
            '% Difference': [None, None]
        }
        df = pd.DataFrame(scorecard_data)
        st.session_state.sheets_dict = {"Final Scorecard": df}

    current_scorecard_df = st.session_state.sheets_dict["Final Scorecard"]
    st.data_editor(current_scorecard_df, use_container_width=True, hide_index=True)
    
    if st.button("Generate Presentation"):
        st.success("Presentation generation would be triggered here.")
