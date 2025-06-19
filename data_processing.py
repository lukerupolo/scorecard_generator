import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List

# ... (get_ai_metric_categories function remains the same)

def process_scorecard_data(config: dict) -> dict:
    """
    Generates the initial scorecard structure, pre-filling benchmarks if they were calculated.
    """
    sheets_dict = {}
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected.")
        return {}
    
    ai_categories = {} # get_ai_metric_categories(all_metrics, config.get('openai_api_key'))
    if not ai_categories: st.warning("AI Categorization skipped. Using 'Uncategorized'.")
    
    # Get the pre-calculated benchmarks from the config
    proposed_benchmarks = config.get('proposed_benchmarks', {})

    for idx, ev in enumerate(config.get('events', [])):
        rows_for_event = []
        for metric_name in config.get('metrics', []):
            category = ai_categories.get(metric_name, "Uncategorized")
            # Pre-fill the benchmark value if it exists, otherwise leave it blank
            benchmark_val = proposed_benchmarks.get(metric_name)
            
            row = {"Category": category, "Metric": metric_name, "Actuals": None, "Benchmark": benchmark_val, "% Difference": None}
            rows_for_event.append(row)

        df_event = pd.DataFrame(rows_for_event)
        if not df_event.empty:
            df_event['category_group'] = (df_event['Category'] != df_event['Category'].shift()).cumsum()
            df_event.loc[df_event.duplicated(subset=['category_group']), 'Category'] = ''
            df_event = df_event.drop(columns=['category_group'])
        
        unique_key = f"{ev['name'][:24] or f'Event {idx+1}'} - {idx+1}"
        sheets_dict[unique_key] = df_event
        
    return sheets_dict

def calculate_benchmark_summary(df_input: pd.DataFrame) -> Dict:
    """
    Takes a DataFrame with 'Baseline (7-day)' and 'Actual (7-day)' columns
    and calculates the four summary metrics.
    """
    # Ensure columns are numeric, coercing errors
    df_input['Baseline (7-day)'] = pd.to_numeric(df_input['Baseline (7-day)'], errors='coerce')
    df_input['Actual (7-day)'] = pd.to_numeric(df_input['Actual (7-day)'], errors='coerce')
    
    # Drop rows where data is missing
    df_input.dropna(subset=['Baseline (7-day)', 'Actual (7-day)'], inplace=True)
    
    if df_input.empty:
        return {}

    baselines = df_input['Baseline (7-day)']
    actuals = df_input['Actual (7-day)']

    # Calculate uplift for each row
    uplifts = (actuals - baselines) / baselines * 100
    
    # Calculate summary metrics
    avg_actual = actuals.mean()
    avg_baseline = baselines.mean()
    avg_uplift_pct = uplifts.mean()
    proposed_benchmark = np.median([avg_actual, avg_baseline])

    return {
        "Avg. Actuals": round(avg_actual, 2),
        "Avg. Baseline": round(avg_baseline, 2),
        "Baseline Uplift Expect. (%)": f"{avg_uplift_pct:.2f}%",
        "Proposed Benchmark": round(proposed_benchmark, 2),
    }

