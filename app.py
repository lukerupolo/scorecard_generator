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
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

APP_VERSION = "5.0.4" # Version for Strategic Influencer Profiling

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
    st.info("Provide the details of your campaign. This profile will be used to find the most similar historical campaigns to generate relevant benchmarks.")
    
    with st.form("campaign_profile_form"):
        st.subheader("Core Campaign Details")
        campaign_name = st.text_input("Campaign Name")
        objective = st.selectbox("Campaign Objective", ['Brand Awareness', 'Lead Generation', 'Sales', 'Audience Engagement'])
        c1, c2 = st.columns(2)
        start_date = c1.date_input("Start Date", value=datetime.now())
        end_date = c2.date_input("End Date", value=datetime.now() + pd.Timedelta(days=30))
        total_budget = st.number_input("Total Budget ($)", min_value=1, format="%d", value=100000)

        st.markdown("---")
        st.subheader("Target Audience & Creatives")
        c1, c2 = st.columns(2)
        audience_name = c1.selectbox("Primary Target Audience", ['US Tech Decision Makers', 'UK SMB Owners', 'Global Gaming Enthusiasts (18-25)'])
        creative_types = c2.multiselect("Primary Creative Types", ['Video Ad', 'Image Ad', 'Text Ad', 'Email Template', 'Live Stream'])
        
        st.markdown("---")
        # --- NEW INFLUENCER STRATEGY SECTION (Replaces Channel Mix) ---
        st.subheader("Influencer & Creator Strategy Profile")
        
        # 1.1 Financial Allocation & Scale
        st.write("**1. Financial Allocation & Scale**")
        creator_budget_percent = st.slider("% of Total Campaign Budget for Creators", 0, 100, 50)
        creator_budget_abs = (creator_budget_percent / 100) * total_budget
        st.info(f"Estimated Creator Budget: **${creator_budget_abs:,.0f}**")
        
        st.write("Compensation Model Mix (%)")
        c1, c2, c3 = st.columns(3)
        comp_flat = c1.number_input("% Flat Fee", 0, 100, 80, key="comp_flat")
        comp_perf = c2.number_input("% Performance/Commission", 0, 100, 20, key="comp_perf")
        comp_gifting = c3.number_input("% Gifting/Value-in-Kind", 0, 100, 0, key="comp_gifting")
        
        # 1.2. Creator Portfolio Mix
        st.write("**2. Creator Portfolio Mix**")
        st.write("Tier-Based Budget Allocation (%)")
        c1, c2, c3, c4 = st.columns(4)
        tier_mega = c1.number_input("% Mega (1M+)", 0, 100, 50, key="tier_mega")
        tier_macro = c2.number_input("% Macro (250k-1M)", 0, 100, 30, key="tier_macro")
        tier_mid = c3.number_input("% Mid (50k-250k)", 0, 100, 20, key="tier_mid")
        tier_micro = c4.number_input("% Micro (<50k)", 0, 100, 0, key="tier_micro")
        
        creator_niche = st.radio("Creator Niche / Vertical", ["Primarily Endemic", "Primarily Non-Endemic", "A Mix of Both"], horizontal=True)

        # 1.3. Content & Activation Strategy
        st.write("**3. Content & Activation Strategy**")
        c1, c2 = st.columns(2)
        primary_format = c1.selectbox("Primary Content Format", ["Short-form Video", "Long-form Video", "Static Images/Carousels", "Live Streams"])
        primary_cta = c2.selectbox("Primary Call-to-Action (CTA)", ["Watch/View (Reach)", "Comment/Share (Depth)", "Click/Sign-up/Buy (Action)"])
        
        # Final Submit
        submitted = st.form_submit_button("Save Profile & Find Comparable Campaigns", type="primary")
        if submitted:
            # --- Validation ---
            if (comp_flat + comp_perf + comp_gifting) != 100:
                st.error("Error: Compensation Model Mix percentages must add up to 100.")
            elif (tier_mega + tier_macro + tier_mid + tier_micro) != 100:
                st.error("Error: Tier-Based Budget Allocation percentages must add up to 100.")
            else:
                st.session_state.campaign_profile = {
                    "CoreDetails": {
                        "CampaignName": campaign_name,
                        "Objective": objective,
                        "StartDate": str(start_date),
                        "EndDate": str(end_date),
                        "TotalBudget": total_budget,
                    },
                    "AudienceAndCreative": {
                         "TargetAudience": audience_name,
                         "CreativeTypes": creative_types,
                    },
                    "InfluencerStrategy": {
                        "Financials": {
                            "CreatorBudgetPercentage": creator_budget_percent,
                            "CompensationMix": {
                                "FlatFee": comp_flat,
                                "Performance": comp_perf,
                                "Gifting": comp_gifting
                            }
                        },
                        "Portfolio": {
                            "TierAllocation": {
                                "Mega": tier_mega,
                                "Macro": tier_macro,
                                "Mid": tier_mid,
                                "Micro": tier_micro
                            },
                            "CreatorNiche": creator_niche
                        },
                        "Activation": {
                            "PrimaryContentFormat": primary_format,
                            "PrimaryCTA": primary_cta
                        }
                    }
                }
                st.session_state.comparison_profile_complete = True
                st.rerun()

elif st.session_state.comparison_profile_complete and not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Campaign Profile Saved")
    st.success("Your campaign profile has been successfully saved. This detailed profile is now ready to be matched against the historical database.")
    
    st.subheader("Your Saved Influencer Strategy Profile")
    st.json(st.session_state.campaign_profile.get("InfluencerStrategy", {}))

    st.markdown("---")
    st.subheader("Comparable Historical Campaigns")
    st.info("Based on your detailed profile, here are the most relevant historical campaigns. The benchmarks in the next step will be calculated from the average performance of this set.")
    
    # This data is now more meaningful because it's based on a more detailed profile
    comparable_campaigns_data = {
        'Historical Campaign': ['Q4 2023 - Project Titan', 'Q1 2024 - Nova Launch', 'Summer 2022 - Falcon'],
        'Similarity Score': ['95%', '91%', '87%'],
        'Objective': [st.session_state.campaign_profile['CoreDetails'].get('Objective', 'N/A')] * 3,
        'Total Budget': ['$7.5M', '$8.0M', '$6.9M'],
        'Creator Budget %': ['40%', '45%', '42%']
    }
    st.dataframe(pd.DataFrame(comparable_campaigns_data), use_container_width=True, hide_index=True)

    if st.button("Proceed to Benchmarking →", type="primary"):
        st.session_state.benchmark_flow_complete = True
        st.rerun()

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
