# Scenario E2: Electric Vehicle Charging Infrastructure - Technical Documentation

## Overview

This document provides comprehensive technical documentation for Scenario E2, including all mathematical formulas, optimization algorithms, and core concepts used in the EV charging infrastructure simulation.

**Simulation Type**: IEEE 13-node distribution test feeder with EV charging impact  
**Time Horizon**: 24 hours  
**Time Resolution**: 5-minute intervals (288 timesteps)  
**Number of EVs**: 100 vehicles  
**Charging Infrastructure**: 20 Level 2 + 5 DC Fast stations

---

## 1. Grid Topology

### IEEE 13-Node Test Feeder

- **Configuration**: Modified IEEE 13-node distribution system
- **Network Type**: Radial distribution feeder
- **Voltage Level**: Medium voltage distribution
- **Node Allocation**:
  - Nodes 1-8: Residential areas (Level 2 charging)
  - Nodes 9-13: Commercial zones (DC fast charging)

### Grid Parameters

- **Total Grid Capacity**: 5000 kW
- **Base Load** (without EV): 2000 kW average
- **Number of Nodes**: 13

---

## 2. Electric Vehicle Model

### 2.1 Battery Characteristics

**Battery Capacity Distribution**:
$$E_{battery} \sim U(40, 100) \text{ kWh}$$

Where $U(a, b)$ represents a uniform distribution between $a$ and $b$.

**State of Charge (SOC) Constraints**:
$$SOC_{min} = 0.10 \quad (10\%)$$
$$SOC_{max} = 0.90 \quad (90\%)$$
$$SOC_{target} = 0.80 \quad (80\%)$$

**Initial SOC** (upon arrival):
$$SOC_{initial} \sim U(0.2, 0.5)$$

Represents vehicles arriving after a trip with depleted battery.

### 2.2 Charging Parameters

**Onboard Charger Limit**:
$$P_{charger}^{max} = 11.0 \text{ kW}$$

This is the vehicle's onboard AC charger limitation.

**Charging Efficiency**:
$$\eta_{charge} = 0.90 \quad (90\%)$$

**Energy Stored During Charging**:
$$E_{charged} = \min(P_{charge} \cdot \Delta t \cdot \eta_{charge}, E_{available})$$

Where:
- $P_{charge}$ = Charging power (kW)
- $\Delta t$ = Time step duration (hours)
- $E_{available}$ = Available battery capacity = $(SOC_{max} - SOC_{current}) \cdot E_{battery}$

**SOC Update (Charging)**:
$$SOC_{new} = SOC_{current} + \frac{E_{charged}}{E_{battery}}$$

**Actual Charging Power** (limited by multiple factors):
$$P_{charge}^{actual} = \min(P_{requested}, P_{charger}^{max}, P_{station}^{max}, \frac{E_{available}}{\Delta t \cdot \eta_{charge}})$$

### 2.3 Vehicle-to-Grid (V2G) Model

**V2G Capability**: 50% of vehicles are V2G-enabled
$$P_{v2g} = \begin{cases} 
U(0,1) > 0.5 & \text{V2G capable} \\
\text{otherwise} & \text{Not V2G capable}
\end{cases}$$

**Maximum Discharge Rate**:
$$P_{discharge}^{max} = \begin{cases} 
10.0 \text{ kW} & \text{if V2G capable} \\
0.0 \text{ kW} & \text{otherwise}
\end{cases}$$

**Energy Discharged (V2G)**:
$$E_{discharged} = \min(P_{discharge} \cdot \Delta t, E_{available}^{discharge})$$

Where:
- $E_{available}^{discharge}$ = $(SOC_{current} - SOC_{min}) \cdot E_{battery}$

**SOC Update (Discharging)**:
$$SOC_{new} = SOC_{current} - \frac{E_{discharged}}{E_{battery}}$$

**Grid Power Provided** (accounting for losses):
$$P_{grid}^{v2g} = \frac{E_{discharged}}{\Delta t \cdot \eta_{charge}}$$

The discharge process has conversion losses similar to charging.

### 2.4 Energy Need Calculation

