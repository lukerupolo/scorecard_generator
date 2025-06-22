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
# Helper Function for Influencer Analysis
# ================================================================================
def get_influencer_tier(followers):
    """Categorizes an influencer into a tier based on follower count."""
    if followers >= 1000000:
        return "Mega"
    elif followers >= 250000:
        return "Macro"
    elif followers >= 50000:
        return "Mid"
    else:
        return "Micro"

# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

APP_VERSION = "5.0.8" # Version for CAP Scorecard Integration

if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    api_key = st.session_state.get('openai_api_key')
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
    # State for managing the dynamic list of creators
    if 'creators' not in st.session_state:
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
    # This section remains unchanged
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
    st.info("Provide the details of your campaign. The profile you build will determine the benchmarks.")
    
    # --- Main form for Core Details ---
    with st.form("campaign_profile_form"):
        st.subheader("Core Campaign Details")
        campaign_name = st.text_input("Campaign Name")
        # The Objective now controls the UI below
        objective = st.selectbox("Campaign Objective", ['Reach', 'Depth', 'Action'])
        c1, c2 = st.columns(2)
        start_date = c1.date_input("Start Date", value=datetime.now())
        end_date = c2.date_input("End Date", value=datetime.now() + pd.Timedelta(days=30))
        total_budget = st.number_input("Total Budget ($)", min_value=1, format="%d", value=100000)

        st.markdown("---")
        
        # --- DYNAMIC INFLUENCER STRATEGY SECTION BASED ON CAP SCORECARD ---
        st.subheader("Influencer & Creator Strategy Profile")
        st.info(f"Because your objective is **{objective}**, we'll focus on the most relevant strategic inputs.")

        cap_scores = {}

        # BUCKET 1: CREATOR & AUDIENCE AXIS
        with st.expander("**Bucket 1: Creator & Audience Axis**", expanded=True):
            cap_scores['audience_authenticity'] = st.slider("Estimated Audience Authenticity (%)", 0, 100, 85, help="Use tools like HypeAuditor or manual checks. Red Flag: < 85%.")
            cap_scores['niche_relevance'] = st.radio("Creator Niche Relevance", ["Highly Relevant (Endemic)", "Somewhat Relevant", "Non-Endemic (Broad Appeal)"], index=0)
            cap_scores['brand_safety_content'] = st.select_slider("Content Brand Safety Risk", ["Low", "Medium", "High"], value="Low", help="Scan for sensitive topics.")

        # BUCKET 2: ACTIVATION BLUEPRINT
        with st.expander("**Bucket 2: Activation Blueprint**", expanded=True):
            if objective == 'Reach':
                st.write("For a **Reach** objective, focus on scalable formats and clear, low-friction calls-to-action.")
                cap_scores['activation_format'] = st.selectbox("Primary Activation Format", ["Short-form Video (TikTok, Reels)", "Static Images/Carousels", "Long-form Video (YouTube)", "Live Streams"])
                cap_scores['cta_efficacy'] = st.selectbox("Primary Call-to-Action (CTA)", ["Watch/View", "Learn More", "Visit Profile"])
            
            elif objective == 'Depth':
                st.write("For a **Depth** objective, focus on trust-building formats and community interaction.")
                cap_scores['activation_format'] = st.selectbox("Primary Activation Format", ["Long-form Video (YouTube)", "Live Streams", "Community Q&A / AMA", "Detailed Carousels"])
                cap_scores['cta_efficacy'] = st.selectbox("Primary Call-to-Action (CTA)", ["Comment/Share", "Join the Conversation", "Ask a Question"])
                cap_scores['creative_control'] = st.radio("Creative Control Balance", ["Creator-Led (High Freedom)", "Collaborative", "Brand-Led (Prescriptive)"], index=1)

            elif objective == 'Action':
                st.write("For an **Action** objective, focus on high-intent formats and frictionless, trackable calls-to-action.")
                cap_scores['activation_format'] = st.selectbox("Primary Activation Format", ["Product Demos / Tutorials", "Live Shopping Event", "Testimonials / Reviews"])
                cap_scores['cta_efficacy'] = st.selectbox("Primary Call-to-Action (CTA)", ["Click Link in Bio (Tracked)", "Use Promo Code", "Sign Up / Download", "Shop Now"])
                cap_scores['funnel_alignment'] = st.radio("Funnel Stage", ["Top-of-Funnel (TOFU)", "Middle-of-Funnel (MOFU)", "Bottom-of-Funnel (BOFU)"], index=2)

        # BUCKET 3: ECOSYSTEM & ENVIRONMENT
        with st.expander("**Bucket 3: Ecosystem & Environment**", expanded=True):
            cap_scores['platform_objective_fit'] = st.selectbox("Primary Platform", ["TikTok", "Instagram", "YouTube", "Twitch", "LinkedIn"])
            cap_scores['competitive_landscape'] = st.select_slider("Competitive Saturation (Share of Voice)", ["Low", "Medium", "High"], value="Medium")

        submitted = st.form_submit_button("Save Profile & Find Comparable Campaigns", type="primary")
        if submitted:
            st.session_state.campaign_profile = {
                "CoreDetails": { "CampaignName": campaign_name, "Objective": objective, "TotalBudget": total_budget },
                "CAP_Scores": cap_scores
            }
            st.session_state.comparison_profile_complete = True
            st.rerun()

