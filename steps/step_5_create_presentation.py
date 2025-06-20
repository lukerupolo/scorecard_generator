import streamlit as st
from style import STYLE_PRESETS
from powerpoint import create_presentation

def render():
    if not st.session_state.get('show_ppt_creator'):
        return

    st.markdown("---")
    st.header("Step 5: Create Presentation")

    if st.session_state.get("presentation_buffer"):
        st.download_button(
            label="✅ Download Your Presentation!", 
            data=st.session_state.presentation_buffer, 
            file_name="game_scorecard_presentation.pptx", 
            use_container_width=True
        )

    with st.form("ppt_form"):
        st.subheader("Presentation Style & Details")

        if st.session_state.saved_moments:
            options = list(st.session_state.saved_moments.keys())
            selected_moments = st.multiselect(
                "Select which saved moments to include in the presentation:",
                options=options,
                default=options
            )
        else:
            st.warning("No scorecard moments saved yet. Please save at least one moment above.")
            selected_moments = []

        col1, col2 = st.columns(2)
        style_name = col1.radio("Select Style Preset:", options=list(STYLE_PRESETS.keys()), horizontal=True)
        region_prompt = col2.text_input("Region for AI Background Image", "Brazil")
        ppt_title = st.text_input("Presentation Title", "Game Scorecard")
        ppt_subtitle = st.text_input("Presentation Subtitle", "A detailed analysis")

        submitted = st.form_submit_button("Generate Presentation", use_container_width=True)

        if submitted:
            if not selected_moments:
                st.error("Please select at least one saved moment to include.")
            else:
                with st.spinner(f"Building presentation with {style_name} style..."):
                    data = {name: st.session_state.saved_moments[name] for name in selected_moments}
                    style = STYLE_PRESETS[style_name]
                    buffer = create_presentation(
                        title=ppt_title,
                        subtitle=ppt_subtitle,
                        scorecard_moments=selected_moments,
                        sheets_dict=data,
                        style_guide=style,
                        region_prompt=region_prompt,
                        openai_api_key=st.session_state.openai_api_key 
                    )
                    st.session_state["presentation_buffer"] = buffer
                    st.rerun()
