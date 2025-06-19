import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List

# Note: AI categorization has been removed as per the latest workflow.
# It can be re-added here if needed in the future.

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

    for idx, ev in enumerate(config.get('events', [])):
        rows_for_event = []
        for metric_name in all_metrics:
            # Pre-fill the benchmark value if it exists, otherwise leave it blank
            benchmark_val = proposed_benchmarks.get(metric_name)
            
            # The initial table has blank values, ready for manual input
            row = {
                "Category": "N/A",  # Category can be manually edited later
                "Metric": metric_name, 
                "Actuals": None, 
                "Benchmark": benchmark_val, 
                "% Difference": None
            }
            rows_for_event.append(row)

        df_event = pd.DataFrame(rows_for_event)
        
        unique_key = f"{ev['name'][:24] or f'Event {idx+1}'} - {idx+1}"
        sheets_dict[unique_key] = df_event
        
    return sheets_dict

def generate_benchmark_summary(
    historical_data: Dict[str, pd.DataFrame]
) -> (pd.DataFrame, Dict):
    """
    Takes a dictionary of historical event DataFrames and calculates the final
    proposed benchmark summary table based on the specified logic.
    """
    # Combine all historical event data into a single DataFrame
    all_events_df = pd.concat(historical_data.values(), ignore_index=True)

    # Ensure data is numeric and drop rows with missing values
    all_events_df['Baseline (7-day)'] = pd.to_numeric(all_events_df['Baseline (7-day)'], errors='coerce')
    all_events_df['Actual (7-day)'] = pd.to_numeric(all_events_df['Actual (7-day)'], errors='coerce')
    all_events_df.dropna(subset=['Baseline (7-day)', 'Actual (7-day)'], inplace=True)

    if all_events_df.empty:
        st.warning("No valid historical data was entered to calculate benchmarks.")
        return pd.DataFrame(), {}

    # --- Perform Calculations as per the specified logic ---
    
    # Calculate Uplift % for each individual historical data row
    all_events_df['Uplift %'] = ((all_events_df['Actual (7-day)'] - all_events_df['Baseline (7-day)']) / all_events_df['Baseline (7-day)']) * 100

    # Group by metric to calculate averages
    grouped = all_events_df.groupby('Metric')
    
    avg_actuals = grouped['Actual (7-day)'].mean()
    avg_baselines = grouped['Baseline (7-day)'].mean()
    avg_uplift_pct = grouped['Uplift %'].mean()
    
    # Assemble the summary DataFrame
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
    
    # --- Formatting for Final Display ---
    final_cols = ["Metric", "Avg. Actuals", "Baseline Method", "Baseline Uplift Expect. (%)", "Proposed Benchmark"]
    summary_df = summary_df[final_cols]
    
    for col in ["Avg. Actuals", "Baseline Method", "Proposed Benchmark"]:
        summary_df[col] = summary_df[col].round(2)
    summary_df['Baseline Uplift Expect. (%)'] = summary_df['Baseline Uplift Expect. (%)'].apply(lambda x: f"{x:.2f}%")

    # Create the simple dictionary to pass to the next step
    proposed_benchmarks_dict = summary_df.set_index('Metric')['Proposed Benchmark'].to_dict()

    return summary_df, proposed_benchmarks_dict
