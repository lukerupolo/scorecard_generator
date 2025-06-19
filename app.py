import streamlit as st
from io import BytesIO
from datetime import datetime

# --- Local Imports from our other files ---
from style import STYLE_PRESETS 
from ui import render_sidebar
from data_processing import process_scorecard_data, get_ai_metric_explanations
from powerpoint import create_presentation
from excel import create_excel_workbook

# ================================================================================
# 1) App State Initialization
# ================================================================================
st.set_page_config(page_title="Event Marketing Scorecard", layout="wide")

# Initialize session state keys
for key in ['api_key_entered', 'metrics_confirmed', 'scorecard_ready', 'show_ppt_creator']:
    if key not in st.session_state: st.session_state[key] = False
for key in ['openai_api_key', 'metrics', 'sheets_dict', 'presentation_buffer', 'metric_explanations']:
     if key not in st.session_state: st.session_state[key] = None

st.title("Event Marketing Scorecard & Presentation Generator")
render_sidebar() # Renders the (now empty) sidebar

# ================================================================================
# Step 0: API Key Entry
# ================================================================================
if not st.session_state.api_key_entered:
    st.header("Step 0: Enter Your OpenAI API Key")
    with st.form("api_key_form"):
        api_key_input = st.text_input("🔑 OpenAI API Key", type="password")
        submitted = st.form_submit_button("Submit API Key")
        if submitted:
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
    st.header("Step 1: Metric Selection")
    with st.form("metrics_form"):
        predefined_metrics = ["Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions"]
        selected_metrics = st.multiselect("Select metrics:", options=predefined_metrics, default=["Video Views (VOD)", "Hours Watched (Streams)"])
        if custom_metric := st.text_input("✍️ Add Custom Metric"):
            selected_metrics.append(custom_metric)
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        # Button to get AI explanations
        if col1.form_submit_button("🤖 Get AI Explanation for Selected Metrics"):
             with st.spinner("Asking AI for explanations..."):
                explanations = get_ai_metric_explanations(selected_metrics, st.session_state.openai_api_key)
                st.session_state.metric_explanations = explanations
        
        # Button to confirm and move to the next step
        if col2.form_submit_button("Confirm Metrics & Proceed →", type="primary"):
            st.session_state.metrics = selected_metrics
            st.session_state.metrics_confirmed = True
            st.rerun()
            
    # Display AI explanations if they exist
    if st.session_state.metric_explanations:
        st.info("### AI Metric Explanations")
        for metric, explanation in st.session_state.metric_explanations.items():
            st.markdown(f"**{metric}:** {explanation}")
# ================================================================================
# Steps 2, 3, 4 - Main App Logic
# ================================================================================
else:
    app_config = {
        'openai_api_key': st.session_state.openai_api_key,
        'metrics': st.session_state.metrics
    }

    st.header("Step 2: Configure Events & Generate Data")
    with st.expander("Configure Events", expanded=True):
        game_options = {"EA Sports FC25": 3136, "FIFA 25": 3140, "Madden NFL 25": 3150, "NHL 25": 3160}
        region_options = ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR", "TH", "Other"]
        n_events = st.number_input("Number of events", min_value=1, max_value=10, value=1, step=1)
        
        events = []
        event_cols = st.columns(n_events)
        for i in range(n_events):
            with event_cols[i]:
                st.markdown(f"##### Event {i+1}")
                selected_game = st.selectbox(f"Game", options=list(game_options.keys()), key=f"game_{i}")
                name = st.text_input(f"Label", key=f"name_{i}", value=selected_game)
                date = st.date_input(f"Date", key=f"date_{i}")
                selected_region = st.selectbox(f"Region", options=region_options, key=f"region_select_{i}")
                region = st.text_input(f"Custom Region", key=f"region_custom_{i}") or selected_region if selected_region == "Other" else selected_region
                events.append({"name": name, "date": datetime.combine(date, datetime.min.time()), "brandId": int(game_options[selected_game]), "brandName": selected_game, "region": region})
    app_config['events'] = events

    if st.button("✅ Generate Scorecard Data", use_container_width=True, type="primary"):
        with st.spinner("Categorizing metrics with AI and building scorecards..."):
            sheets_dict = process_scorecard_data(app_config)
            st.session_state["sheets_dict"] = sheets_dict
            st.session_state["scorecard_ready"] = True
        st.rerun()

    if st.session_state.scorecard_ready and st.session_state.sheets_dict:
        st.markdown("---"); st.header("Step 3: Review & Edit Data")
        for name, df in st.session_state.sheets_dict.items():
            st.markdown(f"#### Edit Scorecard: {name}")
            edited_df = st.data_editor(df, key=f"editor_{name}", use_container_width=True, num_rows="dynamic", column_config={"Category": st.column_config.TextColumn(width="medium"), "Baseline": st.column_config.NumberColumn(format="%d"), "Actual": st.column_config.NumberColumn(format="%d")})
            st.session_state.sheets_dict[name] = edited_df
        st.markdown("---")
        col1, col2 = st.columns(2)
        if col1.button("🎯 Generate Proposed Benchmark", use_container_width=True): st.info("Benchmark logic would run here.")
        if st.session_state.sheets_dict:
            excel_buffer = create_excel_workbook(st.session_state.sheets_dict)
            col2.download_button(label="📥 Download as Excel Workbook", data=excel_buffer, file_name="full_scorecard.xlsx", use_container_width=True)
        st.markdown("---")
        st.session_state['show_ppt_creator'] = True

    if st.session_state.get('show_ppt_creator'):
        st.header("Step 4: Create Your Presentation")
        if st.session_state.get("presentation_buffer"):
            st.download_button(label="✅ Download Your Presentation!", data=st.session_state.presentation_buffer, file_name="game_scorecard_presentation.pptx", use_container_width=True)
        with st.form("ppt_form"):
            st.subheader("Presentation Style & Details")
            col1, col2 = st.columns(2)
            selected_style_name = col1.radio("Select Style Preset:", options=list(STYLE_PRESETS.keys()), horizontal=True)
            image_region_prompt = col2.text_input("Region for AI Background Image", "Brazil")
            ppt_title = st.text_input("Presentation Title", "Game Scorecard")
            ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")
            moments_input = st.text_area("Scorecard Moments (one per line)", "Pre-Reveal\nLaunch", height=100)
            submitted = st.form_submit_button("Generate Presentation", use_container_width=True)
            if submitted:
                if not st.session_state.get("sheets_dict"):
                    st.error("Please generate scorecard data first.")
                else:
                    with st.spinner(f"Building presentation..."):
                        style_guide = STYLE_PRESETS[selected_style_name]
                        scorecard_moments = [moment.strip() for moment in moments_input.split('\n') if moment.strip()]
                        ppt_buffer = create_presentation(title=ppt_title, subtitle=ppt_subtitle, scorecard_moments=scorecard_moments, sheets_dict=st.session_state.sheets_dict, style_guide=style_guide, region_prompt=image_region_prompt, openai_api_key=st.session_state.openai_api_key)
                        st.session_state["presentation_buffer"] = ppt_buffer
                        st.rerun()
