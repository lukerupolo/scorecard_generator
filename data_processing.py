import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta

# ================================================================================
# AI Metric Categorization using OpenAI API
# ================================================================================
def get_ai_metric_categories(metrics: list, api_key: str) -> dict:
    """
    Uses the OpenAI API to categorize a list of metrics.
    Returns a dictionary mapping each metric to its category.
    """
    if not api_key:
        st.error("OpenAI API key is required for AI categorization. Please enter it in the sidebar.")
        return {}

    if not metrics:
        return {}

    st.info("Asking AI to categorize metrics...")
    
    prompt = f"""
    You are a marketing analyst. Categorize the following metrics into 'Reach', 'Depth', or 'Action'.
    - Reach: Did we hit sufficient scale?
    - Depth: Did we meaningfully engage?
    - Action: Did they take action?

    Metrics: {json.dumps(metrics)}

    Respond *only* with a single JSON object where keys are the metrics and values are their category.
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    
    try:
        api_url = "https://api.openai.com/v1/chat/completions"
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result_json = response.json()
        categorized_metrics = json.loads(result_json['choices'][0]['message']['content'])
        
        return categorized_metrics

    except requests.exceptions.RequestException as e:
        st.error(f"AI categorization failed due to a network or API error: {e}")
        return {}
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        st.error(f"AI categorization failed while parsing the OpenAI response: {e}")
        return {}

# ================================================================================
# Data Processing and Scorecard Generation
# ================================================================================
def process_scorecard_data(config: dict) -> dict:
    """
    Main function to process all events and generate scorecards with AI-driven categories.
    """
    sheets_dict = {}
    
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected. Please select at least one metric in the sidebar.")
        return {}
        
    openai_api_key = config.get('openai_api_key')
    ai_categories = get_ai_metric_categories(all_metrics, openai_api_key)
    
    if not ai_categories:
        st.warning("Could not generate AI categories. Using 'Uncategorized'.")
    
    # --- FIXED: This loop now correctly generates a separate scorecard for each event ---
    for idx, ev in enumerate(config['events']):
        rows_for_event = []
        for metric_name in config['metrics']:
            category = ai_categories.get(metric_name, "Uncategorized")
            
            row = {
                "Category": category,
                "Metric": metric_name,
                "Baseline": np.random.randint(1000, 5000),
                "Actual": np.random.randint(1500, 7500),
                "3-Month Avg": "N/A"
            }
            rows_for_event.append(row)

        df_event = pd.DataFrame(rows_for_event)
        
        if not df_event.empty:
            df_event['category_group'] = (df_event['Category'] != df_event['Category'].shift()).cumsum()
            df_event.loc[df_event.duplicated(subset=['category_group']), 'Category'] = ''
            df_event = df_event.drop(columns=['category_group'])

        # Use the event's name as the key to ensure a unique entry for each scorecard
        sheets_dict[ev["name"][:28] or f"Event {idx+1}"] = df_event
        
    return sheets_dict
