# Cross-Domain Scenario M1+T1: Mobility–Telecommunications Integration — Technical Documentation

## Overview

This document provides comprehensive technical documentation for the second cross-domain scenario, M1+T1, which couples the urban traffic management model (M1) with the 5G slice resource allocation model (T1). The scenario demonstrates that vehicle mobility patterns produce fundamentally different radio-access conditions than pedestrian-speed random-waypoint users, and that URLLC QoS degradation propagates back to traffic signal control through a bidirectional coupling loop.

### System Configuration

| Parameter | Value |
|-----------|-------|
| **Network** | Shared 5×5 grid with 25 signalized intersections (from M1) |
| **Intersection Spacing** | 1250 m |
| **Grid Extent** | 5000 m × 5000 m |
| **Connected Vehicles** | 200 vehicles each hosting one 5G UE |
| **Background Vehicles** | 2300 non-connected traffic vehicles |
| **gNB Count** | 3 (triangular layout scaled to 5000 m area) |
| **UE Slice Split** | 100 eMBB / 50 URLLC / 50 mMTC |
| **RBs per gNB** | 100 |
| **Simulation Duration** | 3 hours (10,800 seconds) |
| **Time Step** | 1 second (M1 native resolution) |
| **Speed Limit** | 50 km/h (13.9 m/s) |
| **Comparison Modes** | Coupled vs. Uncoupled |

---

## 1. Cross-Domain Coupling Architecture

### 1.1 Coupling Hypothesis

The central hypothesis is that vehicular mobility produces qualitatively different 5G radio conditions compared to the pedestrian-speed random-waypoint model used in standalone T1 simulations, and that the resulting URLLC QoS degradation meaningfully impacts traffic signal operation.

Two distinct effects are hypothesised:

1. **M1 → T1 (forward path)**: Vehicles traverse grid links at 50 km/h and cluster at red lights, creating spatially dense, temporally bursty handover loads that the random-waypoint model cannot replicate.
2. **T1 → M1 (feedback path)**: When URLLC QoS at a gNB falls below a threshold, adaptive signal control is disabled at nearby intersections, reverting those intersections to fixed-time operation and increasing queue lengths and travel delays.

### 1.2 Coordinate Mapping

The T1 radio model and M1 traffic network use different coordinate spaces. The mapping between grid coordinates $(i, j) \in \{0, \ldots, 4\}^2$ and radio coordinates $(x_m, y_m)$ is:

$$x_m = i \times d_{\text{spacing}}, \quad y_m = j \times d_{\text{spacing}}$$

where $d_{\text{spacing}} = 1250\,\text{m}$.  The M1 grid therefore spans $[0, 5000]\,\text{m}^2$ in both dimensions.

### 1.3 gNB Position Rescaling

The standalone T1 scenario places gNBs in a $2000\,\text{m} \times 2000\,\text{m}$ area. For the cross-domain scenario the positions are scaled to the $5000\,\text{m}$ grid extent:

| gNB | Standalone T1 Position (m) | Cross-Domain M1+T1 Position (m) | Nearest Grid Cell |
|-----|---------------------------|---------------------------------|-------------------|
| 0   | (500, 500)                | (1250, 1250)                    | (1, 1)            |
| 1   | (1500, 500)               | (3750, 1250)                    | (3, 1)            |
| 2   | (1000, 1500)              | (2500, 3750)                    | (2, 3)            |

### 1.4 Coupling vs. Uncoupling Modes

| Aspect | Coupled | Uncoupled |
|--------|---------|-----------|
| UE mobility | Vehicle position via `sync_position()` | Independent random waypoint |
| Handover pattern | Burst at signal releases, clustering at intersections | Smooth pedestrian-speed drift |
| URLLC feedback | Disables adaptive signals near degraded gNBs | No signal feedback |
| Signal operation | Mixed adaptive / fixed-time | Fully adaptive |
| Emissions | Elevated by fixed-time delay | Baseline adaptive |

---

## 2. Component Models

### 2.1 ConnectedVehicle

`ConnectedVehicle` extends `M1Vehicle` (from `scenario_m1.py`) with an embedded `MobileUser` (from `scenario_t1.py`).

```python
class ConnectedVehicle(M1Vehicle):
    def __init__(self, vehicle_id, origin, destination,
                 user: MobileUser, spacing_m: float = 1250.0):
        super().__init__(vehicle_id, origin, destination)
        self.user = user
        self._spacing_m = spacing_m

    def sync_position(self):
        col, row = self.current_position
        self.user.x = col * self._spacing_m
        self.user.y = row * self._spacing_m
```

