# Cross-Domain Scenario E2+M1: Energy–Mobility Integration — Technical Documentation

## Overview

This document provides comprehensive technical documentation for the first cross-domain scenario, E2+M1, which couples the EV charging infrastructure model (E2) with the urban traffic management model (M1). The scenario demonstrates that treating energy and mobility as independent domains produces inaccurate system-level predictions, and that physically grounded coupling reveals important interdependencies.

### System Configuration

| Parameter | Value |
|-----------|-------|
| **Network** | Shared 5×5 grid with 25 signalized intersections (from M1) |
| **Intersection Spacing** | 1250 m |
| **Electric Vehicles** | 500 EVs navigating to charging stations |
| **Background Vehicles** | 2000 non-EV traffic vehicles |
| **Charging Stations** | 5 DC-fast (inner grid) + 8 Level 2 (perimeter) |
| **Total Charging Ports** | 52 (20 DC-fast + 32 L2) |
| **Simulation Duration** | 3 hours (10,800 seconds) |
| **Base Time Step** | 1 second (M1 native resolution) |
| **Charging Update Interval** | 300 seconds (5 minutes, E2 compatible) |
| **Speed Limit** | 50 km/h (13.9 m/s) |
| **Comparison Modes** | Coupled vs. Uncoupled |

---

## 1. Cross-Domain Coupling Architecture

### 1.1 Coupling Hypothesis

The central hypothesis is that the physical travel time of EVs through the urban traffic network materially affects charging infrastructure utilization and grid load profiles. In an uncoupled (siloed) approach, EV arrival at charging stations is modeled independently of traffic conditions. The coupled approach integrates both domains on a shared network, revealing emergent interactions.

### 1.2 Shared Infrastructure

Both domains operate on the same 5×5 grid graph $G = (V, E)$ from M1:

$$V = \{(i, j) \mid 0 \leq i, j < 5\}$$
$$|V| = 25 \text{ intersections}, \quad |E| = 40 \text{ bidirectional links}$$

Charging stations are placed at a subset of intersections $S \subset V$, serving as destination nodes for EVs within the traffic simulation.

### 1.3 Coupling Mechanism

The coupling is bidirectional:

**Energy → Mobility**: EV agents are physical vehicles in the traffic network. They consume road capacity, wait at signals, and contribute to congestion that affects background traffic.

**Mobility → Energy**: Traffic conditions determine EV arrival patterns at charging stations. Congested routes delay arrivals, producing staggered charging demand rather than the simultaneous demand assumed by uncoupled models.

### 1.4 Coupling vs. Uncoupling Modes

| Aspect | Coupled | Uncoupled |
|--------|---------|-----------|
| EV travel | Navigate through traffic (M1 mechanics) | Teleport to station at departure time |
| Signal interaction | EVs wait at red lights | EVs bypass traffic network |
| Congestion contribution | EVs add to intersection queues | EVs absent from traffic |
| Arrival pattern | Staggered by traffic conditions | Simultaneous after departure |
| Background traffic impact | Affected by 500 additional vehicles | No EV interference |
| Emissions from driving | EVs contribute driving CO₂ | Zero EV driving emissions |

---

## 2. Component Models

### 2.1 EV Traffic Vehicle (EVTrafficVehicle)

The `EVTrafficVehicle` class inherits from M1's `Vehicle` for traffic movement and holds an E2 `ElectricVehicle` instance for battery state. A finite state machine governs the EV lifecycle:

#### Phase State Machine

$$
\text{DRIVING\_TO\_STATION} \xrightarrow{\text{arrive at station}} \text{CHARGING} \xrightarrow{\text{SOC target met}} \text{DRIVING\_BACK} \xrightarrow{\text{arrive at return dest.}} \text{DONE}
$$

**State Transitions**:

1. **DRIVING_TO_STATION → CHARGING**: When the EV reaches its designated station intersection AND a charging port is available. If no port is free, the EV remains at the intersection in a virtual queue.

2. **CHARGING → DRIVING_BACK**: When $SOC \geq SOC_{target}$ or the maximum dwell time (2 hours) expires. The EV disconnects and is assigned a return route.

3. **DRIVING_BACK → DONE**: When the EV reaches its randomly assigned return destination.

