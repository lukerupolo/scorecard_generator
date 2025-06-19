import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta

# ================================================================================
# NEW: AI Metric Categorization Function
# ================================================================================
def get_ai_metric_categories(metrics: list) -> dict:
    """
    Uses the Gemini AI to categorize a list of metrics.
    Returns a dictionary mapping each metric to its category.
    """
    st.info("Asking AI to categorize metrics...")
    
    # Create the detailed prompt for the AI model
    prompt = f"""
    You are an expert marketing analyst. Your task is to categorize a list of metrics into one of three categories: 'Reach', 'Depth', or 'Action'.

    Here are the definitions:
    - **Reach**: Did we hit sufficient scale? (e.g., 'Video Views', 'Impressions', 'Social Conversation Volume')
    - **Depth**: Did we meaningfully engage? (e.g., 'Social Sentiment', 'Average % Viewed', 'Email Open Rate')
    - **Action**: Did they take action? (e.g., 'Labs program sign-ups', 'Discord channel sign-ups', 'Installs')

    Here is the list of metrics to categorize:
    {json.dumps(metrics)}

    Return your answer *only* as a JSON array of objects, where each object has a "metric" and a "category" key. The category must be one of "Reach", "Depth", or "Action".
    """

    # Define the expected JSON structure for the AI's response
    response_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "metric": {"type": "STRING"},
                "category": {"type": "STRING", "enum": ["Reach", "Depth", "Action"]}
            },
            "required": ["metric", "category"]
        }
    }
    
    # --- Gemini API Call for structured data ---
    try:
        api_key = "" # Handled by the execution environment
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema
            }
        }
        
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        
        result_json = response.json()
        
        # Extract the text part which contains the JSON string
        content_text = result_json['candidates'][0]['content']['parts'][0]['text']
        categorized_metrics = json.loads(content_text)
        
        # Convert the list of objects into a simple {metric: category} dictionary
        return {item['metric']: item['category'] for item in categorized_metrics}

    except requests.exceptions.RequestException as e:
        st.error(f"AI categorization failed due to a network error: {e}")
        return {}
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        st.error(f"AI categorization failed while parsing the response: {e}")
        return {}

# ================================================================================
# Data Processing and Scorecard Generation
# ================================================================================
def process_scorecard_data(config: dict) -> dict:
    """
    Main function to process all events and generate scorecards with AI-driven categories.
    """
    sheets_dict = {}
    
    # Get all unique metrics from the config to be categorized
    all_metrics = list(set(config.get('metrics', [])))
    
    # Call the AI function once to get all categories
    ai_categories = get_ai_metric_categories(all_metrics)
    if not ai_categories:
        st.error("Could not generate AI categories. Scorecards will not be created.")
        return {}

    for idx, ev in enumerate(config['events']):
        rows_for_event = []
        for metric_name in config['metrics']:
            # Get the category for the metric from the AI's response
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
        
        # Add a helper column for grouping and then drop it
        if not df_event.empty:
            df_event['category_group'] = (df_event['Category'] != df_event['Category'].shift()).cumsum()
            df_event.loc[df_event.duplicated(subset=['category_group']), 'Category'] = ''
            df_event = df_event.drop(columns=['category_group'])

        sheets_dict[ev["name"][:28] or f"Event{idx+1}"] = df_event
        
    return sheets_dict
