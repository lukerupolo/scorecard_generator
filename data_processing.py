import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List

# ... (AI Categorization and process_scorecard_data functions remain the same)

def process_scorecard_data(config: dict) -> dict:
    """
    Generates the initial scorecard structure, pre-filling benchmarks if they were calculated.
    """
    sheets_dict = {}
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected.")
        return {}
    
    # AI categorization can be re-enabled here if needed in the future.
    ai_categories = {metric: "N/A" for metric in all_metrics}
    
    proposed_benchmarks = config.get('proposed_benchmarks', {})

    rows_for_event = []
    for metric_name in all_metrics:
        benchmark_val = proposed_benchmarks.get(metric_name)
        row = {"Category": ai_categories.get(metric_name, "N/A"), "Metric": metric_name, "Actuals": None, "Benchmark": benchmark_val, "% Difference": None}
        rows_for_event.append(row)
    
    df_event = pd.DataFrame(rows_for_event)
    sheets_dict["Final Scorecard"] = df_event
    return sheets_dict


def calculate_all_benchmarks(historical_inputs: Dict[str, Dict]) -> (pd.DataFrame, Dict, Dict):
    """
    Takes a dictionary where keys are metrics and values contain their historical data
    and a user-provided 3-month average. Returns a summary DataFrame and a simple
    dictionary of {metric: proposed_benchmark}.
    """
    summary_rows = []
    proposed_benchmarks_dict = {}
    avg_actuals_dict = {}

    for metric, inputs in historical_inputs.items():
        df = inputs['historical_df']
        three_month_avg_input = inputs['three_month_avg']

        # Ensure data is numeric and drop rows with missing values
        df['Baseline (7-day)'] = pd.to_numeric(df['Baseline (7-day)'], errors='coerce')
        df['Actual (7-day)'] = pd.to_numeric(df['Actual (7-day)'], errors='coerce')
        df.dropna(subset=['Baseline (7-day)', 'Actual (7-day)'], inplace=True)
        
        if df.empty:
            continue

        baselines = df['Baseline (7-day)']
        actuals = df['Actual (7-day)']

        # --- Perform Calculations Exactly as Specified ---
        
        # 1. Calculate historical averages and uplift
        avg_actual_historical = actuals.mean()
        uplifts = np.where(baselines != 0, (actuals - baselines) / baselines * 100, 0.0)
        avg_uplift_pct = uplifts.mean()
        
        # 2. Calculate the "Baseline Method" value
        # This is the user-provided 3-month average adjusted by the historical uplift.
        baseline_method_value = three_month_avg_input * (1 + (avg_uplift_pct / 100))
        
        # 3. Calculate the "Proposed Benchmark" value
        # This is the median of the historical average actuals and the new baseline method value.
        proposed_benchmark = np.median([avg_actual_historical, baseline_method_value])

        # Append the summary row for the final table
        summary_rows.append({
            "Metric":                         metric,
            "Avg. Actuals (Historical)":      round(avg_actual_historical, 2),
            "Baseline Method":                round(baseline_method_value, 2), # Display the newly calculated value
            "Baseline Uplift Expect. (%)":    f"{avg_uplift_pct:.2f}%",
            "Proposed Benchmark":             round(proposed_benchmark, 2),
        })
        
        # Store the final calculated values to be used in the main scorecard
        proposed_benchmarks_dict[metric] = round(proposed_benchmark, 2)
        avg_actuals_dict[metric] = round(avg_actual_historical, 2)
    
    if not summary_rows:
        st.warning("No valid data entered to calculate benchmarks.")
        return pd.DataFrame(), {}, {}
        
    summary_df = pd.DataFrame(summary_rows)
    return summary_df, proposed_benchmarks_dict, avg_actuals_dict