After each M1 movement step, `sync_position()` projects the vehicle's integer grid coordinates onto the radio coordinate space, ensuring the path-loss calculation uses the correct physical distance to each gNB.

### 2.2 Traffic Signal Update with Degradation

The signal update loop re-implements M1's `update_signals` function to support per-intersection mode selection:

```
for each intersection pos:
    if coupled and pos in degraded_intersections:
        signal.update(dt, 1, 1)   # fixed-time: equal NS/EW demand
    else:
        compute ns_demand, ew_demand from vehicles at pos
        signal.update(dt, ns_demand, ew_demand)   # adaptive
```

Degraded intersections are those within `_COVERAGE_RADIUS_M = 1600 m` of a gNB that failed the URLLC QoS threshold in the previous step.

### 2.3 Radio Model (inherited from T1)

The path-loss model follows 3GPP Urban Macro (TS 38.901):

$$PL_{\text{UMa}}(d) = 128.1 + 37.6 \cdot \log_{10}(d_{\text{km}}) \quad [\text{dB}]$$

Received power at the UE:

$$P_{\text{rx}} = P_{\text{tx}} - PL + \xi_{\text{shadow}}, \quad \xi_{\text{shadow}} \sim \mathcal{N}(0, \sigma_s^2)$$

where $P_{\text{tx}} = 46\,\text{dBm}$ (macro gNB), $\sigma_s = 4\,\text{dB}$.

Handover is triggered when the candidate gNB exceeds the serving gNB by at least 3 dB (hysteresis), subject to a 1-second cooldown and $P_{\text{success}} = 0.95$.

### 2.4 Resource Block Allocation (inherited from T1)

Dynamic strategy allocates RBs proportional to slice demand with a minimum floor of 5 RBs:

