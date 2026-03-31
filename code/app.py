"""
Streamlit UI for the Co-Simulation Framework.

Launch with:  streamlit run code/app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import logging
import sys
import os
import io

# Ensure the code/ directory is on the import path
sys.path.insert(0, os.path.dirname(__file__))

from scenarios.scenario_e1 import run_scenario_e1
from scenarios.scenario_e2 import (
    run_scenario_e2, compare_strategies, ChargingStrategy,
)
from scenarios.scenario_m1 import (
    run_scenario_m1, compare_signal_strategies,
)
from scenarios.scenario_t1 import (
    run_scenario_t1, compare_slicing_strategies, SlicingStrategy,
)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Co-Simulation Framework",
    page_icon="⚡",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar – scenario selector
# ---------------------------------------------------------------------------
st.sidebar.title("Co-Simulation Framework")
st.sidebar.markdown("---")

SCENARIOS = {
    "E1 – Smart Grid with Renewable Integration": "E1",
    "E2 – Electric Vehicle Charging Infrastructure": "E2",
    "M1 – Urban Traffic Congestion Management": "M1",
    "T1 – 5G Slice Resource Allocation": "T1",
}

scenario_label = st.sidebar.selectbox("Select Scenario", list(SCENARIOS.keys()))
scenario_key = SCENARIOS[scenario_label]

# Per-scenario options
strategy_e2 = None
adaptive_m1 = True
strategy_t1 = None
compare_mode = False

if scenario_key == "E2":
    strategy_e2 = st.sidebar.selectbox(
        "Charging Strategy",
        ["Smart", "Uncoordinated", "V2G"],
    )
    compare_mode = st.sidebar.checkbox("Compare all strategies")

elif scenario_key == "M1":
    adaptive_m1 = st.sidebar.selectbox(
        "Signal Control",
        ["Adaptive", "Fixed"],
    ) == "Adaptive"
    compare_mode = st.sidebar.checkbox("Compare both strategies")

elif scenario_key == "T1":
    strategy_t1 = st.sidebar.selectbox(
        "Slicing Strategy",
        ["Dynamic", "Static"],
    )
    compare_mode = st.sidebar.checkbox("Compare both strategies")

st.sidebar.markdown("---")
run_button = st.sidebar.button("Run Simulation", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title(scenario_label)


def _format_metric_name(key: str) -> str:
    """Turn a snake_case metric key into a readable label."""
    return key.replace("_", " ").replace("pct", "(%)").replace("kwh", "(kWh)").replace(
        "kw", "(kW)").replace("usd", "(USD)").replace("pu", "(p.u.)").replace(
        " s ", " (s) ").replace(" g ", " (g) ").title()


def _display_report(report: dict):
    """Render a single scenario report."""
    # --- Components ---
    st.subheader("Components")
    comp = report.get("components", {})
    cols = st.columns(min(len(comp), 4))
    for idx, (key, val) in enumerate(comp.items()):
        cols[idx % len(cols)].metric(_format_metric_name(key), val)

    # --- Metrics ---
    st.subheader("Metrics")
    metrics = report.get("metrics", {})

    # Separate numeric from non-numeric metrics
    numeric_metrics = {}
    text_metrics = {}
    list_metrics = {}
    for k, v in metrics.items():
        if isinstance(v, list):
            list_metrics[k] = v
        elif isinstance(v, (int, float, np.integer, np.floating)):
            numeric_metrics[k] = v
        else:
            text_metrics[k] = v

    # Show numeric metrics in a metric grid
    metric_cols = st.columns(4)
    for idx, (key, val) in enumerate(numeric_metrics.items()):
        label = _format_metric_name(key)
        display = f"{val:,.2f}" if isinstance(val, float) else str(val)
        metric_cols[idx % 4].metric(label, display)

    # Show text metrics (e.g. PASS/FAIL validations)
    if text_metrics:
        st.markdown("**Validation**")
        for k, v in text_metrics.items():
            icon = "✅" if v == "PASS" else "❌" if v == "FAIL" else "ℹ️"
            st.markdown(f"- {_format_metric_name(k)}: {icon} **{v}**")

    # Show list metrics (e.g. battery SOC list)
    if list_metrics:
        for k, v in list_metrics.items():
            st.markdown(f"**{_format_metric_name(k)}**")
            st.bar_chart(pd.Series(v, name=_format_metric_name(k)))

    # --- Metrics table for reference ---
    with st.expander("Raw Metrics Table"):
        flat = {_format_metric_name(k): v for k, v in metrics.items() if not isinstance(v, list)}
        st.dataframe(pd.DataFrame(flat.items(), columns=["Metric", "Value"]), use_container_width=True)


def _display_comparison(results: dict, scenario_key: str):
    """Render a side-by-side comparison of multiple strategy reports."""
    strategies = list(results.keys())
    tabs = st.tabs([s.upper() for s in strategies])

    for tab, strat_name in zip(tabs, strategies):
        with tab:
            _display_report(results[strat_name])

    # --- Comparison bar charts ---
    st.subheader("Strategy Comparison")
    all_metrics = {}
    for strat_name, report in results.items():
        for k, v in report["metrics"].items():
            if isinstance(v, (int, float, np.integer, np.floating)):
                all_metrics.setdefault(k, {})[strat_name] = v

    comparison_df = pd.DataFrame(all_metrics).T
    comparison_df.index = [_format_metric_name(k) for k in comparison_df.index]

    # Pick the most interesting metrics per scenario for a summary chart
    highlight_keys = _highlight_keys(scenario_key)
    highlight_labels = [_format_metric_name(k) for k in highlight_keys if k in all_metrics]
    if highlight_labels:
        chart_df = comparison_df.loc[comparison_df.index.isin(highlight_labels)]
        st.bar_chart(chart_df)

    with st.expander("Full Comparison Table"):
        st.dataframe(comparison_df, use_container_width=True)


def _highlight_keys(scenario_key: str) -> list:
    """Return the most relevant metric keys for the comparison chart."""
    if scenario_key == "E2":
        return [
            "peak_load_kw",
            "total_charging_cost_usd",
            "avg_cost_per_vehicle_usd",
            "max_transformer_loading_pct",
            "transformer_overload_count",
            "v2g_revenue_usd",
            "load_factor",
            "vehicles_meeting_soc_target",
        ]
    if scenario_key == "M1":
        return [
            "completion_rate_pct",
            "avg_travel_time_s",
            "avg_delay_s",
            "total_emissions_kg_co2",
            "emissions_per_vehicle_g",
            "max_queue_length",
            "avg_queue_length",
            "throughput_veh_per_hour",
        ]
    if scenario_key == "T1":
        return [
            "qos_satisfaction_embb_pct",
            "qos_satisfaction_urllc_pct",
            "qos_satisfaction_mmtc_pct",
            "overall_utilization_pct",
            "resource_waste_pct",
            "handover_success_rate_pct",
            "handover_failures",
        ]
    return []


# ---------------------------------------------------------------------------
# Run simulation
# ---------------------------------------------------------------------------
if run_button:
    # Capture log output to display in the UI
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    try:
        if compare_mode:
            with st.spinner("Running comparison – this may take a while…"):
                if scenario_key == "E2":
                    results = compare_strategies()
                elif scenario_key == "M1":
                    results = compare_signal_strategies()
                elif scenario_key == "T1":
                    results = compare_slicing_strategies()
                else:
                    st.warning("Comparison not available for this scenario.")
                    results = None

            if results:
                _display_comparison(results, scenario_key)
        else:
            with st.spinner("Running simulation…"):
                if scenario_key == "E1":
                    report = run_scenario_e1()
                elif scenario_key == "E2":
                    strat_map = {
                        "Smart": ChargingStrategy.SMART,
                        "Uncoordinated": ChargingStrategy.UNCOORDINATED,
                        "V2G": ChargingStrategy.V2G,
                    }
                    report = run_scenario_e2(strategy=strat_map[strategy_e2])
                elif scenario_key == "M1":
                    report = run_scenario_m1(adaptive_signals=adaptive_m1)
                elif scenario_key == "T1":
                    strat_map = {
                        "Dynamic": SlicingStrategy.DYNAMIC,
                        "Static": SlicingStrategy.STATIC,
                    }
                    report = run_scenario_t1(strategy=strat_map[strategy_t1])

            _display_report(report)

    finally:
        root_logger.removeHandler(handler)

    # Show simulation log
    log_output = log_stream.getvalue()
    if log_output:
        with st.expander("Simulation Log"):
            st.code(log_output, language="text")
else:
    st.info("Configure the scenario in the sidebar and click **Run Simulation**.")