**Remaining Energy Need**:
$$E_{need} = \max(0, (SOC_{target} - SOC_{current}) \cdot E_{battery})$$

**Available Charging Time**:
$$T_{available} = \max(0, \frac{t_{departure} - t_{current}}{3600})$$

This is critical for smart charging optimization.

---

## 3. Charging Station Models

### 3.1 Level 2 Charger (Residential)

**Specifications**:
- **Quantity**: 20 stations
- **Location**: Nodes 1-8 (residential areas)
- **Power Rating**: $P_{L2} = 7.2$ kW
- **Ports per Station**: 1
- **Voltage**: 240V AC
- **Use Case**: Overnight home charging

### 3.2 DC Fast Charger (Commercial)

**Specifications**:
- **Quantity**: 5 stations
- **Location**: Nodes 9-13 (commercial zones)
- **Power Rating**: $P_{DCFC} = 50.0$ kW
- **Ports per Station**: 2
- **Voltage**: DC high voltage
- **Use Case**: Rapid daytime charging

### 3.3 Station Constraints

**Available Ports**:
$$N_{available} = N_{total} - N_{occupied}$$

A vehicle can only connect if $N_{available} > 0$.

**Power Delivery**:
$$P_{delivered} = \min(P_{station}^{max}, P_{vehicle}^{max}, P_{requested})$$

---

## 4. Arrival and Departure Patterns

### 4.1 Residential Charging Pattern (80% of EVs)

**Arrival Time** (returning from work):
$$t_{arrival} \sim \mathcal{N}(18.5, 1.0) \text{ hours}$$

Clipped to range $[17, 20]$ hours.

Where $\mathcal{N}(\mu, \sigma)$ is a normal distribution with mean $\mu$ and standard deviation $\sigma$.

**Departure Time** (leaving for work next day):
$$t_{departure} \sim \mathcal{N}(8.0, 0.5) \text{ hours}$$

Clipped to range $[7, 9]$ hours.

If $t_{departure} < t_{arrival}$, then $t_{departure} := t_{departure} + 24$ (next day).

**Connection Duration**:
$$T_{connected} = t_{departure} - t_{arrival} \approx 12-14 \text{ hours}$$

### 4.2 Commercial Fast Charging Pattern (20% of EVs)

**Arrival Time** (daytime):
$$t_{arrival} \sim U(8, 18) \text{ hours}$$

**Connection Duration** (short stop):
$$T_{connected} \sim U(0.5, 1.0) \text{ hours (30-60 minutes)}$$

**Departure Time**:
$$t_{departure} = t_{arrival} + T_{connected}$$

---

## 5. Time-of-Use (TOU) Tariff Structure

### Pricing Periods

**Off-Peak** (00:00-07:00, 23:00-24:00):
$$c_{off-peak} = 0.08 \text{ USD/kWh}$$

**Mid-Peak** (07:00-17:00, 21:00-23:00):
$$c_{mid-peak} = 0.12 \text{ USD/kWh}$$

**On-Peak** (17:00-21:00):
$$c_{on-peak} = 0.20 \text{ USD/kWh}$$

### Price Function

$$c(h) = \begin{cases} 
0.08 & \text{if } 0 \leq h < 7 \text{ or } 23 \leq h < 24 \\
0.20 & \text{if } 17 \leq h < 21 \\
0.12 & \text{otherwise}
\end{cases}$$

### Charging Cost Calculation

**Total Charging Cost per Vehicle**:
$$C_{charge} = \sum_{t=0}^{T} E_{charged}(t) \cdot c(h_t)$$

**V2G Revenue** (20% premium for grid support):
$$R_{v2g} = \sum_{t=0}^{T} E_{discharged}(t) \cdot c(h_t) \cdot 1.2$$

**Net Cost**:
$$C_{net} = C_{charge} - R_{v2g}$$

---

## 6. Charging Strategies

### 6.1 Uncoordinated Charging

**Strategy**: Charge immediately at maximum available power upon arrival.