### 2.2 Vehicle Parameters

**Battery Model** (from E2):
$$E_{battery} \sim U(40, 100) \text{ kWh}$$
$$SOC_{initial} \sim U(0.2, 0.5)$$
$$SOC_{target} = 0.80$$

**Traffic Model** (from M1):
$$v_{max} = 13.9 \text{ m/s} \quad (50 \text{ km/h})$$
$$t_{link} = \frac{d_{spacing}}{v_{max}} = \frac{1250}{13.9} \approx 90 \text{ s}$$

**Departure Pattern**:
$$t_{dep} \sim U(0, 3600) \text{ s}$$

Staggered over the first hour, identical for both coupled and uncoupled modes (same RNG seed).

### 2.3 Charging Station Placement

Stations are placed strategically on the shared grid:

**DC-Fast Stations** (5 stations, 4 ports each, 50 kW):
$$S_{DC} = \{(1,1), (1,3), (2,2), (3,1), (3,3)\}$$

Positioned at inner intersections for central accessibility.

**Level 2 Stations** (8 stations, 4 ports each, 7.2 kW):
$$S_{L2} = \{(0,0), (0,2), (0,4), (2,0), (2,4), (4,0), (4,2), (4,4)\}$$

Positioned at perimeter intersections for spatial coverage.

**Total Infrastructure**:
$$|S| = 13 \text{ stations}, \quad P_{total} = 52 \text{ ports}$$

### 2.4 Station Assignment

Each EV is assigned to the nearest station using Manhattan distance with random tie-breaking:

$$s^*(v) = \arg\min_{s \in S \setminus \{o_v\}} \left( d_{Manhattan}(o_v, s), \; \xi_s \right)$$

where $o_v$ is the EV's origin, $d_{Manhattan}(a,b) = |a_x - b_x| + |a_y - b_y|$, and $\xi_s \sim U(0,1)$ is a random tie-breaker. This distributes EVs across both DC-fast and L2 stations when multiple stations are equidistant.

---

## 3. Traffic Simulation (from M1)

### 3.1 Vehicle Movement

All vehicles (EVs + background) follow the M1 movement model:

1. **Departure**: Vehicle activates at $t_{dep}$
2. **Intersection traversal**: At each intersection, vehicle waits for a green signal on its desired direction
3. **Link travel**: Upon green signal, vehicle enters the link with countdown $t_{link} = 90$ s
4. **Arrival**: When the vehicle reaches its destination intersection, it is marked complete

### 3.2 Adaptive Signal Control

All intersections use adaptive control (from M1):

$$T_{green} = T_{min} + (T_{max} - T_{min}) \cdot \frac{Q_{phase}}{Q_{NS} + Q_{EW}}$$

with $T_{min} = 15$ s and $T_{max} = 90$ s.

In coupled mode, EV vehicles contribute to directional queue counts $Q_{NS}$ and $Q_{EW}$, influencing signal timing allocation. In uncoupled mode, only background vehicles influence signals.

### 3.3 Emissions Model

$$\Delta E_{CO_2} = \begin{cases} \alpha_{idle} \cdot \Delta t & v < 1.0 \text{ m/s} \\ \alpha_{move} \cdot v \cdot \Delta t & v \geq 1.0 \text{ m/s} \end{cases}$$

with $\alpha_{idle} = 2.31$ g/s and $\alpha_{move} = 0.15$ g/m.

In coupled mode, EVs generate driving emissions. In uncoupled mode, only background vehicles produce emissions (EVs teleport without driving).

---

## 4. Charging Simulation (from E2)

### 4.1 Charging Logic

Charging is executed every 300 time steps (5-minute intervals), matching E2's temporal resolution:

$$\Delta E_{charged} = P_{allocated} \cdot \eta \cdot \Delta t_{charge}$$

where $\eta = 0.95$ is the charging efficiency and $\Delta t_{charge} = 5$ min.

### 4.2 Smart Charging Strategy

The smart charging controller (from E2) allocates available grid capacity using urgency-based priority:

$$U_i(t) = \frac{E_{need,i}(t)}{T_{available,i}(t)} \cdot F_{price}(t)$$

Vehicles with higher urgency (more energy needed in less time) receive priority allocation from the remaining grid headroom:

