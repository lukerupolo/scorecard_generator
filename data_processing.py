import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
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
    You are a marketing analyst. Categorize the following metrics into 'Reach', 'Depth', or 'Action'.
    - Reach: Did we hit sufficient scale?
    - Depth: Did we meaningfully engage?
    - Action: Did they take action?
    Metrics: {json.dumps(metrics)}
    Respond *only* with a single JSON object where keys are the metrics and values are their category.
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
    Generates the initial scorecard structure with blank columns for manual entry.
    It now correctly uses the pre-calculated benchmarks if they exist.
    """
    sheets_dict = {}
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected.")
        return {}
    
    ai_categories = get_ai_metric_categories(all_metrics, config.get('openai_api_key'))
    if not ai_categories: 
        st.warning("Could not get AI categories. Using 'Uncategorized'.")
    
    # Get the pre-calculated benchmarks from the config
    proposed_benchmarks = config.get('proposed_benchmarks', {})

    for idx, ev in enumerate(config.get('events', [])):
        rows_for_event = []
        for metric_name in config.get('metrics', []):
            category = ai_categories.get(metric_name, "Uncategorized")
            # Pre-fill the benchmark value if it exists, otherwise leave it blank
            benchmark_val = proposed_benchmarks.get(metric_name)
            
            # The initial table has blank values for the main columns
            row = {"Category": category, "Metric": metric_name, "Actuals": None, "Benchmark": benchmark_val, "% Difference": None}
            rows_for_event.append(row)

        df_event = pd.DataFrame(rows_for_event)
        if not df_event.empty:
            # This logic correctly blanks out repeated category names for a clean look
            df_event['category_group'] = (df_event['Category'] != df_event['Category'].shift()).cumsum()
            df_event.loc[df_event.duplicated(subset=['category_group']), 'Category'] = ''
            df_event = df_event.drop(columns=['category_group'])
        
        unique_key = f"{ev['name'][:24] or f'Event {idx+1}'} - {idx+1}"
        sheets_dict[unique_key] = df_event
        
    return sheets_dict

# ================================================================================
# Proposed Benchmark Calculation
# ================================================================================
def generate_proposed_benchmark(
    sheets_dict: Dict[str, pd.DataFrame],
    metrics:    List[str],
) -> pd.DataFrame:
    """
    Given a dict of historical event DataFrames, computes a proposed benchmark 
    for each metric using the user-specified logic.
    """
    benchmark_data = {m: {"actuals": [], "baselines": []} for m in metrics}

    # Pull each event's values from the historical data
    for name, df in sheets_dict.items():
        # Ensure data is numeric, coercing errors
        df['Actual (7-day)'] = pd.to_numeric(df['Actual (7-day)'], errors='coerce')
        df['Baseline (7-day)'] = pd.to_numeric(df['Baseline (7-day)'], errors='coerce')
        df = df.set_index("Metric")

        for m in metrics:
            if m not in df.index: continue
            
            row = df.loc[m]
            if pd.notna(row["Actual (7-day)"]):
                benchmark_data[m]["actuals"].append(row["Actual (7-day)"])
            if pd.notna(row["Baseline (7-day)"]):
                 benchmark_data[m]["baselines"].append(row["Baseline (7-day)"])

    # Build the output rows
    rows = []
    for m, vals in benchmark_data.items():
        actuals   = np.array(vals["actuals"])
        baselines = np.array(vals["baselines"])

        # Skip metrics that don't have enough historical data
        if len(actuals) == 0 or len(baselines) == 0:
            continue

        avg_actual   = actuals.mean()
        avg_baseline = baselines.mean()

        # Uplift per event: (Actual - Baseline) / Baseline
        # This creates a list of uplift percentages for each historical event
        uplifts = [
            ((a - b) / b) * 100 if b != 0 else 0.0
            for a, b in zip(actuals, baselines)
        ]
        avg_uplift_pct = float(np.mean(uplifts))

        # Proposed benchmark = median of the two means
        proposed_benchmark = float(np.median([avg_actual, avg_baseline]))

        rows.append({
            "Metric":                         m,
            "Avg. Actuals (Event Periods)":   round(avg_actual,   2),
            "Baseline Method":                round(avg_baseline, 2),
            "Baseline Uplift Expect. (%)":    f"{avg_uplift_pct:.2f}%",
            "Proposed Benchmark":             round(proposed_benchmark, 2),
        })

    return pd.DataFrame(rows)