**Power Allocation**:
$$P_{EV,i}(t) = \begin{cases} 
\min(P_{station}^{max}, P_{charger,i}^{max}) & \text{if } SOC_i < SOC_{target} \\
0 & \text{otherwise}
\end{cases}$$

**Characteristics**:
- Simple "plug-and-charge" behavior
- No grid awareness
- Potential for peak load coincidence
- Maximum convenience for users
- Can cause transformer overloads

**Peak Load Problem**:
When multiple EVs arrive simultaneously (e.g., 18:00), all start charging at once, creating a sharp peak that coincides with residential evening peak.

### 6.2 Smart Charging (Coordinated)

**Objective**: Minimize grid impact while ensuring all vehicles reach target SOC before departure.

**Optimization Problem**:
$$\min_{P_{i}(t)} \quad \sum_{t} \left[ P_{total}(t) - P_{capacity} \right]^+ + \alpha \sum_{i,t} P_i(t) \cdot c(t)$$

Subject to:
$$\sum_{t=t_{arrival,i}}^{t_{departure,i}} P_i(t) \cdot \Delta t \cdot \eta \geq E_{need,i} \quad \forall i$$
$$0 \leq P_i(t) \leq \min(P_{station}, P_{charger,i}) \quad \forall i,t$$
$$SOC_{min} \leq SOC_i(t) \leq SOC_{max} \quad \forall i,t$$

Where $(x)^+ = \max(0, x)$ penalizes exceeding grid capacity.

**Priority-Based Allocation**:

**Urgency Score**:
$$U_i(t) = \frac{E_{need,i}(t)}{T_{available,i}(t)}$$

Higher urgency means less time to charge more energy.

**Price Factor**:
$$F_{price}(t) = \begin{cases} 
1.0 & \text{if } c(t) < 0.15 \\
0.5 & \text{otherwise (peak hours)}
\end{cases}$$

**Overall Priority**:
$$\pi_i(t) = U_i(t) \cdot F_{price}(t)$$

**Allocation Algorithm**:
1. Calculate priority for all connected vehicles
2. Sort vehicles by priority (descending)
3. Allocate available grid capacity sequentially
4. Higher priority vehicles get power first

**Available Grid Capacity**:
$$P_{available}(t) = \max(0, P_{capacity} - P_{base}(t))$$

**Power Allocation**:
$$P_i(t) = \begin{cases} 
\min(P_{station}, P_{charger,i}, P_{available}^{remaining}) & \text{if vehicle } i \text{ has highest priority} \\
0 & \text{if no capacity remaining}
\end{cases}$$

$$P_{available}^{remaining} := P_{available}^{remaining} - P_i(t)$$

### 6.3 Vehicle-to-Grid (V2G) Strategy

**Extension of Smart Charging** with bidirectional power flow.

**V2G Activation Criteria**:
1. Vehicle is V2G-capable
2. Current hour is peak period: $17 \leq h < 21$
3. $SOC > SOC_{min} + \delta$ (safety margin, $\delta = 0.1$)
4. Grid price is high: $c(h) \geq c_{on-peak}$

**Discharge Power**:
$$P_{v2g,i}(t) = \min(P_{discharge,i}^{max}, P_{requested}^{v2g})$$

Where $P_{requested}^{v2g}$ is determined by grid support needs.

**Energy Constraint**:
Vehicle must still reach $SOC_{target}$ by departure:
$$SOC_i(t_{departure}) \geq SOC_{target}$$

This ensures V2G participation doesn't compromise user needs.

---

## 7. Transformer Loading Model

### Transformer Specifications

**Residential Transformers** (Nodes 1-8):
$$S_{rated} \sim U(150, 300) \text{ kVA}$$

**Commercial Transformers** (Nodes 9-13):
$$S_{rated} \sim U(500, 1000) \text{ kVA}$$

### Loading Calculation

**Apparent Power**:
$$S = \frac{P}{PF}$$

Where:
- $P$ = Active power (kW)
- $PF$ = Power factor = 0.95 (typical)

**Loading Percentage**:
$$L_{transformer}(\%) = \frac{S}{S_{rated}} \times 100$$

