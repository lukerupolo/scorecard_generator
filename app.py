import streamlit as st
from io import BytesIO
from datetime import datetime
import pandas as pd

# --- Local Imports from our other files ---
from style import STYLE_PRESETS
from ui import render_sidebar
from data_processing import process_scorecard_data, calculate_all_benchmarks, get_ai_metric_categories
from powerpoint import create_presentation
from excel import create_excel_workbook
# The strategy.py file is no longer used in this new workflow
# from strategy import generate_strategy

# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

APP_VERSION = "5.0.0" # Major version change for new comparison logic

if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    api_key = st.session_state.get('openai_api_key')
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state.app_version = APP_VERSION
    st.session_state.api_key_entered = True if api_key else False
    st.session_state.openai_api_key = api_key
    st.session_state.metrics_confirmed = False
    # This state is now for the new comparison profile
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
    # State to hold the new detailed campaign profile
    st.session_state.campaign_profile = {}
    # State to hold the selected channels
    if 'selected_channels' not in st.session_state:
        st.session_state.selected_channels = []


st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar()

# ================================================================================
# Step 0: API Key Entry
# ================================================================================
if not st.session_state.api_key_entered:
    st.header("Step 0: Enter Your OpenAI API Key")
    # ... (code for API key entry is unchanged)

# ================================================================================
# Step 1: Metric Selection
# ================================================================================
elif not st.session_state.metrics_confirmed:
    st.header("Step 1: Select Your Core Scorecard Metrics (RDA)")
    # ... (code for Metric Selection is unchanged)

# ================================================================================
# NEW Step 2: Define Campaign Profile for Comparison
# ================================================================================
elif not st.session_state.comparison_profile_complete:
    st.header("Step 2: Define Campaign Profile for Comparison")
    st.info("Provide the details of your campaign. This profile will be used to find the most similar historical campaigns to generate relevant benchmarks.")

    with st.form("campaign_profile_form"):
        st.subheader("Core Campaign Details")
        
        # --- Based on the "Campaigns" table schema ---
        campaign_name = st.text_input("Campaign Name")
        objective = st.selectbox("Campaign Objective", ['Brand Awareness', 'Lead Generation', 'Sales', 'Audience Engagement'])
        
        c1, c2 = st.columns(2)
        start_date = c1.date_input("Start Date")
        end_date = c2.date_input("End Date")
        total_budget = st.number_input("Total Budget ($)", min_value=0, format="%d")

        st.markdown("---")

        # --- Based on the "Audiences" table schema ---
        st.subheader("Target Audience")
        audience_name = st.selectbox("Primary Target Audience", ['US Tech Decision Makers', 'UK SMB Owners', 'Global Gaming Enthusiasts (18-25)'])
        
        st.markdown("---")

        # --- Based on the "Creatives" table schema ---
        st.subheader("Primary Creative Types")
        creative_types = st.multiselect("Select the primary creative types used:", ['Video Ad', 'Image Ad', 'Text Ad', 'Email Template', 'Live Stream'])
        
        st.markdown("---")
        
        # --- Based on the "Channels" and "Campaign_Channels" schema ---
        st.subheader("Channel Mix & Budget Allocation")
        
        # Use a callback to update the selected channels for dynamic budget allocation fields
        def update_channels():
            st.session_state.selected_channels = st.session_state.channel_multiselect

        all_channels = ['Facebook Ads', 'Google Search', 'Email Marketing', 'LinkedIn Ads', 'TikTok Ads', 'Organic Social', 'Influencer Marketing']
        
        st.multiselect(
            "Select all channels used in this campaign:",
            options=all_channels,
            key="channel_multiselect",
            on_change=update_channels,
            default=st.session_state.selected_channels
        )

        # Dynamically create budget allocation fields for selected channels
        channel_budgets = {}
        if st.session_state.selected_channels:
            st.write("Enter the budget allocated to each selected channel:")
            for channel in st.session_state.selected_channels:
                # Use a key that is unique to the channel
                channel_budgets[channel] = st.number_input(f"Budget for {channel} ($)", min_value=0, key=f"budget_{channel}", format="%d")

        submitted = st.form_submit_button("Save Profile & Find Comparable Campaigns", type="primary")
        if submitted:
            # On submission, save the entire profile to session state
            st.session_state.campaign_profile = {
                "CampaignName": campaign_name,
                "Objective": objective,
                "StartDate": str(start_date),
                "EndDate": str(end_date),
                "TotalBudget": total_budget,
                "TargetAudience": audience_name,
                "CreativeTypes": creative_types,
                "Channels": channel_budgets # This now contains both channel name and budget
            }
            st.session_state.comparison_profile_complete = True
            st.rerun()

