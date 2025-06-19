import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List

# --- (AI Categorization and other functions can remain here) ---

def process_scorecard_data(config: dict) -> dict:
    """
    Generates the initial scorecard structure, pre-filling benchmarks if they were calculated.
    """
    sheets_dict = {}
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected.")
        return {}
    
    proposed_benchmarks = config.get('proposed_benchmarks', {})

    # The app now focuses on a single, final scorecard
    rows_for_event = []
    for metric_name in all_metrics:
        benchmark_val = proposed_benchmarks.get(metric_name)
        row = {"Category": "N/A", "Metric": metric_name, "Actuals": None, "Benchmark": benchmark_val, "% Difference": None}
        rows_for_event.append(row)
    
    df_event = pd.DataFrame(rows_for_event)
    sheets_dict["Final Scorecard"] = df_event
    return sheets_dict

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
        three_month_avg = inputs['three_month_avg']

        # Ensure data is numeric and drop rows with missing values
        df['Baseline (7-day)'] = pd.to_numeric(df['Baseline (7-day)'], errors='coerce')
        df['Actual (7-day)'] = pd.to_numeric(df['Actual (7-day)'], errors='coerce')
        df.dropna(subset=['Baseline (7-day)', 'Actual (7-day)'], inplace=True)
        
        if df.empty:
            continue

        baselines = df['Baseline (7-day)']
        actuals = df['Actual (7-day)']

        # --- Perform Calculations Exactly as Specified ---
        
        # 1. Calculate the average uplift percentage from historical data
        uplifts = np.where(baselines != 0, (actuals - baselines) / baselines * 100, 0.0)
        avg_uplift_pct = uplifts.mean()
        
        # 2. Calculate the proposed benchmark using the user-provided 3-month average
        # and the calculated uplift.
        proposed_benchmark = three_month_avg * (1 + (avg_uplift_pct / 100))

        # Also calculate historical averages for the summary table
        avg_actual_historical = actuals.mean()
        avg_baseline_historical = baselines.mean()

        # Append the summary row for the final table
        summary_rows.append({
            "Metric":                         metric,
            "Avg. Actuals (Historical)":      round(avg_actual_historical, 2),
            "Avg. Baseline (Historical)":     round(avg_baseline_historical, 2),
            "Baseline Uplift Expect. (%)":    f"{avg_uplift_pct:.2f}%",
            "3-Month Avg (User Input)":       round(three_month_avg, 2),
            "Proposed Benchmark":             round(proposed_benchmark, 2),
        })
        
        # Store the calculated benchmark for this metric
        proposed_benchmarks_dict[metric] = round(proposed_benchmark, 2)
    
    if not summary_rows:
        st.warning("No valid data entered to calculate benchmarks.")
        return pd.DataFrame(), {}
        
    summary_df = pd.DataFrame(summary_rows)
    return summary_df, proposed_benchmarks_dict