**Overload Condition**:
$$\text{Overload} = \begin{cases} 
\text{True} & \text{if } L_{transformer} > 100\% \\
\text{False} & \text{otherwise}
\end{cases}$$

### Load Distribution

**Simplified Node Load**:
$$P_{node}(t) = \frac{P_{total}(t)}{N_{nodes}} = \frac{P_{total}(t)}{13}$$

In a more detailed model, load would be distributed based on actual vehicle locations.

**Total Load**:
$$P_{total}(t) = P_{base}(t) + \sum_{i=1}^{N_{EV}} P_{EV,i}(t)$$

---

## 8. Base Load Profile

**Time-Varying Load Factor**:
$$\lambda_{base}(h) = \begin{cases} 
0.50 & \text{if } 0 \leq h < 6 & \text{(Night)} \\
0.75 & \text{if } 6 \leq h < 9 & \text{(Morning)} \\
0.80 & \text{if } 9 \leq h < 17 & \text{(Daytime)} \\
1.00 & \text{if } 17 \leq h < 22 & \text{(Evening Peak)} \\
0.60 & \text{if } 22 \leq h < 24 & \text{(Late Evening)}
\end{cases}$$

**Base Load**:
$$P_{base}(t) = P_{base}^{rated} \cdot \lambda_{base}(h_t)$$

Where $P_{base}^{rated} = 2000$ kW.

---

## 9. Voltage Deviation Model

**Simplified Voltage Deviation**:
$$\Delta V(t) = \min\left(0.05, \frac{P_{total}(t)}{P_{capacity}} \times 0.05\right)$$

This is a highly simplified model. In reality:
$$V_{node,i} = V_{source} - Z_{i} \cdot I_i$$

Where:
- $V_{source}$ = Substation voltage
- $Z_i$ = Impedance from source to node $i$
- $I_i$ = Current at node $i$

**Voltage Limits** (ANSI C84.1):
$$0.95 \leq V \leq 1.05 \text{ p.u.}$$

---

## 10. Performance Metrics

### 10.1 Energy Metrics

**Total Energy Charged (24h)**:
$$E_{charged}^{total} = \sum_{i=1}^{N_{EV}} \sum_{t=0}^{T} P_{charge,i}(t) \cdot \Delta t$$

**Total Energy Discharged (V2G)**:
$$E_{discharged}^{total} = \sum_{i=1}^{N_{EV}} \sum_{t=0}^{T} P_{discharge,i}(t) \cdot \Delta t$$

**Average Final SOC**:
$$\overline{SOC}_{final} = \frac{1}{N_{EV}} \sum_{i=1}^{N_{EV}} SOC_i(t_{final})$$

### 10.2 Grid Impact Metrics

**Peak Load**:
$$P_{peak} = \max_{t \in [0,T]} P_{total}(t)$$

**Peak Load Reduction** (Smart vs Uncoordinated):
$$\Delta P_{peak} = P_{peak}^{uncoord} - P_{peak}^{smart}$$

**Load Factor**:
$$LF = \frac{\overline{P}_{total}}{P_{peak}}$$

Higher load factor indicates more efficient grid utilization.

### 10.3 Transformer Metrics

**Maximum Loading**:
$$L_{max} = \max_{i \in [1,N_{trans}]} \max_{t \in [0,T]} L_{transformer,i}(t)$$

**Average Loading**:
$$\overline{L} = \frac{1}{N_{trans} \times T} \sum_{i=1}^{N_{trans}} \sum_{t=0}^{T} L_{transformer,i}(t)$$

**Total Overload Events**:
$$N_{overload} = \sum_{i=1}^{N_{trans}} \sum_{t=0}^{T} \mathbb{1}(L_{transformer,i}(t) > 100\%)$$

### 10.4 Economic Metrics

**Total Charging Cost**:
$$C_{total} = \sum_{i=1}^{N_{EV}} C_{net,i}$$

**Average Cost per Vehicle**:
$$\overline{C}_{vehicle} = \frac{C_{total}}{N_{EV}}$$

**Cost Savings** (Smart vs Uncoordinated):
$$\Delta C = C_{total}^{uncoord} - C_{total}^{smart}$$