$$P_{available} = P_{grid}^{max} - P_{base}(t)$$

### 4.3 Base Load Profile

$$P_{base}(h) = \begin{cases}
2000 \times 0.50 \text{ kW} & 0 \leq h < 6 \\
2000 \times 0.75 \text{ kW} & 6 \leq h < 9 \\
2000 \times 0.80 \text{ kW} & 9 \leq h < 17 \\
2000 \times 1.00 \text{ kW} & 17 \leq h < 22 \\
2000 \times 0.60 \text{ kW} & 22 \leq h < 24
\end{cases}$$

### 4.4 Transformer Model

Each station has an associated distribution transformer with randomized capacity:

$$C_{transformer} \sim \begin{cases} U(500, 1000) \text{ kVA} & \text{DC-fast} \\ U(150, 300) \text{ kVA} & \text{Level 2} \end{cases}$$

Loading percentage and overload counting follow E2's transformer model.

### 4.5 Time-of-Use Tariff

$$c(h) = \begin{cases}
0.08 \text{ USD/kWh} & \text{off-peak} \\
0.12 \text{ USD/kWh} & \text{mid-peak} \\
0.20 \text{ USD/kWh} & \text{on-peak}
\end{cases}$$

---

## 5. Temporal Alignment

### 5.1 Multi-Rate Integration

The scenario reconciles two domain-native time scales:

| Domain | Native Resolution | Role in E2+M1 |
|--------|-------------------|----------------|
| M1 (Traffic) | 1 second | Base time step for all vehicle movement |
| E2 (Charging) | 5 minutes | Charging logic applied every 300 base steps |

The 1-second base step ensures traffic dynamics are captured at full fidelity. Charging decisions execute at their native 5-minute granularity, matching the E2 standalone behavior.

### 5.2 Simulation Loop

```
for each step (1s resolution):
    1. Update adaptive traffic signals (M1)
    2. Move all vehicles through network (M1)
    3. [Uncoupled only] Teleport departed EVs to stations
    4. Handle EV arrivals at station nodes
    5. [Every 300 steps] Execute charging logic (E2)
    6. Handle EV departures (prepare return trips)
    7. Transition completed return trips to DONE
    8. Collect queue metrics
    9. Advance simulation time
```

---

## 6. Performance Metrics

### 6.1 Traffic Metrics

**Background Completion Rate**:
$$R_{bg} = \frac{|\{v \in V_{bg} \mid v.\text{completed}\}|}{|V_{bg}|} \times 100\%$$

**Background Average Travel Time**:
$$\bar{T}_{travel}^{bg} = \frac{1}{|V_{bg}^{done}|} \sum_{v \in V_{bg}^{done}} T_{travel}(v)$$

**Background Average Delay**:
$$\bar{D}^{bg} = \frac{1}{|V_{bg}^{done}|} \sum_{v \in V_{bg}^{done}} D(v)$$

**Total Emissions**:
$$E_{total} = \sum_{v \in V_{all}} E_{CO_2}(v)$$

In coupled mode $V_{all}$ includes EVs; in uncoupled mode $V_{all} = V_{bg}$ only.

### 6.2 EV Travel Metrics

**Average EV Drive Time** (key coupling metric):
$$\bar{T}_{drive}^{EV} = \frac{1}{|V_{EV}^{arrived}|} \sum_{v \in V_{EV}^{arrived}} (t_{intersection}(v) - t_{dep}(v))$$

where $t_{intersection}$ is when the EV first reaches the station node. For uncoupled: $\approx 0$ s. For coupled: reflects actual traffic travel time.

**Average EV Queue Time**:
$$\bar{T}_{queue}^{EV} = \frac{1}{|V_{EV}^{connected}|} \sum_{v \in V_{EV}^{connected}} (t_{port}(v) - t_{intersection}(v))$$

**EVs at Station Node**: Count of EVs that physically reached the station intersection (regardless of port availability).

**EVs Connected**: Count of EVs that obtained a charging port.

### 6.3 Charging Metrics

**EVs Meeting SOC Target**:
$$N_{SOC} = |\{v \in V_{EV} \mid SOC(v) \geq SOC_{target}\}|$$

