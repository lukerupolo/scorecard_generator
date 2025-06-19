import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List

# ... (get_ai_metric_categories and process_scorecard_data functions remain the same)
# These will be called after the benchmark step is complete.

def calculate_all_benchmarks(historical_data: Dict[str, pd.DataFrame]) -> (pd.DataFrame, Dict):
    """
    Takes a dictionary where keys are metrics and values are DataFrames of their historical data.
    Returns a summary DataFrame and a simple dictionary of {metric: proposed_benchmark}.
    """
    summary_rows = []
    proposed_benchmarks_dict = {}

    for metric, df in historical_data.items():
        # Ensure data is numeric and drop rows with missing values
        df['Baseline (7-day)'] = pd.to_numeric(df['Baseline (7-day)'], errors='coerce')
        df['Actual (7-day)'] = pd.to_numeric(df['Actual (7-day)'], errors='coerce')
        df.dropna(subset=['Baseline (7-day)', 'Actual (7-day)'], inplace=True)
        
        if df.empty:
            continue

        baselines = df['Baseline (7-day)']
        actuals = df['Actual (7-day)']

        # Perform the calculations exactly as specified
        avg_actual = actuals.mean()
        avg_baseline = baselines.mean()
        
        # Calculate uplift for each historical event
        df['Uplift %'] = ((df['Actual (7-day)'] - df['Baseline (7-day)']) / df['Baseline (7-day)']) * 100
        avg_uplift_pct = df['Uplift %'].mean()
        
        # Calculate the proposed benchmark
        proposed_benchmark = np.median([avg_actual, avg_baseline])

        # Append the summary row for the final table
        summary_rows.append({
            "Metric":                         metric,
            "Avg. Actuals (Event Periods)":   round(avg_actual, 2),
            "Baseline Method":                round(avg_baseline, 2),
            "Baseline Uplift Expect. (%)":    f"{avg_uplift_pct:.2f}%",
            "Proposed Benchmark":             round(proposed_benchmark, 2),
        })
        
        # Store the calculated benchmark for this metric
        proposed_benchmarks_dict[metric] = round(proposed_benchmark, 2)
    
    summary_df = pd.DataFrame(summary_rows)
    return summary_df, proposed_benchmarks_dict

def process_scorecard_data(config: dict) -> dict:
    # ... (This function remains unchanged)
    pass