# This block executes after the profile is submitted to show the user what was saved
# and to simulate finding comparable campaigns.
elif st.session_state.comparison_profile_complete and not st.session_state.benchmark_flow_complete:
    st.header("Step 2: Campaign Profile Saved")
    st.success("Your campaign profile has been successfully saved.")
    
    st.subheader("Your Saved Profile")
    st.json(st.session_state.campaign_profile)

    st.markdown("---")
    st.subheader("Comparable Historical Campaigns")
    st.info("Based on your profile, here are the most relevant historical campaigns. The benchmarks in the next step will be calculated from the average performance of this set.")
    
    # This is a placeholder for where the app would display the results of the database query
    # In a real app, this DataFrame would be generated by a backend function that queries
    # the historical database based on the st.session_state.campaign_profile
    
    comparable_campaigns_data = {
        'Historical Campaign': ['Q4 2023 - Project Titan', 'Summer 2023 - Ignite', 'Q1 2024 - Nova Launch'],
        'Similarity Score': ['92%', '88%', '85%'],
        'Objective': [st.session_state.campaign_profile['Objective']] * 3,
        'Total Budget': ['$1,100,000', '$950,000', '$1,250,000'],
        'Target Audience': [st.session_state.campaign_profile['TargetAudience']] * 3,
    }
    st.dataframe(pd.DataFrame(comparable_campaigns_data), use_container_width=True)

    if st.button("Proceed to Benchmarking →", type="primary"):
        st.session_state.benchmark_flow_complete = True
        st.rerun()

# ================================================================================
# Step 3: Optional Benchmark Calculation (UI remains, logic context changes)
# ================================================================================
elif not st.session_state.benchmark_flow_complete:
     st.header("Step 3: Auto-Generate Benchmarks")
     st.info("These proposed benchmarks are calculated from the average performance of the comparable campaigns identified in the previous step.")
     # ... UI for showing and confirming benchmarks would go here ...
     # This step is now simplified as the context is clear.
     if st.button("Proceed to Scorecard Creation →", type="primary"):
            st.session_state.benchmark_flow_complete = True # We are skipping the detailed historical entry for now
            st.rerun()

# ================================================================================
# Step 4 & 5 - Main App Logic (Largely unchanged)
# ================================================================================
else:
    # ... The rest of the app (Steps 4 and 5) remains the same ...
    app_config = {
        'openai_api_key': st.session_state.openai_api_key, 
        'metrics': st.session_state.metrics,
        'proposed_benchmarks': st.session_state.get('proposed_benchmarks'),
        'avg_actuals': st.session_state.get('avg_actuals')
    }
    
    st.header("Step 4: Build & Save Scorecard Moments")
    # ... The rest of the application code ...
    
    if st.session_state.sheets_dict is None:
        st.session_state.sheets_dict = process_scorecard_data(app_config)

    st.info("Fill in the 'Actuals' and 'Benchmark' columns, give the scorecard a name, and save it as a 'moment'. You can create multiple moments.")
    
    current_scorecard_df = next(iter(st.session_state.sheets_dict.values()), None)

    if current_scorecard_df is not None:
        edited_df = st.data_editor(current_scorecard_df, key="moment_editor", use_container_width=True, num_rows="dynamic")
        
        edited_df['Actuals'] = pd.to_numeric(edited_df['Actuals'], errors='coerce')
        edited_df['Benchmark'] = pd.to_numeric(edited_df['Benchmark'], errors='coerce')
        edited_df['% Difference'] = ((edited_df['Actuals'] - edited_df['Benchmark']) / edited_df['Benchmark'].replace(0, pd.NA)).apply(lambda x: f"{x:.1%}" if pd.notna(x) else None)
        
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
        if st.session_state.benchmark_df is not None and not st.session_state.benchmark_df.empty:
            with st.expander("View Benchmark Calculation Summary"):
                st.dataframe(st.session_state.benchmark_df.set_index("Metric"), use_container_width=True)
        
        for name, df in st.session_state.saved_moments.items():
            with st.expander(f"View Moment: {name}"):
                st.dataframe(df, use_container_width=True)
        st.session_state.show_ppt_creator = True

    # --- Step 5: Create Presentation ---
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
                st.warning("No scorecard moments saved yet. Please save at least one moment above.")
                selected_moments = []

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
