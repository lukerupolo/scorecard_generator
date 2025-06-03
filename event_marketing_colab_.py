from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
# Removed requests import as API logic is removed

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def format_span_labels(event_date: datetime) -> tuple[str, str]:
    b_start = event_date - timedelta(days=7)
    b_end   = event_date - timedelta(days=1)
    a_end   = event_date + timedelta(days=6)
    baseline = f"Baseline {b_start:%Y-%m-%d} → {b_end:%Y-%m-%d}"
    actual   = f"Actual  {event_date:%Y-%m-%d} → {a_end:%Y-%m-%d}"
    return baseline, actual

# ---------------------------------------------------------
# Modified function: generate_event_tables (API calls removed)
# ---------------------------------------------------------
def generate_event_tables(events: list[dict], metrics: list[str], countries: list[str]) -> dict[str, pd.DataFrame]:
    sheets: dict[str, pd.DataFrame] = {}
    # API_relevant_metrics list removed as API calls are removed

    for ev in events:
        baseline_col, actual_col = format_span_labels(ev["date"])

        # Create the DataFrame for this specific event, setting column names correctly
        sheet_df_data = []
        for metric in metrics:
            sheet_df_data.append({
                "Metric": metric,
                baseline_col: None,
                actual_col: None, # Default to None
                "Baseline Method": None,
            })
        template_df = pd.DataFrame(sheet_df_data)

        for country in countries:
            sheet_name = f"{ev['name'][:25] or 'Event'}_{country}"

            # Start with a copy of the event's base template (which has the right column names)
            sheet_df = template_df.copy()

            # Loop through metrics to fill in the template (no API calls here anymore)
            for i, metric in enumerate(sheet_df["Metric"]):
                 # The actual and baseline method columns are left as None initially
                 # and are expected to be filled by the user in the downloaded Excel.
                 pass # No specific action needed here after removing API logic

            sheets[sheet_name] = sheet_df

    return sheets

def compute_final_benchmarks(uploaded_file) -> dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(uploaded_file)
    sheets_all = {sh: pd.read_excel(xls, sh) for sh in xls.sheet_names}
    region_groups: dict[str, list[pd.DataFrame]] = {}

    for name, df in sheets_all.items():
        parts = name.rsplit("_", 1)
        if len(parts) != 2:
            continue
        region_groups.setdefault(parts[1], []).append(df)

    summary: dict[str, pd.DataFrame] = {}
    for region, dfs in region_groups.items():
        # Ensure metrics_list is consistent across all sheets for this region if possible
        # Using the metrics from the first DataFrame for simplicity here,
        # but robust code might merge metrics from all DataFrames.
        if not dfs or dfs[0].empty:
            st.warning(f"No dataframes found for region {region} or first dataframe is empty. Skipping summary.")
            continue

        metrics_list = dfs[0]["Metric"].tolist()
        data = {"Metric": metrics_list}
        avg_actuals, avg_uplift, avg_method = [], [], []

        for m in metrics_list:
            acts, upls, meths = [], [], []
            for df in dfs:
                # Dynamically find column names as they include dates
                cols = df.columns.tolist()
                # Assuming baseline is col 1 and actual is col 2 after Metric
                if len(cols) < 3:
                     continue # Skip if not enough columns
                b_col = cols[1]
                a_col = cols[2]
                meth_col = cols[3] if len(cols) > 3 else None

                row = df[df["Metric"] == m]
                if row.empty:
                    continue

                # Handle potential errors if columns don't exist in a specific sheet or row access issues
                try:
                    base = row[b_col].iloc[0] if b_col in row.columns else None # Use iloc[0] for clarity/safety
                    act  = row[a_col].iloc[0] if a_col in row.columns else None # Use iloc[0]
                    meth = row[meth_col].iloc[0] if meth_col and meth_col in row.columns else None # Use iloc[0]
                except IndexError: # Catch cases where row might be empty even after filter (unlikely but safe)
                    st.warning(f"IndexError accessing row for metric {m} in a sheet for region {region}. Skipping.")
                    continue
                except KeyError as e:
                     st.warning(f"KeyError accessing column {e} for metric {m} in a sheet for region {region}. Skipping.")
                     continue


                if pd.notna(act):
                    acts.append(act)

                if meth is not None and pd.notna(meth): # Check for both None and pandas NaN
                    meths.append(meth)

                if pd.notna(base) and pd.notna(act):
                    if base != 0: # Avoid division by zero
                        upls.append((act - base) / base * 100)
                    elif act > 0:
                         upls.append(float('inf')) # Infinite uplift if base is 0 and actual > 0
                    else: # base is 0 and act is 0
                         upls.append(0.0) # 0 uplift

            # Compute averages, handling cases with no valid data
            avg_actuals_val = np.nanmean(acts) if acts else np.nan
            avg_method_val = np.nanmean(meths) if meths else np.nan # Use nanmean for methods too if they are numerical
            avg_uplift_val = np.nanmean(upls) if upls else np.nan

            avg_actuals.append(avg_actuals_val)
            avg_method.append(avg_method_val)
            avg_uplift.append(avg_uplift_val)


        data["Average Actuals"]        = avg_actuals
        data["Baseline Method"]        = avg_method
        data["Baseline Uplift Expect"] = avg_uplift
        # Compute Proposed Benchmark - need to handle potential NaN from avg_actuals and avg_method
        proposed_benchmark = []
        for actual, method in zip(avg_actuals, avg_method):
            valid_values = [v for v in [actual, method] if pd.notna(v)]
            if valid_values:
                 proposed_benchmark.append(np.nanmedian(valid_values))
            else:
                 proposed_benchmark.append(np.nan)


        data["Proposed Benchmark"]     = proposed_benchmark
        summary[region] = pd.DataFrame(data)

    return summary


