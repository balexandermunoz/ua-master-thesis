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
scenario_kwargs = {}

if scenario_key == "E1":
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        scenario_kwargs["num_solar_pvs"] = st.number_input("Solar PV count", 1, 500, 50)
        col1, col2 = st.columns(2)
        scenario_kwargs["solar_capacity_min_kw"] = col1.number_input("Solar min (kW)", 0.5, 50.0, 5.0, step=0.5)
        scenario_kwargs["solar_capacity_max_kw"] = col2.number_input("Solar max (kW)", 1.0, 100.0, 10.0, step=0.5)
        scenario_kwargs["num_wind_turbines"] = st.number_input("Wind turbine count", 0, 50, 3)
        scenario_kwargs["wind_capacity_kw"] = st.number_input("Wind capacity (kW each)", 10.0, 5000.0, 500.0, step=50.0)
        scenario_kwargs["num_batteries"] = st.number_input("Battery count", 0, 100, 5)
        scenario_kwargs["battery_capacity_kwh"] = st.number_input("Battery capacity (kWh each)", 5.0, 500.0, 50.0, step=5.0)
        scenario_kwargs["num_loads"] = st.number_input("Residential loads", 10, 5000, 800, step=10)
        scenario_kwargs["sim_duration_hours"] = st.number_input("Simulation duration (h)", 1, 72, 24)

elif scenario_key == "E2":
    strategy_e2 = st.sidebar.selectbox(
        "Charging Strategy",
        ["Smart", "Uncoordinated", "V2G"],
    )
    compare_mode = st.sidebar.checkbox("Compare all strategies")
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        scenario_kwargs["num_vehicles"] = st.number_input("Number of EVs", 10, 1000, 100, step=10)
        scenario_kwargs["num_l2_stations"] = st.number_input("Level-2 stations", 1, 200, 20)
        scenario_kwargs["num_dc_stations"] = st.number_input("DC-fast stations", 1, 50, 5)
        scenario_kwargs["grid_capacity_kw"] = st.number_input("Grid capacity (kW)", 500.0, 20000.0, 2500.0, step=100.0)
        scenario_kwargs["base_load_kw"] = st.number_input("Base load (kW)", 500.0, 15000.0, 2000.0, step=100.0)

elif scenario_key == "M1":
    adaptive_m1 = st.sidebar.selectbox(
        "Signal Control",
        ["Adaptive", "Fixed"],
    ) == "Adaptive"
    compare_mode = st.sidebar.checkbox("Compare both strategies")
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        scenario_kwargs["num_vehicles"] = st.number_input("Number of vehicles", 100, 10000, 2500, step=100)
        scenario_kwargs["grid_size"] = st.number_input("Grid size (NxN)", 2, 10, 5)
        scenario_kwargs["sim_duration_hours"] = st.number_input("Simulation duration (h)", 1, 12, 3)

elif scenario_key == "T1":
    strategy_t1 = st.sidebar.selectbox(
        "Slicing Strategy",
        ["Dynamic", "Static"],
    )
    compare_mode = st.sidebar.checkbox("Compare both strategies")
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        scenario_kwargs["num_gnbs"] = st.number_input("Number of gNBs", 1, 20, 3)
        scenario_kwargs["embb_users"] = st.number_input("eMBB users", 10, 500, 100, step=10)
        scenario_kwargs["urllc_users"] = st.number_input("URLLC users", 5, 200, 40, step=5)
        scenario_kwargs["mmtc_users"] = st.number_input("mMTC users", 5, 500, 60, step=5)
        scenario_kwargs["rbs_per_gnb"] = st.number_input("RBs per gNB", 10, 500, 100, step=10)

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
                    results = compare_strategies(**scenario_kwargs)
                elif scenario_key == "M1":
                    results = compare_signal_strategies(**scenario_kwargs)
                elif scenario_key == "T1":
                    results = compare_slicing_strategies(**scenario_kwargs)
                else:
                    st.warning("Comparison not available for this scenario.")
                    results = None

            if results:
                _display_comparison(results, scenario_key)
        else:
            with st.spinner("Running simulation…"):
                if scenario_key == "E1":
                    report = run_scenario_e1(**scenario_kwargs)
                elif scenario_key == "E2":
                    strat_map = {
                        "Smart": ChargingStrategy.SMART,
                        "Uncoordinated": ChargingStrategy.UNCOORDINATED,
                        "V2G": ChargingStrategy.V2G,
                    }
                    report = run_scenario_e2(strategy=strat_map[strategy_e2], **scenario_kwargs)
                elif scenario_key == "M1":
                    report = run_scenario_m1(adaptive_signals=adaptive_m1, **scenario_kwargs)
                elif scenario_key == "T1":
                    strat_map = {
                        "Dynamic": SlicingStrategy.DYNAMIC,
                        "Static": SlicingStrategy.STATIC,
                    }
                    report = run_scenario_t1(strategy=strat_map[strategy_t1], **scenario_kwargs)

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