**Total Energy Charged**:
$$E_{charged} = \sum_{v \in V_{EV}} E_{charged}(v) \text{ [kWh]}$$

**Peak Grid Load**:
$$P_{peak} = \max_t \left( P_{base}(t) + P_{EV}(t) \right)$$

**Transformer Loading**:
$$L_{max} = \max_{i,t} \frac{P_i(t)}{C_i} \times 100\%$$

---

## 7. Simulation Algorithm

### 7.1 Initialization

```
1. Create shared 5×5 traffic network (M1)
2. Place 13 charging stations at designated intersections
3. Create 500 EVs with random origins, nearest-station assignment
4. Create 2000 background vehicles (M1)
5. [Coupled] Add EVs + background to traffic pool
   [Uncoupled] Add only background to traffic pool
6. Initialize smart charging controller (E2)
```

### 7.2 Main Loop (10,800 iterations)

```
while t < 10800:
    # Traffic domain (every step)
    update_adaptive_signals(all_vehicles_at_intersections)
    move_vehicles(all_vehicles, dt=1s)
    
    # Coupling point
    [uncoupled] teleport_departed_evs_to_stations()
    handle_ev_arrivals_at_stations(t)
    
    # Energy domain (every 300 steps)
    if step % 300 == 0:
        allocate_charging_power(smart_controller, t)
        charge_connected_evs(allocation, dt=300s)
    
    handle_ev_departures(t)
    collect_metrics()
    t += 1
```

### 7.3 Comparison Protocol

Both modes run with identical RNG seed (42), ensuring:
- Same EV origins, destinations, and battery parameters
- Same background vehicle routes and departures
- Same charging station placements and transformer capacities
- Only the coupling mechanism differs

---

## 8. Key Assumptions

1. **Grid topology**: Urban 5×5 grid identical to M1; no road closures or asymmetric capacities.
2. **Uniform speed**: All vehicles travel at the speed limit (50 km/h) on links; intersection delay is the sole source of variability.
3. **No en-route charging decision**: EVs are pre-assigned to their nearest station and do not reroute based on congestion or station occupancy.
4. **Charging occurs at station only**: No en-route or opportunistic charging.
5. **Return trips**: After charging, EVs drive to a random destination to model continued mobility.
6. **Port queuing**: EVs waiting at a full station remain at the intersection until a port opens; no balking or reneging.
7. **Same RNG seed**: Both coupled and uncoupled modes use seed(42) for fair comparison.

---

## 9. Validation Criteria

### 9.1 Coupling Effect Validation

The cross-domain scenario is valid if coupling produces statistically distinct outcomes:

| Metric | Expected Direction | Rationale |
|--------|-------------------|-----------|
| EV Drive Time | Coupled > Uncoupled | Traffic delays increase travel time |
| Total Emissions | Coupled > Uncoupled | EV driving adds CO₂ |
| EVs Meeting SOC | Coupled < Uncoupled | Less charging time available |
| Energy Charged | Coupled < Uncoupled | Fewer EVs complete charging cycle |
| Max Queue Length | Coupled ≥ Uncoupled | EVs add to intersection congestion |

### 9.2 Physical Consistency Checks

- All EVs must eventually reach their station node (within 3h, given max ~4-hop routes at ~90s/hop)
- SOC must remain within $[SOC_{min}, SOC_{max}]$ at all times
- Background traffic metrics must be reproducible under the same seed
- Energy charged must equal $\sum P \cdot \eta \cdot \Delta t$ for all connected intervals

### 9.3 Reference Results (seed=42, Smart charging)

| Metric | Uncoupled | Coupled | Delta |
|--------|-----------|---------|-------|
| Avg EV Drive Time (s) | 0.5 | 366.5 | +366.0 s |
| Avg EV Queue Time (s) | 3068.4 | 2863.7 | −204.7 s |
| EVs at Station Node | 500 | 500 | 0 |
| EVs Connected (port) | 155 | 150 | −5 |
| EVs Meeting SOC Target | 71 | 66 | −7.0% |
| Total Energy Charged (kWh) | 3189.4 | 3127.1 | −2.0% |
| Total Charging Cost (USD) | 255.15 | 250.17 | −$4.98 |
| Background Avg Travel (s) | 536.2 | 536.3 | +0.1 s |
| Total Emissions (kg CO₂) | 2246.1 | 2728.6 | +21.5% |
| Peak Grid Load (kW) | 2107.4 | 2107.4 | 0 |
| Max Queue Length | 9 | 9 | 0 |

