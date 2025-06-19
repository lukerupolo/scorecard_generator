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
    if not api_key: return {}
    if not metrics: return {}
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
# Scorecard and Benchmark Generation
# ================================================================================
def process_scorecard_data(config: dict) -> dict:
    """Generates the initial scorecard structure with blank columns for manual entry."""
    sheets_dict = {}
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected.")
        return {}
    
    ai_categories = get_ai_metric_categories(all_metrics, config.get('openai_api_key'))
    if not ai_categories: st.warning("Could not get AI categories. Using 'Uncategorized'.")
    
    for idx, ev in enumerate(config.get('events', [])):
        rows_for_event = []
        for metric_name in config.get('metrics', []):
            category = ai_categories.get(metric_name, "Uncategorized")
            # The initial table has blank values for the main columns
            row = {"Category": category, "Metric": metric_name, "Actuals": None, "Benchmark": None, "% Difference": None}
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

def generate_proposed_benchmark(
    sheets_dict: Dict[str, pd.DataFrame],
    metrics:    List[str],
) -> pd.DataFrame:
    """
    Given a dict of event DataFrames, computes a proposed benchmark for each metric.
    This version is adapted to use the 'Actuals' and 'Benchmark' columns.
    """
    # Initialize storage
    benchmark_data = {m: {"actuals": [], "benchmarks": []} for m in metrics}

    # Pull each event's values from the provided dictionary of DataFrames
    for name, df in sheets_dict.items():
        if "Benchmark" in name: continue
        
        # Ensure data is numeric, converting non-numeric values to NaN
        df['Actuals'] = pd.to_numeric(df['Actuals'], errors='coerce')
        df['Benchmark'] = pd.to_numeric(df['Benchmark'], errors='coerce')
        df = df.set_index("Metric")

        for m in metrics:
            if m not in df.index: continue
            
            row = df.loc[m]
            # Add values only if they are not null/NaN
            if pd.notna(row["Actuals"]):
                benchmark_data[m]["actuals"].append(row["Actuals"])
            if pd.notna(row["Benchmark"]):
                 benchmark_data[m]["benchmarks"].append(row["Benchmark"])

    # Build the output rows
    rows = []
    for m, vals in benchmark_data.items():
        actuals   = np.array(vals["actuals"])
        benchmarks = np.array(vals["benchmarks"])

        # Skip metrics that don't have enough data
        if len(actuals) == 0 or len(benchmarks) == 0:
            continue

        avg_actual   = actuals.mean()
        avg_benchmark = benchmarks.mean()

        # Uplift per event: (Actual - Benchmark) / Benchmark
        uplifts = [
            (a - b) / b * 100 if b != 0 else 0.0
            for a, b in zip(actuals, benchmarks)
        ]
        avg_uplift_pct = float(np.mean(uplifts))

        # Proposed benchmark = median of the two means
        proposed_benchmark = float(np.median([avg_actual, avg_benchmark]))

        rows.append({
            "Metric":                         m,
            "Avg. Actuals (Event Periods)":   round(avg_actual,   2),
            "Avg. Benchmark (Event Periods)": round(avg_benchmark, 2),
            "Avg. Uplift (%)":                f"{avg_uplift_pct:.1f}%",
            "Proposed Benchmark":             round(proposed_benchmark, 2),
        })

    return pd.DataFrame(rows)
