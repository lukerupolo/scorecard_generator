import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from typing import Dict, List

# ================================================================================
# AI Metric Categorization using OpenAI API
# ================================================================================
def get_ai_metric_categories(metrics: list, api_key: str) -> dict:
    """Uses the OpenAI API to categorize a list of metrics."""
    if not api_key:
        st.error("OpenAI API key is required for AI categorization.")
        return {}
    if not metrics:
        return {}
        
    st.info("Asking AI to categorize metrics...")
    prompt = f"""
    You are an expert marketing analyst. Your task is to categorize a list of metrics into one of three categories: 'Reach', 'Depth', or 'Action'.

    Here are the definitions:
    - **Reach**: Did we hit sufficient scale? (e.g., 'Video Views', 'Impressions', 'Social Conversation Volume')
    - **Depth**: Did we meaningfully engage? (e.g., 'Social Sentiment', 'Average % Viewed', 'Email Open Rate')
    - **Action**: Did they take action? (e.g., 'Labs program sign-ups', 'Discord channel sign-ups', 'Installs')

    Here is the list of metrics to categorize:
    {json.dumps(metrics)}

    Respond *only* with a single JSON object where keys are the metrics and values are their category. The category must be one of "Reach", "Depth", or "Action".
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "gpt-4-turbo", "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}, "temperature": 0.1}
    
    try:
        api_url = "https://api.openai.com/v1/chat/completions"
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return json.loads(response.json()['choices'][0]['message']['content'])
    except Exception as e:
        st.error(f"AI categorization failed: {e}")
        return {}

# ================================================================================
# Scorecard Generation
# ================================================================================
def process_scorecard_data(config: dict) -> dict:
    """
    Generates the initial scorecard structure, with AI-driven categories, 
    pre-filling benchmarks if they were calculated.
    """
    sheets_dict = {}
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected.")
        return {}
    
    # --- FIXED: Re-enabled the AI categorization call ---
    ai_categories = get_ai_metric_categories(all_metrics, config.get('openai_api_key'))
    if not ai_categories: 
        st.warning("Could not get AI categories. Using 'Uncategorized'.")
    
    proposed_benchmarks = config.get('proposed_benchmarks', {})

    rows_for_event = []
    # Sort metrics based on the desired category order
    category_order = ["Reach", "Depth", "Action", "Uncategorized"]
    sorted_metrics = sorted(all_metrics, key=lambda x: category_order.index(ai_categories.get(x, "Uncategorized")))

    for metric_name in sorted_metrics:
        category = ai_categories.get(metric_name, "Uncategorized")
        benchmark_val = proposed_benchmarks.get(metric_name)
        row = {"Category": category, "Metric": metric_name, "Actuals": None, "Benchmark": benchmark_val, "% Difference": None}
        rows_for_event.append(row)
    
    df_event = pd.DataFrame(rows_for_event)
    if not df_event.empty:
        # This logic correctly blanks out repeated category names for a clean look
        df_event['category_group'] = (df_event['Category'] != df_event['Category'].shift()).cumsum()
        df_event.loc[df_event.duplicated(subset=['category_group']), 'Category'] = ''
        df_event = df_event.drop(columns=['category_group'])
    
    # The app now only generates one final scorecard.
    sheets_dict["Final Scorecard"] = df_event
    return sheets_dict

# ================================================================================
# Benchmark Calculation
# ================================================================================
def calculate_all_benchmarks(historical_inputs: Dict[str, Dict]) -> (pd.DataFrame, Dict):
    """
    Takes a dictionary where keys are metrics and values contain their historical data
    and a user-provided 3-month average. Returns a summary DataFrame and a simple
    dictionary of {metric: proposed_benchmark}.
    """
    summary_rows = []
    proposed_benchmarks_dict = {}

    for metric, inputs in historical_inputs.items():
        df = inputs['historical_df']
        three_month_avg_baseline = inputs['three_month_avg']

        df['Baseline (7-day)'] = pd.to_numeric(df['Baseline (7-day)'], errors='coerce')
        df['Actual (7-day)'] = pd.to_numeric(df['Actual (7-day)'], errors='coerce')
        df.dropna(subset=['Baseline (7-day)', 'Actual (7-day)'], inplace=True)
        
        if df.empty: continue

        baselines = df['Baseline (7-day)']; actuals = df['Actual (7-day)']
        avg_actual_historical = actuals.mean()
        uplifts = np.where(baselines != 0, (actuals - baselines) / baselines * 100, 0.0)
        avg_uplift_pct = uplifts.mean()
        proposed_benchmark = three_month_avg_baseline * (1 + (avg_uplift_pct / 100))

        summary_rows.append({
            "Metric":                         metric,
            "Avg. Actuals (Historical)":      round(avg_actual_historical, 2),
            "Baseline Method (User Input)":   round(three_month_avg_baseline, 2),
            "Baseline Uplift Expect. (%)":    f"{avg_uplift_pct:.2f}%",
            "Proposed Benchmark":             round(proposed_benchmark, 2),
        })
        proposed_benchmarks_dict[metric] = round(proposed_benchmark, 2)
    
    if not summary_rows:
        st.warning("No valid data entered to calculate benchmarks.")
        return pd.DataFrame(), {}
        
    return pd.DataFrame(summary_rows), proposed_benchmarks_dict