**V2G Revenue**:
$$R_{v2g}^{total} = \sum_{i=1}^{N_{EV}} E_{discharged,i} \cdot c_{avg} \cdot 1.2$$

---

## 11. Simulation Algorithm

### Pseudocode

```
INITIALIZE:
  Create 100 EVs (40-100 kWh, initial SOC 20-50%)
  Create 20 Level 2 stations (7.2 kW, nodes 1-8)
  Create 5 DC Fast stations (50 kW, 2 ports, nodes 9-13)
  Create 13 transformers
  Generate arrival/departure patterns
  
FOR t = 0 TO 86400 STEP 300:  // 24 hours, 5-min steps
  hour = t / 3600
  
  // Handle arrivals/departures
  FOR each vehicle:
    IF t ≈ arrival_time AND not connected:
      Find available station and connect
    IF t ≥ departure_time AND connected:
      Disconnect from station
  
  // Calculate base load
  P_base = calculate_base_load(hour)
  
  // Get electricity price
  price = tariff.get_price(hour)
  
  // Determine charging strategy
  IF strategy == UNCOORDINATED:
    power_allocation = uncoordinated_charging()
  ELSE IF strategy == SMART or V2G:
    power_allocation = smart_controller.optimize(t, P_base, P_capacity)
  
  // Apply charging/discharging
  total_ev_load = 0
  FOR each vehicle:
    IF vehicle.id in power_allocation:
      P = power_allocation[vehicle.id]
      IF P > 0:  // Charging
        P_actual = vehicle.charge(P, Δt, price)
        total_ev_load += P_actual
      ELSE IF P < 0 AND strategy == V2G:  // Discharging
        IF hour in [17, 21):
          P_discharged = vehicle.discharge(|P|, Δt, price)
          total_ev_load -= P_discharged
  
  // Calculate total load
  P_total = P_base + total_ev_load
  P_peak = MAX(P_peak, P_total)
  
  // Transformer loading
  FOR each transformer:
    P_node = P_total / num_nodes
    loading = transformer.calculate_loading(P_node)
  
  // Voltage deviation
  voltage_dev = MIN(0.05, P_total / P_capacity * 0.05)
  
  // Store metrics
  RECORD(P_base, total_ev_load, P_total, loading[], voltage_dev)
  
  // Time advancement
  IF use_helics:
    current_time = helics_request_time(t + 300)
  ELSE:
    current_time = t + 300

// Calculate final metrics
total_cost = SUM(vehicle.charging_cost for all vehicles)
avg_soc = MEAN(vehicle.soc for all vehicles)
GENERATE_REPORT()
```

---

## 12. Strategy Comparison

### Expected Outcomes

**Uncoordinated Charging**:
- ✗ Highest peak load (coincides with evening peak)
- ✗ More transformer overloads
- ✗ Higher overall cost (charging during peak hours)
- ✓ Simplest implementation
- ✓ Maximum user convenience

**Smart Charging**:
- ✓ Reduced peak load (shifted to off-peak)
- ✓ Fewer transformer overloads
- ✓ Lower charging costs (optimized for TOU)
- ✓ Better grid utilization
- ✗ Requires coordination infrastructure

**V2G Strategy**:
- ✓ Lowest peak load (V2G support during peak)
- ✓ Additional grid flexibility
- ✓ Revenue for EV owners
- ✓ Enhanced grid stability
- ✗ Increased battery degradation
- ✗ Most complex implementation

---

## 13. Key Assumptions and Limitations

### Assumptions

1. **Perfect Communication**: No delays or failures in charging control
2. **Deterministic Patterns**: Arrival/departure times follow known distributions
3. **Simplified Grid Model**: Linear voltage drop, uniform load distribution
4. **No Driving During Day**: Vehicles stay connected once parked
5. **Perfect Forecasting**: Controller knows all future arrivals
6. **No Battery Degradation**: V2G cycling has no long-term impact modeled
7. **Fixed Tariff**: TOU prices don't change during simulation
8. **No Demand Charges**: Only energy charges considered

### Limitations