$$\text{RB}_s = \max\!\left(5,\ \left\lfloor\frac{N_s \cdot r_s}{\sum_{s'} N_{s'} \cdot r_{s'}}\cdot R_{\text{total}}\right\rfloor\right)$$

where $N_s$ is the number of active users in slice $s$ at the gNB, $r_s$ is the per-user RB requirement ($r_{\text{eMBB}} = r_{\text{URLLC}} = 2$, $r_{\text{mMTC}} = 1$), and $R_{\text{total}} = 100$.

QoS is satisfied when $\lfloor \text{RB}_s / N_s \rfloor \geq r_s$.

---

## 3. QoS Feedback Mechanism

### 3.1 Per-gNB URLLC Satisfaction Rate

At each simulation step, after resource allocation, the per-gNB URLLC satisfaction rate is computed:

$$\rho_{\text{URLLC}}^{(k)} = \frac{\text{URLLC users with QoS satisfied at gNB } k}{\text{active URLLC users at gNB } k}$$

If $\rho_{\text{URLLC}}^{(k)} < \theta$ (default $\theta = 0.80$), gNB $k$ is declared degraded.

### 3.2 Intersection Degradation

For each degraded gNB $k$ at position $(g_x, g_y)$, all grid intersections within $r = 1600\,\text{m}$ are added to the degraded set:

$$\mathcal{D} = \left\{ (i,j) \;\middle|\; \sqrt{(i \cdot 1250 - g_x)^2 + (j \cdot 1250 - g_y)^2} \leq r \right\}$$

Signals at intersections in $\mathcal{D}$ receive `update(dt, 1, 1)` instead of the demand-weighted adaptive call, reducing throughput at those locations.

### 3.3 Degradation Metrics

| Metric | Definition |
|--------|-----------|
| `degradation_events` | Count of per-gNB URLLC threshold violations across all steps |
| `degradation_duration_s` | Sum over all time steps of $|\mathcal{D}|$ (seconds × intersections) |
| `affected_intersections` | Size of the union of all intersections ever added to $\mathcal{D}$ |

---

## 4. Mobility Model Differences

### 4.1 Vehicle vs. Random Waypoint Speed

| Parameter | M1+T1 Coupled | T1 Standalone |
|-----------|--------------|---------------|
| Speed | 50 km/h (13.9 m/s) on links | 0.5–2.0 m/s (pedestrian) |
| Motion | Discrete grid hops (1250 m links) | Continuous random waypoint |
| Stopping | Up to 90 s at red lights | Never stopped |
| Clustering | Dense at intersection nodes | Uniform spatial distribution |

### 4.2 Link Traversal Time

The M1 model computes link travel time as:

$$t_{\text{link}} = \frac{d_{\text{spacing}}}{v_{\text{max}}} = \frac{1250}{13.9} \approx 90\,\text{s}$$

A vehicle that departs at 50 km/h crosses a gNB cell boundary (approximately one grid link) roughly every 90 seconds, triggering a potential handover at each crossing. In contrast, a pedestrian-speed RWP user at 1.5 m/s would take approximately 833 seconds to traverse the same distance.

### 4.3 Burst Handover Effect

When a green phase releases vehicles stopped at an intersection, multiple vehicles near a cell boundary hand over simultaneously. This creates instantaneous demand spikes on both the source and target gNB that are absent from the smooth RWP mobility model.

---

## 5. Metrics Reference

### 5.1 Telecommunications Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| `qos_satisfaction_embb_pct` | % | Fraction of eMBB user-steps with $\lfloor\text{RB/user}\rfloor \geq 2$ |
| `qos_satisfaction_urllc_pct` | % | Fraction of URLLC user-steps meeting QoS threshold |
| `qos_satisfaction_mmtc_pct` | % | Fraction of active mMTC user-steps meeting QoS threshold |
| `overall_utilization_pct` | % | Ratio of RBs actually used to total available |
| `resource_waste_pct` | % | Complement of utilisation |
| `handover_attempts` | count | Total handover attempts across all UEs and steps |
| `handover_successes` | count | Handovers completed with $P = 0.95$ |
| `handover_failures` | count | Handovers that failed |
| `handover_success_rate_pct` | % | Successes / attempts |
| `handover_rate_per_min` | /min | Attempts per simulation minute |
| `load_imbalance_std_users` | users | Mean over time of per-step std dev of users-per-gNB |

### 5.2 Coupling / Degradation Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| `degradation_events` | count | Per-gNB below-threshold URLLC occurrences (summed across gNBs and steps) |
| `degradation_duration_s` | s | Combined intersection-degradation duration (∑ \|𝒟\| across steps) |
| `affected_intersections` | count | Distinct intersections ever in degraded set |

### 5.3 Traffic Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| `bg_completion_rate_pct` | % | Background vehicles that completed their trip |
| `bg_avg_travel_time_s` | s | Mean total travel time for completed background vehicles |
| `bg_avg_delay_s` | s | Mean signal-induced delay for completed background vehicles |
| `cv_avg_travel_time_s` | s | Mean travel time for completed connected vehicles |
| `total_emissions_kg_co2` | kg | Aggregate CO₂ across all 2500 vehicles |
| `max_queue_length` | vehicles | Peak instantaneous queue at any intersection |
| `avg_queue_length` | vehicles | Mean queue length averaged over intersections and time |

---

## 6. Public API

```python
from scenarios.scenario_m1t1 import run_scenario_m1t1, compare_coupling_modes_m1t1
from scenarios.scenario_t1 import SlicingStrategy

# Single run (coupled, dynamic slicing)
report = run_scenario_m1t1(
    use_helics=False,
    coupled=True,
    slicing_strategy=SlicingStrategy.DYNAMIC,
    num_connected=200,
    num_background=2300,
    sim_duration_hours=3,
)

# Compare coupled vs uncoupled (reproducible with seed 42)
results = compare_coupling_modes_m1t1(
    slicing_strategy=SlicingStrategy.DYNAMIC,
)
uncoupled_metrics = results["uncoupled"]["metrics"]
coupled_metrics   = results["coupled"]["metrics"]
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `coupled` | bool | `True` | Enable M1↔T1 bidirectional coupling |
| `num_connected` | int | 200 | Connected vehicles (each hosts one UE) |
| `num_background` | int | 2300 | Non-connected background vehicles |
| `grid_size` | int | 5 | N for the N×N traffic grid |
| `sim_duration_hours` | int | 3 | Simulation length in hours |
| `slicing_strategy` | SlicingStrategy | DYNAMIC | RB allocation policy |
| `urllc_qos_threshold` | float | 0.80 | URLLC satisfaction rate below which degradation is triggered |

---

## 7. File Dependencies

```
scenario_m1t1.py
├── engine/base.py          (BaseFederate, print_report)
├── scenarios/scenario_m1.py (TrafficNetwork, Vehicle, create_random_vehicles,
│                              move_vehicles_step, collect_queue_lengths)
└── scenarios/scenario_t1.py (GNodeB, MobileUser, SliceType, SlicingStrategy,
                               SLICE_CONFIG, SliceResourceAllocator)
```

No modifications to `scenario_m1.py` or `scenario_t1.py` were required.