**Key Finding**: Coupling adds an average 366 seconds of EV travel time, increases system emissions by 21.5%, and reduces the number of EVs reaching their SOC target by 7.0%. These effects are invisible to independent (uncoupled) domain simulations.

---

## 10. Implementation Notes

### 10.1 Class Hierarchy

```
BaseFederate (engine/base.py)
└── CrossDomainE2M1
    ├── uses: TrafficNetwork, TrafficSignal (from M1)
    ├── uses: ChargingStation, SmartChargingController, TransformerModel (from E2)
    └── contains: EVTrafficVehicle(M1.Vehicle) + ElectricVehicle (E2)
```

### 10.2 Reused Components

| Component | Source | Role in E2+M1 |
|-----------|--------|----------------|
| `TrafficNetwork` | M1 | Shared 5×5 grid, A* routing |
| `TrafficSignal` | M1 | Adaptive signal control at intersections |
| `Vehicle` | M1 | Base class for all vehicles (movement, emissions) |
| `ElectricVehicle` | E2 | Battery model (SOC, charge/discharge) |
| `ChargingStation` | E2 | Port management, charger types |
| `SmartChargingController` | E2 | Priority-based power allocation |
| `TransformerModel` | E2 | Grid equipment loading |
| `TimeOfUseTariff` | E2 | Pricing model |

### 10.3 Computational Complexity

- **Per time step**: $O(|V_{all}| \cdot |V|)$ for signal updates and vehicle movement
- **Per charging interval**: $O(|V_{EV}| \log |V_{EV}|)$ for priority sorting
- **Total**: $O(T \cdot N \cdot K)$ where $T = 10800$ steps, $N = 2500$ vehicles, $K = 25$ intersections
- **Runtime**: ~35 seconds per mode on a standard laptop

---

## 11. Extensions and Future Work

1. **Dynamic station selection**: EVs reroute to less congested stations based on real-time occupancy
2. **Battery degradation from driving**: SOC decreases during travel proportional to distance
3. **HELICS co-simulation deployment**: Run E2 and M1 as separate HELICS federates with message-based coupling
4. **Grid feedback to traffic**: Transformer overloads trigger charging curtailment, causing EVs to wait longer
5. **Multi-period analysis**: Extend to 24h to capture overnight residential charging + daytime traffic patterns

---

## 12. References and Standards

- **E2 model basis**: Adapted from IEEE 13-node test feeder EV impact studies
- **M1 model basis**: Agent-based traffic simulation with adaptive signal control
- **Co-simulation**: HELICS framework for multi-domain time synchronization
- **Emissions factors**: EPA MOVES model simplified two-state approximation

---

## Appendix: Notation Table

| Symbol | Description | Unit |
|--------|-------------|------|
| $G = (V, E)$ | Traffic network graph | — |
| $S$ | Set of charging station intersections | — |
| $S_{DC}$, $S_{L2}$ | DC-fast and L2 station subsets | — |
| $SOC$ | State of charge | — (fraction) |
| $E_{battery}$ | Battery capacity | kWh |
| $P_{DC}$ | DC-fast charging power | 50 kW |
| $P_{L2}$ | Level 2 charging power | 7.2 kW |
| $P_{base}(h)$ | Base electrical load at hour $h$ | kW |
| $P_{grid}^{max}$ | Grid feeder capacity | 2500 kW |
| $t_{dep}$ | Vehicle departure time | s |
| $t_{intersection}$ | EV arrival at station intersection | s |
| $t_{port}$ | EV connection to charging port | s |
| $T_{green}$ | Adaptive green time | s |
| $Q_{NS}$, $Q_{EW}$ | Directional queue counts | vehicles |
| $\alpha_{idle}$, $\alpha_{move}$ | Emission rate coefficients | g/s, g/m |
| $\eta$ | Charging efficiency | 0.95 |
| $U_i(t)$ | Charging urgency score | kW |
| $c(h)$ | Time-of-use tariff rate | USD/kWh |