1. **Grid Model**: Simplified 13-node, no detailed power flow
2. **Battery Model**: No temperature, degradation, or state-of-health
3. **No Uncertainty**: Actual departure times might deviate
4. **No User Behavior**: Users always comply with smart charging signals
5. **Single Day**: No multi-day patterns or weekend effects
6. **No Renewable Integration**: Could couple with Scenario E1
7. **Uniform Vehicles**: Limited diversity in EV models
8. **No Queuing**: Assumes sufficient station availability

---

## 14. Future Enhancements

### Model Extensions

1. **Stochastic Optimization**: Handle uncertainty in departures
2. **Battery Degradation**: Model capacity fade from cycling
3. **Dynamic Pricing**: Real-time pricing with demand response
4. **Detailed Power Flow**: AC power flow with voltage regulation
5. **Multi-Day Simulation**: Weekly patterns and learning
6. **Renewable Integration**: Coordinate with solar/wind (Scenario E1)
7. **Heterogeneous Fleet**: Mix of BEVs, PHEVs, different models

### Advanced Features

1. **Machine Learning**: Predict arrival/departure patterns
2. **Robust Optimization**: Handle worst-case scenarios
3. **Game Theory**: Model competing charging strategies
4. **Market Participation**: EVs in energy/ancillary services markets
5. **Fast Charging Optimization**: Thermal management
6. **Distribution System State Estimation**: Real-time grid monitoring

---

## 15. Validation Metrics

### Energy Balance Verification

$$E_{charged}^{total} - E_{discharged}^{total} = \sum_{i=1}^{N_{EV}} (SOC_i^{final} - SOC_i^{initial}) \cdot E_{battery,i}$$

### Power Balance at Each Timestep

$$P_{total}(t) = P_{base}(t) + \sum_{i=1}^{N_{EV}} P_{charge,i}(t) - \sum_{i=1}^{N_{EV}} P_{discharge,i}(t)$$

### SOC Feasibility

$$\forall i,t: \quad SOC_{min} \leq SOC_i(t) \leq SOC_{max}$$

### Charging Requirement Satisfaction

$$\forall i: \quad SOC_i(t_{departure,i}) \geq SOC_{target} \text{ (desired)}$$

Percentage of vehicles achieving target SOC should be reported.

---

## 16. References and Standards

### EV Charging Standards

- **SAE J1772**: Level 1 and Level 2 AC charging
- **SAE J3068**: Level 2 charging specifications
- **CHAdeMO**: DC fast charging protocol
- **CCS (Combined Charging System)**: DC fast charging
- **ISO 15118**: Vehicle-to-Grid communication

### Grid Standards

- **IEEE 13-Node Test Feeder**: Standard distribution test case
- **ANSI C84.1**: Voltage ratings
- **IEEE 1547**: Interconnection for distributed resources
- **IEEE 2030.1.1**: V2G interconnection and interoperability

### Optimization References

- Electric vehicle smart charging algorithms
- Priority-based charging scheduling
- Time-of-use optimization strategies
- V2G aggregation and control

---

## Appendix: Notation Table

| Symbol | Description | Units |
|--------|-------------|-------|
| $P$ | Active power | kW |
| $E$ | Energy | kWh |
| $S$ | Apparent power | kVA |
| $SOC$ | State of charge | - (0-1) |
| $\eta$ | Efficiency | - (0-1) |
| $c$ | Electricity price | USD/kWh |
| $h$ | Hour of day | hours (0-24) |
| $t$ | Time | seconds |
| $\Delta t$ | Time step | hours (1/12) |
| $L$ | Transformer loading | % |
| $U(a,b)$ | Uniform distribution | - |
| $\mathcal{N}(\mu,\sigma)$ | Normal distribution | - |
| $PF$ | Power factor | - (0-1) |
| $\pi$ | Priority score | - |
| $U$ | Urgency score | kWh/hour |

---

**Document Version**: 1.0  
**Last Updated**: January 11, 2026  
**Simulation Code**: scenario_e2.py  
**Related Scenarios**: E1 (Smart Grid), E4 (Energy-Mobility Integration)
