import streamlit as st
from datetime import datetime

def render_sidebar():
    """Renders the sidebar UI and returns a dictionary of configurations."""
    config = {}
    with st.sidebar:
        st.markdown("## ⚙️ App Configuration")
        
        # This key is required for AI categorization in Step 1
        config['openai_api_key'] = st.text_input(
            "🔑 OpenAI API Key", 
            type="password",
            help="Required for AI-powered metric categorization and image generation."
        )

        st.markdown("---")
        
        st.markdown("## 📅 Event Configuration")
        game_options = {"EA Sports FC25": 3136, "FIFA 25": 3140, "Madden NFL 25": 3150, "NHL 25": 3160}
        region_options = ["US", "GB", "AU", "CA", "FR", "DE", "JP", "KR", "TH", "Other"]
        n_events = st.number_input("Number of events", min_value=1, max_value=10, value=1, step=1)
        
        events = []
        for i in range(n_events):
            st.markdown(f"### Event {i+1}")
            selected_game = st.selectbox(f"🎮 Select Game (Event {i+1})", options=list(game_options.keys()), key=f"game_{i}")
            name = st.text_input(f"🔤 Event Label (Event {i+1})", key=f"name_{i}", value=selected_game)
            date = st.date_input(f"📅 Date (Event {i+1})", key=f"date_{i}")
            selected_region = st.selectbox(f"🌐 Select Region (Event {i+1})", options=region_options, key=f"region_select_{i}")
            region = st.text_input(f"Enter custom region code (Event {i+1})", key=f"region_custom_{i}") or selected_region if selected_region == "Other" else selected_region
            events.append({"name": name, "date": datetime.combine(date, datetime.min.time()), "brandId": int(game_options[selected_game]), "brandName": selected_game, "region": region})
        config['events'] = events

        st.markdown("## 🎛️ Metric Selection")
        predefined_metrics = ["Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions"]
        metrics = st.multiselect("Select metrics:", options=predefined_metrics, default=["Video Views (VOD)", "Hours Watched (Streams)"], key="metrics_multiselect")
        if custom_metric := st.text_input("✍️ Add Custom Metric", key="custom_metric_input"): metrics.append(custom_metric)
        config['metrics'] = metrics
            
    return config
