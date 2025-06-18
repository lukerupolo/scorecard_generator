import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

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
    Main function to process all events and generate scorecards.
    Returns a dictionary of DataFrames.
    """
    sheets_dict = {}
    api_headers = setup_levelup_headers(config.get('levelup_api_key', '')) if config.get('levelup_api_key') else None

    for idx, ev in enumerate(config['events']):
        # --- Dummy Data Generation for Demonstration ---
        rows_for_event = []
        for metric_name in config['metrics']:
            row = {
                "Metric": metric_name,
                "Baseline": np.random.randint(1000, 5000),
                "Actual": np.random.randint(1500, 7500),
                "3-Month Avg": "N/A"
            }
            rows_for_event.append(row)
        # --- End Dummy Data ---

        df_event = pd.DataFrame(rows_for_event).set_index("Metric").reset_index()
        sheets_dict[ev["name"][:28] or f"Event{idx+1}"] = df_event
        
    return sheets_dict
