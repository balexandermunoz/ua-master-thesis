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
import time

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
from scenarios.scenario_e2m1 import (
    run_scenario_e2m1, compare_coupling_modes,
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
    "E2+M1 – Energy–Mobility Cross-Domain": "E2M1",
}

scenario_label = st.sidebar.selectbox("Select Scenario", list(SCENARIOS.keys()))
scenario_key = SCENARIOS[scenario_label]

# ---------------------------------------------------------------------------
# Article-default parameter values
# ---------------------------------------------------------------------------
E1_DEFAULTS = {
    "e1_num_solar_pvs": 50, "e1_solar_capacity_min_kw": 5.0,
    "e1_solar_capacity_max_kw": 10.0, "e1_num_wind_turbines": 3,
    "e1_wind_capacity_kw": 500.0, "e1_num_batteries": 5,
    "e1_battery_capacity_kwh": 50.0, "e1_num_loads": 800,
    "e1_sim_duration_hours": 24,
}
E2_DEFAULTS = {
    "e2_num_vehicles": 100, "e2_num_l2_stations": 20,
    "e2_num_dc_stations": 5, "e2_grid_capacity_kw": 2500.0,
    "e2_base_load_kw": 2000.0,
}
M1_DEFAULTS = {
    "m1_num_vehicles": 2500, "m1_grid_size": 5,
    "m1_sim_duration_hours": 3,
}
T1_DEFAULTS = {
    "t1_num_gnbs": 3, "t1_embb_users": 100, "t1_urllc_users": 40,
    "t1_mmtc_users": 60, "t1_rbs_per_gnb": 100,
}
E2M1_DEFAULTS = {
    "e2m1_num_evs": 500, "e2m1_num_background": 2000,
    "e2m1_grid_size": 5, "e2m1_sim_duration_hours": 3,
}

def _reset_params(defaults: dict):
    """Reset session_state keys to article defaults."""
    for k, v in defaults.items():
        st.session_state[k] = v

# Per-scenario options
strategy_e2 = None
adaptive_m1 = True
strategy_t1 = None
strategy_e2m1 = None
coupled_e2m1 = True
compare_mode = False
scenario_kwargs = {}

if scenario_key == "E1":
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        d = E1_DEFAULTS
        scenario_kwargs["num_solar_pvs"] = st.number_input(
            "Solar PV count", 1, 500, d["e1_num_solar_pvs"], key="e1_num_solar_pvs")
        col1, col2 = st.columns(2)
        scenario_kwargs["solar_capacity_min_kw"] = col1.number_input(
            "Solar min (kW)", 0.5, 50.0, d["e1_solar_capacity_min_kw"],
            step=0.5, key="e1_solar_capacity_min_kw")
        scenario_kwargs["solar_capacity_max_kw"] = col2.number_input(
            "Solar max (kW)", 1.0, 100.0, d["e1_solar_capacity_max_kw"],
            step=0.5, key="e1_solar_capacity_max_kw")
        scenario_kwargs["num_wind_turbines"] = st.number_input(
            "Wind turbine count", 0, 50, d["e1_num_wind_turbines"], key="e1_num_wind_turbines")
        scenario_kwargs["wind_capacity_kw"] = st.number_input(
            "Wind capacity (kW each)", 10.0, 5000.0, d["e1_wind_capacity_kw"],
            step=50.0, key="e1_wind_capacity_kw")
        scenario_kwargs["num_batteries"] = st.number_input(
            "Battery count", 0, 100, d["e1_num_batteries"], key="e1_num_batteries")
        scenario_kwargs["battery_capacity_kwh"] = st.number_input(
            "Battery capacity (kWh each)", 5.0, 500.0, d["e1_battery_capacity_kwh"],
            step=5.0, key="e1_battery_capacity_kwh")
        scenario_kwargs["num_loads"] = st.number_input(
            "Residential loads", 10, 5000, d["e1_num_loads"],
            step=10, key="e1_num_loads")
        scenario_kwargs["sim_duration_hours"] = st.number_input(
            "Simulation duration (h)", 1, 72, d["e1_sim_duration_hours"],
            key="e1_sim_duration_hours")
        st.button("Reset to Defaults", on_click=_reset_params,
                  args=(d,), key="e1_reset")

