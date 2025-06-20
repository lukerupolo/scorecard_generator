import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List

def process_scorecard_data(config: dict) -> dict:
    """
    Generates the final scorecard structure, pre-filling 'Actuals' and 'Benchmark' 
    if they were calculated in the previous step.
    """
    sheets_dict = {}
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected.")
        return {}
    
    proposed_benchmarks = config.get('proposed_benchmarks') or {}
    avg_actuals = config.get('avg_actuals') or {}

    rows_for_event = []
    for metric_name in all_metrics:
        benchmark_val = proposed_benchmarks.get(metric_name)
        actual_val = avg_actuals.get(metric_name)
        
        row = {"Category": "N/A", "Metric": metric_name, "Actuals": actual_val, "Benchmark": benchmark_val, "% Difference": None}
        rows_for_event.append(row)
    
    df_event = pd.DataFrame(rows_for_event)
    sheets_dict["Final Scorecard"] = df_event
    return sheets_dict

def generate_benchmark_summary(
    historical_data: Dict[str, pd.DataFrame],
    metrics: List[str]
) -> (pd.DataFrame, Dict, Dict):
    """
    Takes a dictionary of historical event DataFrames and calculates the final
    proposed benchmark summary table based on the specified logic.
    """
    all_events_df = pd.concat(historical_data.values(), ignore_index=True)
    
    all_events_df['Baseline (7-day)'] = pd.to_numeric(all_events_df['Baseline (7-day)'], errors='coerce')
    all_events_df['Actual (7-day)'] = pd.to_numeric(all_events_df['Actual (7-day)'], errors='coerce')
    all_events_df.dropna(subset=['Baseline (7-day)', 'Actual (7-day)'], inplace=True)

    if all_events_df.empty:
        st.warning("No valid historical data was entered to calculate benchmarks.")
        return pd.DataFrame(), {}, {}

    # --- Perform Calculations Exactly as Specified ---
    
    # Calculate Uplift % for each individual historical data row
    all_events_df['Uplift %'] = ((all_events_df['Actual (7-day)'] - all_events_df['Baseline (7-day)']) / all_events_df['Baseline (7-day)']) * 100

    grouped = all_events_df.groupby('Metric')
    
    avg_actuals = grouped['Actual (7-day)'].mean()
    avg_baselines = grouped['Baseline (7-day)'].mean()
    avg_uplift_pct = all_events_df.groupby('Metric')['Uplift %'].mean()
    
    summary_df = pd.DataFrame({
        "Avg. Actuals": avg_actuals,
        "Baseline Method": avg_baselines,
        "Baseline Uplift Expect. (%)": avg_uplift_pct
    }).reset_index()

    # Calculate the Proposed Benchmark using the calculated averages
    summary_df['Proposed Benchmark'] = summary_df.apply(
        lambda row: np.median([row['Avg. Actuals'], row['Baseline Method']]),
        axis=1
    )
    
    final_cols = ["Metric", "Avg. Actuals", "Baseline Method", "Baseline Uplift Expect. (%)", "Proposed Benchmark"]
    summary_df = summary_df[final_cols]
    
    for col in ["Avg. Actuals", "Baseline Method", "Proposed Benchmark"]:
        summary_df[col] = summary_df[col].round(2)
    summary_df['Baseline Uplift Expect. (%)'] = summary_df['Baseline Uplift Expect. (%)'].apply(lambda x: f"{x:.2f}%")

    # Create dictionaries to pass to the next step
    proposed_benchmarks_dict = summary_df.set_index('Metric')['Proposed Benchmark'].to_dict()
    avg_actuals_dict = summary_df.set_index('Metric')['Avg. Actuals'].to_dict()

    return summary_df, proposed_benchmarks_dict, avg_actuals_dict
