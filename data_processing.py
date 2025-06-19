import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# NEW: A dictionary to map metrics to their scorecard category.
# This makes it easy to add or change categories in the future.
METRIC_CATEGORIES = {
    # Reach
    "Social Conversation Volume": "Reach",
    "Video Views (VOD)": "Reach",
    "Views trailer": "Reach",
    "UGC Views": "Reach",
    "Social Impressions-Posts with trailer (FB, IG, X)": "Reach",
    "Social Impressions-All posts": "Reach",
    "Nb. press articles": "Reach",
    
    # Depth
    "Press UMV (unique monthly views)": "Depth",
    "Social Sentiment (Franchise)": "Depth",
    "Trailer avg % viewed (Youtube)": "Depth",
    "Email Open Rate (OR)": "Depth",
    "Email Click Through Rate (CTR)": "Depth",

    # Engagement / Action
    "Labs program sign-ups": "Engagement",
    "Discord channel sign-ups": "Engagement",
    "% Trailer views from Discord (Youtube)": "Engagement",
    "Labs sign up click-through Web": "Engagement",
    "Sessions": "Engagement",
    "DAU": "Engagement",
    "Hours Watched (Streams)": "Engagement"
}

def setup_levelup_headers(api_key: str) -> dict:
    return {"accept": "application/json", "X-API-KEY": api_key}

def generate_levelup_metrics_for_event(event: dict, headers: dict) -> dict:
    # ... (full implementation)
    return {}

def compute_three_month_average(headers: dict, brand_id: int, region: str, event_date: datetime, metric: str) -> float:
    # ... (full implementation)
    return 0.0

def fetch_social_mentions_count(*args, **kwargs) -> int:
    return np.random.randint(500, 2000)

def process_scorecard_data(config: dict) -> dict:
    """
    Main function to process all events and generate scorecards with categories.
    """
    sheets_dict = {}
    api_headers = setup_levelup_headers(config.get('levelup_api_key', '')) if config.get('levelup_api_key') else None

    for idx, ev in enumerate(config['events']):
        rows_for_event = []
        for metric_name in config['metrics']:
            # Get the category for the metric, defaulting to "Uncategorized"
            category = METRIC_CATEGORIES.get(metric_name, "Uncategorized")
            
            row = {
                "Category": category, # Add the new category
                "Metric": metric_name,
                "Baseline": np.random.randint(1000, 5000),
                "Actual": np.random.randint(1500, 7500),
                "3-Month Avg": "N/A"
            }
            rows_for_event.append(row)

        df_event = pd.DataFrame(rows_for_event)
        
        # Add a helper column for grouping and then drop it
        df_event['category_group'] = (df_event['Category'] != df_event['Category'].shift()).cumsum()
        
        # Set category to blank for all but the first row in each group
        df_event.loc[df_event.duplicated(subset=['category_group']), 'Category'] = ''
        
        df_event = df_event.drop(columns=['category_group'])

        sheets_dict[ev["name"][:28] or f"Event{idx+1}"] = df_event
        
    return sheets_dict
