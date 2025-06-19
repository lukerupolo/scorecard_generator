import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List

# --- (get_ai_metric_categories function can remain here if needed later) ---

def process_scorecard_data(config: dict) -> dict:
    """
    Generates the initial scorecard structure, pre-filling benchmarks if they were calculated.
    """
    sheets_dict = {}
    all_metrics = list(set(config.get('metrics', [])))
    if not all_metrics:
        st.warning("No metrics selected.")
        return {}
    
    # AI categorization can be re-enabled here if needed in the future
    ai_categories = {metric: "Uncategorized" for metric in all_metrics}
    
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

def generate_benchmark_summary(
    historical_data: Dict[str, pd.DataFrame],
    metrics: List[str]
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
    summary_df['Avg. Actuals'] = summary_df['Avg. Actuals'].round(2)
    summary_df['Baseline Method'] = summary_df['Baseline Method'].round(2)
    summary_df['Proposed Benchmark'] = summary_df['Proposed Benchmark'].round(2)
    summary_df['Baseline Uplift Expect. (%)'] = summary_df['Baseline Uplift Expect. (%)'].apply(lambda x: f"{x:.2f}%")

    # Create the simple dictionary to pass to the next step
    proposed_benchmarks_dict = summary_df.set_index('Metric')['Proposed Benchmark'].to_dict()

    return summary_df, proposed_benchmarks_dict