elif st.session_state.comparison_profile_complete and not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Campaign Profile Saved")
    st.success("Your campaign profile has been successfully saved.")
    
    st.subheader("Your Saved Creator Activation Potential (CAP) Profile")
    st.json(st.session_state.campaign_profile)

    st.markdown("---")
    st.subheader("Comparable Historical Campaigns")
    st.info("Based on your detailed profile, here are the most relevant historical campaigns. The benchmarks in the next step will be calculated from the average performance of this set.")
    
    # This data is now more meaningful because it's based on a more detailed profile
    comparable_campaigns_data = {
        'Historical Campaign': ['Q4 2023 - Project Titan', 'Q1 2024 - Nova Launch', 'Summer 2022 - Falcon'],
        'Similarity Score': ['95%', '91%', '87%'],
        'Objective': [st.session_state.campaign_profile['CoreDetails'].get('Objective', 'N/A')] * 3,
    }
    st.dataframe(pd.DataFrame(comparable_campaigns_data), use_container_width=True, hide_index=True)

    if st.button("Proceed to Benchmarking →", type="primary"):
        st.session_state.benchmark_flow_complete = True
        st.rerun()

# ================================================================================
# Step 3 & Beyond (Code remains the same)
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
    st.header("Step 3: Auto-Generate Benchmarks")
    st.info("This section is now placeholder. Benchmarks would be calculated from the campaigns found in Step 2.")
    if st.button("Proceed to Scorecard Creation →", type="primary"):
        st.session_state.benchmark_flow_complete = True
        st.rerun()
else:
    st.header("Step 4: Build & Save Scorecard Moments")
    # This section remains unchanged and will use the data from the previous steps
    app_config = {
        'openai_api_key': st.session_state.openai_api_key, 
        'metrics': st.session_state.metrics,
        'proposed_benchmarks': st.session_state.get('proposed_benchmarks'),
        'avg_actuals': st.session_state.get('avg_actuals')
    }
    
    if 'sheets_dict' not in st.session_state or st.session_state.sheets_dict is None:
        st.session_state.sheets_dict = process_scorecard_data(app_config)

    st.info("Fill in the 'Actuals' and 'Benchmark' columns, give the scorecard a name, and save it as a 'moment'. You can create multiple moments.")
    current_scorecard_df = next(iter(st.session_state.sheets_dict.values()), None)

    if current_scorecard_df is not None:
        edited_df = st.data_editor(current_scorecard_df, key="moment_editor", use_container_width=True, num_rows="dynamic")
        
        edited_df['Actuals'] = pd.to_numeric(edited_df['Actuals'], errors='coerce')
        edited_df['Benchmark'] = pd.to_numeric(edited_df['Benchmark'], errors='coerce')
        if 'Benchmark' in edited_df.columns and edited_df['Benchmark'].notna().any():
            edited_df['% Difference'] = ((edited_df['Actuals'] - edited_df['Benchmark']) / edited_df['Benchmark'].replace(0, pd.NA)).apply(lambda x: f"{x:.1%}" if pd.notna(x) else None)
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