elif scenario_key == "E2":
    strategy_e2 = st.sidebar.selectbox(
        "Charging Strategy",
        ["Smart", "Uncoordinated", "V2G"],
    )
    compare_mode = st.sidebar.checkbox("Compare all strategies")
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        d = E2_DEFAULTS
        scenario_kwargs["num_vehicles"] = st.number_input(
            "Number of EVs", 10, 1000, d["e2_num_vehicles"],
            step=10, key="e2_num_vehicles")
        scenario_kwargs["num_l2_stations"] = st.number_input(
            "Level-2 stations", 1, 200, d["e2_num_l2_stations"],
            key="e2_num_l2_stations")
        scenario_kwargs["num_dc_stations"] = st.number_input(
            "DC-fast stations", 1, 50, d["e2_num_dc_stations"],
            key="e2_num_dc_stations")
        scenario_kwargs["grid_capacity_kw"] = st.number_input(
            "Grid capacity (kW)", 500.0, 20000.0, d["e2_grid_capacity_kw"],
            step=100.0, key="e2_grid_capacity_kw")
        scenario_kwargs["base_load_kw"] = st.number_input(
            "Base load (kW)", 500.0, 15000.0, d["e2_base_load_kw"],
            step=100.0, key="e2_base_load_kw")
        st.button("Reset to Defaults", on_click=_reset_params,
                  args=(d,), key="e2_reset")

elif scenario_key == "M1":
    adaptive_m1 = st.sidebar.selectbox(
        "Signal Control",
        ["Adaptive", "Fixed"],
    ) == "Adaptive"
    compare_mode = st.sidebar.checkbox("Compare both strategies")
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        d = M1_DEFAULTS
        scenario_kwargs["num_vehicles"] = st.number_input(
            "Number of vehicles", 100, 10000, d["m1_num_vehicles"],
            step=100, key="m1_num_vehicles")
        scenario_kwargs["grid_size"] = st.number_input(
            "Grid size (NxN)", 2, 10, d["m1_grid_size"], key="m1_grid_size")
        scenario_kwargs["sim_duration_hours"] = st.number_input(
            "Simulation duration (h)", 1, 12, d["m1_sim_duration_hours"],
            key="m1_sim_duration_hours")
        st.button("Reset to Defaults", on_click=_reset_params,
                  args=(d,), key="m1_reset")

elif scenario_key == "T1":
    strategy_t1 = st.sidebar.selectbox(
        "Slicing Strategy",
        ["Dynamic", "Static"],
    )
    compare_mode = st.sidebar.checkbox("Compare both strategies")
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        d = T1_DEFAULTS
        scenario_kwargs["num_gnbs"] = st.number_input(
            "Number of gNBs", 1, 20, d["t1_num_gnbs"], key="t1_num_gnbs")
        scenario_kwargs["embb_users"] = st.number_input(
            "eMBB users", 10, 500, d["t1_embb_users"],
            step=10, key="t1_embb_users")
        scenario_kwargs["urllc_users"] = st.number_input(
            "URLLC users", 5, 200, d["t1_urllc_users"],
            step=5, key="t1_urllc_users")
        scenario_kwargs["mmtc_users"] = st.number_input(
            "mMTC users", 5, 500, d["t1_mmtc_users"],
            step=5, key="t1_mmtc_users")
        scenario_kwargs["rbs_per_gnb"] = st.number_input(
            "RBs per gNB", 10, 500, d["t1_rbs_per_gnb"],
            step=10, key="t1_rbs_per_gnb")
        st.button("Reset to Defaults", on_click=_reset_params,
                  args=(d,), key="t1_reset")

elif scenario_key == "E2M1":
    coupled_e2m1 = st.sidebar.selectbox(
        "Coupling Mode",
        ["Coupled", "Uncoupled"],
    ) == "Coupled"
    strategy_e2m1 = st.sidebar.selectbox(
        "Charging Strategy",
        ["Smart", "Uncoordinated", "V2G"],
        key="e2m1_strategy",
    )
    compare_mode = st.sidebar.checkbox("Compare coupled vs uncoupled")
    with st.sidebar.expander("Scenario Parameters", expanded=False):
        st.caption("Article defaults shown. Adjust to explore.")
        d = E2M1_DEFAULTS
        scenario_kwargs["num_evs"] = st.number_input(
            "Number of EVs", 10, 2000, d["e2m1_num_evs"],
            step=50, key="e2m1_num_evs")
        scenario_kwargs["num_background"] = st.number_input(
            "Background vehicles", 100, 10000, d["e2m1_num_background"],
            step=100, key="e2m1_num_background")
        scenario_kwargs["grid_size"] = st.number_input(
            "Grid size (NxN)", 2, 10, d["e2m1_grid_size"],
            key="e2m1_grid_size")
        scenario_kwargs["sim_duration_hours"] = st.number_input(
            "Simulation duration (h)", 1, 12, d["e2m1_sim_duration_hours"],
            key="e2m1_sim_duration_hours")
        st.button("Reset to Defaults", on_click=_reset_params,
                  args=(d,), key="e2m1_reset")

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
    if scenario_key == "E2M1":
        return [
            "avg_ev_drive_time_s",
            "avg_ev_queue_time_s",
            "evs_meeting_soc_target",
            "total_energy_charged_kwh",
            "peak_grid_load_kw",
            "total_emissions_kg_co2",
            "bg_avg_travel_time_s",
            "max_queue_length",
        ]
    return []