# ---------------------------------------------------------
# Streamlit App UI
# ---------------------------------------------------------
st.set_page_config(page_title="Event Marketing Analytics", layout="wide")
st.markdown(
    """
# 📊 Event Marketing Analytics Suite

Welcome! This tool helps you:

1.  **Generate** a template workbook to track multiple events and regions.
2.  **Download** the blank workbook, fill in your data (Baseline, Actual, Baseline Method).
3.  **Upload** the completed workbook to compute final benchmarks per region.

Select a mode below to get started.
""",
    unsafe_allow_html=True
)

mode = st.sidebar.radio(
    "Select an action:",
    ["Generate template", "Final benchmarks"]
)

if mode == "Generate template":
    st.sidebar.header("Step 1: Configure template")
    st.sidebar.markdown(
        """
        Specify your event names, start dates, metrics, and regions.
        When ready, click **Generate template** to download the Excel file.
        """
    )
    n_events = st.sidebar.number_input("Quantity of events", 1, 20, 1)
    events: list[dict] = []
    for i in range(n_events):
        st.sidebar.subheader(f"Event {i+1}")
        nm = st.sidebar.text_input("Name", key=f"nm{i}") or f"Event{i+1}"
        dt = st.sidebar.date_input("Start date (T)", key=f"dt{i}")
        if isinstance(dt, list):
            dt = dt[0]
        events.append({"name": nm, "date": datetime.combine(dt, datetime.min.time())})

    all_metrics = [
        "Sessions", "DAU", "Revenue", "Installs", "Retention", "Watch Time", "ARPU", "Conversions",
        "Video Views (VOD)", "Hours Watched (Streams)", "Social Mentions", "Search Index",
        "Broadcast TWT", "PCCV", "AMA"
    ]
    metrics = st.sidebar.multiselect(
        "Metrics to measure:",
        all_metrics,
        default=["Sessions", "DAU", "Revenue", "Installs", "Video Views (VOD)", "Hours Watched (Streams)"]
    )

    countries = st.sidebar.multiselect(
        "Regions/Countries:",
        ["US","GB","KR","JP","BR","DE","AU","CA","FR","IN","TH","ID","SA"],
        default=["US","GB","AU"]
    )
    if st.sidebar.button("Generate template 📥"):
        if not events or not metrics or not countries:
             st.warning("Please configure at least one event, metric, and country.")
        else:
            with st.spinner("Generating template..."):
                sheets = generate_event_tables(events, metrics, countries)
                if sheets:
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        for sheet_name, sheet_df in sheets.items():
                            sheet_df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                    excel_buffer.seek(0)
                    st.download_button(
                        label="Download template workbook",
                        data=excel_buffer,
                        file_name="event_marketing_template.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("No sheets were generated. Please check your inputs.")


elif mode == "Final benchmarks":
    st.sidebar.header("Step 2: Upload completed workbook")
    st.sidebar.markdown(
        """
        Upload the Excel workbook you downloaded and filled with data.
        """
    )
    uploaded_file = st.sidebar.file_uploader("Upload Excel workbook", type=["xlsx"])

    if uploaded_file is not None:
        with st.spinner("Computing benchmarks..."):
            summary_sheets = compute_final_benchmarks(uploaded_file)

        st.header("Benchmark Summary per Region")

        if summary_sheets:
            for region, summary_df in summary_sheets.items():
                st.subheader(f"Region: {region}")
                st.dataframe(summary_df)

            # Option to download the summary
            summary_excel_buffer = BytesIO()
            with pd.ExcelWriter(summary_excel_buffer, engine='openpyxl') as writer:
                for region, summary_df in summary_sheets.items():
                     summary_df.to_excel(writer, sheet_name=f"{region}_Summary"[:31], index=False)
            summary_excel_buffer.seek(0)
            st.download_button(
                label="Download Benchmark Summary",
                data=summary_excel_buffer,
                file_name="event_benchmark_summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
             st.warning("Could not compute benchmarks. Please ensure the uploaded file is in the correct format.")
