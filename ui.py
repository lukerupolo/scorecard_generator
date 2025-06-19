import streamlit as st
from datetime import datetime

def render_sidebar():
    """Renders the sidebar UI for global settings and returns a dictionary."""
    config = {}
    with st.sidebar:
        st.markdown("## ⚙️ App Configuration")
        
        # API key is a global setting, so it stays in the sidebar.
        config['openai_api_key'] = st.text_input(
            "🔑 OpenAI API Key", 
            type="password",
            help="Required for AI-powered metric categorization and image generation."
        )

        st.markdown("---")
        
        # Metric selection is also a global setting.
        st.markdown("## 🎛️ Metric Selection")
        predefined_metrics = [
            "Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Sessions", 
            "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", 
            "Conversions", "Social Conversation Volume", "UGC Views"
        ]
        metrics = st.multiselect(
            "Select metrics:", 
            options=predefined_metrics, 
            default=["Video Views (VOD)", "Hours Watched (Streams)"], 
            key="metrics_multiselect"
        )
        if custom_metric := st.text_input("✍️ Add Custom Metric", key="custom_metric_input"):
            metrics.append(custom_metric)
        config['metrics'] = metrics
            
    return config