# ---------------------------------------------------------------------------
# Run simulation
# ---------------------------------------------------------------------------
if run_button:
    # Clear previous results
    st.session_state.pop("last_result", None)

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    try:
        t0 = time.time()
        run_label = "Running comparison…" if compare_mode else "Running simulation…"
        with st.status(run_label, expanded=True) as status:
            result = None
            if compare_mode:
                if scenario_key == "E2":
                    result = compare_strategies(**scenario_kwargs)
                elif scenario_key == "M1":
                    result = compare_signal_strategies(**scenario_kwargs)
                elif scenario_key == "T1":
                    result = compare_slicing_strategies(**scenario_kwargs)
                elif scenario_key == "E2M1":
                    strat_map = {
                        "Smart": ChargingStrategy.SMART,
                        "Uncoordinated": ChargingStrategy.UNCOORDINATED,
                        "V2G": ChargingStrategy.V2G,
                    }
                    result = compare_coupling_modes(
                        charging_strategy=strat_map[strategy_e2m1],
                        **scenario_kwargs)
                else:
                    st.warning("Comparison not available for this scenario.")
            else:
                if scenario_key == "E1":
                    result = run_scenario_e1(**scenario_kwargs)
                elif scenario_key == "E2":
                    strat_map = {
                        "Smart": ChargingStrategy.SMART,
                        "Uncoordinated": ChargingStrategy.UNCOORDINATED,
                        "V2G": ChargingStrategy.V2G,
                    }
                    result = run_scenario_e2(strategy=strat_map[strategy_e2], **scenario_kwargs)
                elif scenario_key == "M1":
                    result = run_scenario_m1(adaptive_signals=adaptive_m1, **scenario_kwargs)
                elif scenario_key == "T1":
                    strat_map = {
                        "Dynamic": SlicingStrategy.DYNAMIC,
                        "Static": SlicingStrategy.STATIC,
                    }
                    result = run_scenario_t1(strategy=strat_map[strategy_t1], **scenario_kwargs)
                elif scenario_key == "E2M1":
                    strat_map = {
                        "Smart": ChargingStrategy.SMART,
                        "Uncoordinated": ChargingStrategy.UNCOORDINATED,
                        "V2G": ChargingStrategy.V2G,
                    }
                    result = run_scenario_e2m1(
                        coupled=coupled_e2m1,
                        charging_strategy=strat_map[strategy_e2m1],
                        **scenario_kwargs)

            elapsed = time.time() - t0
            status.update(label=f"Simulation completed in {elapsed:.1f}s",
                          state="complete", expanded=False)

        # Persist in session state so results survive widget interactions
        st.session_state["last_result"] = result
        st.session_state["last_scenario"] = scenario_key
        st.session_state["last_compare"] = compare_mode
        st.session_state["last_elapsed"] = elapsed
        st.session_state["last_log"] = log_stream.getvalue()

    except Exception as e:
        st.error(f"Simulation failed: {e}")
    finally:
        root_logger.removeHandler(handler)

# ---------------------------------------------------------------------------
# Display results (persisted across widget interactions)
# ---------------------------------------------------------------------------
if "last_result" in st.session_state and st.session_state.get("last_scenario") == scenario_key:
    result = st.session_state["last_result"]
    if result is not None:
        elapsed = st.session_state.get("last_elapsed", 0)
        st.success(f"Simulation completed in {elapsed:.1f}s")

        if st.session_state.get("last_compare"):
            _display_comparison(result, scenario_key)
        else:
            _display_report(result)

        log_output = st.session_state.get("last_log", "")
        if log_output:
            with st.expander("Simulation Log"):
                st.code(log_output, language="text")
elif not run_button:
    st.info("Configure the scenario in the sidebar and click **Run Simulation**.")
