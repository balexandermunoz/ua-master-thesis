# Scenario E1: Smart Grid with Renewable Integration - Technical Documentation

## Overview

This document provides a comprehensive technical explanation of Scenario E1, including all mathematical formulas, algorithms, and core concepts used in the simulation.

**Simulation Type**: IEEE 33-bus distribution network with distributed energy resources (DER)  
**Time Horizon**: 24 hours  
**Time Resolution**: 15-minute intervals (96 timesteps)  
**Renewable Penetration**: 40% of total load

---

## 1. Grid Topology

### IEEE 33-Bus Distribution System

- **Configuration**: Radial distribution network with 33 buses
- **Voltage Level**: Medium voltage distribution (simplified to per-unit analysis)
- **Bus Numbering**: Buses 1-33, with increasing distance from substation
- **Component Distribution**: Random allocation across buses 1-33

### Bus Allocation Strategy

Components are randomly distributed across the 33 buses:
```python
bus_id = random.randint(1, 34)  # Bus IDs 1-33
```

---

## 2. Component Models

### 2.1 Solar PV Installations

**Quantity**: 10 units  
**Capacity Range**: 2-5 kW per unit  
**Total Capacity**: ~35 kW (variable)

#### Solar Irradiance Model

The solar generation follows a simplified sine-based irradiance model representing daylight hours:

**Operating Hours**: 6:00 - 18:00 (12-hour daylight period)

**Generation Formula**:
$$P_{solar}(t) = \begin{cases} 
P_{rated} \cdot \sin\left(\frac{(h - 6) \cdot \pi}{12}\right) \cdot C_{cloud} \cdot \eta_{sys} & \text{if } 6 \leq h \leq 18 \\
0 & \text{otherwise}
\end{cases}$$

Where:
- $P_{solar}(t)$ = Solar power output at time $t$ (kW)
- $P_{rated}$ = Rated PV capacity (kW)
- $h$ = Hour of day (0-24)
- $C_{cloud}$ = Cloud cover factor (0.8-1.0, stochastic)
- $\eta_{sys}$ = System efficiency = 0.85 (85%)

**Peak Generation**: Occurs at solar noon (h = 12)
$$P_{peak} = P_{rated} \cdot \sin\left(\frac{\pi}{2}\right) \cdot C_{cloud} \cdot 0.85 = P_{rated} \cdot C_{cloud} \cdot 0.85$$

**Cloud Factor Model**:
$$C_{cloud} = 0.8 + 0.2 \cdot U(0,1)$$

Where $U(0,1)$ is a uniform random variable between 0 and 1.

**Key Assumptions**:
- Symmetric irradiance profile (sunrise-sunset)
- No seasonal variations
- Instantaneous response to irradiance changes
- Fixed tilt and orientation

---

### 2.2 Wind Turbines

**Quantity**: 2 units  
**Capacity**: 100 kW per unit  
**Total Capacity**: 200 kW

#### Wind Power Curve

Wind turbines follow a realistic three-region power curve:

**Wind Speed Parameters**:
- $v_{cut-in}$ = 3.0 m/s (cut-in wind speed)
- $v_{rated}$ = 12.0 m/s (rated wind speed)
- $v_{cut-out}$ = 25.0 m/s (cut-out wind speed)

**Power Output Formula**:
$$P_{wind}(v) = \begin{cases} 
0 & \text{if } v < v_{cut-in} \\
P_{rated} \cdot \left(\frac{v - v_{cut-in}}{v_{rated} - v_{cut-in}}\right)^3 & \text{if } v_{cut-in} \leq v < v_{rated} \\
P_{rated} & \text{if } v_{rated} \leq v < v_{cut-out} \\
0 & \text{if } v \geq v_{cut-out}
\end{cases}$$

Where:
- $P_{wind}(v)$ = Wind power output (kW)
- $P_{rated}$ = Rated turbine capacity (100 kW)
- $v$ = Wind speed (m/s)

**Wind Speed Model**:
$$v(t) = 5.0 + 5.0 \cdot U(0,1) \text{ m/s}$$

This gives a uniform distribution between 5-10 m/s (average wind conditions).

**Cubic Region Explanation**:
The cubic relationship ($v^3$) in the partial load region represents the fundamental physics of wind energy:
- Wind power is proportional to air density, swept area, and velocity cubed
- Simplified to a normalized cubic curve for turbine efficiency

**Key Assumptions**:
- No air density corrections
- No turbulence modeling
- Instantaneous power response
- No wake effects between turbines

---

### 2.3 Battery Energy Storage Systems (BESS)

**Quantity**: 5 units  
**Capacity**: 50 kWh per unit  
**Total Capacity**: 250 kWh  
**Power Rating**: 25 kW per unit (0.5C rate)

#### State of Charge (SOC) Model

**SOC Constraints**:
$$SOC_{min} = 0.20 \quad (20\%)$$
$$SOC_{max} = 0.95 \quad (95\%)$$
$$SOC_{initial} = 0.50 \quad (50\%)$$

**Operating Range**: 20%-95% to preserve battery health and lifespan.

#### Charging Model

**Charging Power Formula**:
$$P_{charge}^{actual} = \min\left(P_{charge}^{requested}, P_{max}, \frac{E_{available}}{\Delta t}\right)$$

Where:
- $P_{charge}^{requested}$ = Requested charging power (kW)
- $P_{max}$ = Maximum charge rate = 25 kW (0.5C)
- $E_{available}$ = Available capacity = $(SOC_{max} - SOC_{current}) \cdot E_{capacity}$
- $\Delta t$ = Time step duration (hours)

**Energy Stored**:
$$E_{stored} = P_{charge}^{actual} \cdot \Delta t \cdot \eta_{charge}$$

Where $\eta_{charge} = 0.92$ (92% charging efficiency).

**SOC Update**:
$$SOC_{new} = SOC_{current} + \frac{E_{stored}}{E_{capacity}}$$

#### Discharging Model

**Discharging Power Formula**:
$$P_{discharge}^{actual} = \min\left(P_{discharge}^{requested}, P_{max}, \frac{E_{available}}{\Delta t}\right)$$

Where:
- $E_{available}$ = Available energy = $(SOC_{current} - SOC_{min}) \cdot E_{capacity}$

**Energy Delivered**:
$$E_{delivered} = \frac{P_{discharge}^{actual} \cdot \Delta t}{\eta_{discharge}}$$

Where $\eta_{discharge} = 0.92$ (92% discharging efficiency).

**SOC Update**:
$$SOC_{new} = SOC_{current} - \frac{E_{delivered}}{E_{capacity}}$$

#### Round-Trip Efficiency

$$\eta_{round-trip} = \eta_{charge} \cdot \eta_{discharge} = 0.92 \times 0.92 = 0.8464 \approx 84.6\%$$

**Key Assumptions**:
- Constant efficiency across SOC range
- No self-discharge
- No temperature effects
- Linear capacity-voltage relationship
- Instantaneous power response

---

### 2.4 Residential Loads with Smart Meters

**Quantity**: 800 units  
**Base Load Range**: 0.5-3.0 kW per household  
**Total Base Load**: ~1400 kW (average)  
**Demand Response (DR) Participation**: 70% of loads

#### Load Profile Model

**Time-of-Day Load Factors**:
$$\lambda(h) = \begin{cases} 
0.5 & \text{if } 0 \leq h < 6 & \text{(Night)} \\
0.8 & \text{if } 6 \leq h < 9 & \text{(Morning)} \\
0.6 & \text{if } 9 \leq h < 17 & \text{(Day)} \\
1.0 & \text{if } 17 \leq h < 22 & \text{(Evening Peak)} \\
0.7 & \text{if } 22 \leq h < 24 & \text{(Late Evening)}
\end{cases}$$

**Stochastic Variation**:
$$\lambda_{stochastic} = \lambda(h) \cdot (0.9 + 0.2 \cdot U(0,1))$$

This adds ±10% random variation to represent individual household behavior.

**Load Calculation**:
$$P_{load}(t) = P_{base} \cdot \lambda_{stochastic}(h)$$

#### Demand Response (DR) Model

**DR Active Period**: 17:00 - 22:00 (peak hours)

**DR Reduction Factor**:
$$\alpha_{DR} = 0.85 \quad (15\% \text{ reduction})$$

**Load with DR**:
$$P_{load}^{DR}(t) = \begin{cases} 
P_{load}(t) \cdot \alpha_{DR} & \text{if participant and } 17 \leq h < 22 \\
P_{load}(t) & \text{otherwise}
\end{cases}$$

**DR Participation**:
$$\text{Participant} = \begin{cases} 
\text{True} & \text{if } U(0,1) > 0.3 \\
\text{False} & \text{otherwise}
\end{cases}$$

This gives approximately 70% participation rate.

**Key Assumptions**:
- Fixed load profiles (no day-to-day variation)
- Perfect DR compliance during activation
- No DR rebound effects
- Instantaneous load adjustment

---

## 3. Power Balance and Grid Operations

### 3.1 Net Power Calculation

**Total Renewable Generation**:
$$P_{renewable}(t) = \sum_{i=1}^{10} P_{solar,i}(t) + \sum_{j=1}^{2} P_{wind,j}(t)$$

**Total Load**:
$$P_{load}^{total}(t) = \sum_{k=1}^{800} P_{load,k}^{DR}(t)$$

**Net Power (Before Storage)**:
$$P_{net}(t) = P_{load}^{total}(t) - P_{renewable}(t)$$

**Sign Convention**:
- $P_{net} > 0$: Power deficit (load exceeds generation)
- $P_{net} < 0$: Power surplus (generation exceeds load)

### 3.2 Battery Dispatch Strategy

**Dispatch Logic**:
$$P_{battery}(t) = \begin{cases} 
-\sum_{b=1}^{5} P_{charge,b}(t) & \text{if } P_{net}(t) < 0 & \text{(Charge)} \\
+\sum_{b=1}^{5} P_{discharge,b}(t) & \text{if } P_{net}(t) > 0 & \text{(Discharge)} \\
0 & \text{if } P_{net}(t) = 0 & \text{(Idle)}
\end{cases}$$

**Equal Power Sharing**:
$$P_{charge,b} = \frac{|P_{net}(t)|}{N_{batteries}} = \frac{|P_{net}(t)|}{5}$$

**Final Net Power**:
$$P_{net}^{final}(t) = P_{net}(t) + P_{battery}(t)$$

### 3.3 Renewable Curtailment

**Curtailment Definition**: Excess renewable energy that cannot be used or stored.

**Curtailment Calculation**:
$$P_{curtail}(t) = \max(0, -P_{net}^{final}(t))$$

Curtailment occurs when:
1. Renewable generation exceeds load ($P_{net} < 0$)
2. Batteries are fully charged or charging capacity exceeded
3. Resulting in excess power that must be shed

**Curtailment Percentage**:
$$\text{Curtailment \%} = \frac{\sum_{t=1}^{96} P_{curtail}(t)}{\sum_{t=1}^{96} P_{renewable}(t)} \times 100$$

---

## 4. Voltage Profile Analysis

### 4.1 Simplified Voltage Drop Model

**Note**: This is a simplified model. Real systems would use full AC power flow analysis (Newton-Raphson, etc.).

**Base Voltage**: 1.0 per-unit (p.u.)

**Voltage Drop Calculation**:
$$V_{bus}(i) = V_{base} - k_{drop} \cdot P_{bus}(i) \cdot i$$

Where:
- $V_{bus}(i)$ = Voltage at bus $i$ (p.u.)
- $V_{base}$ = 1.0 p.u.
- $k_{drop}$ = 0.00001 (voltage drop factor)
- $P_{bus}(i)$ = Net power at bus $i$ (kW)
- $i$ = Bus number (1-33, representing distance)

**Bus Power Calculation**:
$$P_{bus}(i) = \sum_{\text{loads at bus } i} P_{load} - \sum_{\text{PV at bus } i} P_{solar} - \sum_{\text{wind at bus } i} P_{wind}$$

### 4.2 Voltage Constraints

**ANSI C84.1 Standards** (typical distribution voltage limits):
$$V_{min} = 0.95 \text{ p.u.} \quad (95\%)$$
$$V_{max} = 1.05 \text{ p.u.} \quad (105\%)$$

**Voltage Violation Count**:
$$N_{violations} = \sum_{t=1}^{96} \sum_{i=1}^{33} \mathbb{1}(V_{bus,i}(t) < 0.95 \text{ or } V_{bus,i}(t) > 1.05)$$

Where $\mathbb{1}$ is the indicator function.

**Limitations of Simplified Model**:
- No reactive power modeling
- No transformer tap ratios
- No line impedances (R, X)
- Linear approximation of voltage drop
- No voltage-dependent loads

---

## 5. Performance Metrics

### 5.1 Energy Metrics

**Total Renewable Generation (24h)**:
$$E_{renewable} = \sum_{t=1}^{96} P_{renewable}(t) \cdot \Delta t = \sum_{t=1}^{96} P_{renewable}(t) \cdot 0.25 \text{ kWh}$$

**Total Load Consumption (24h)**:
$$E_{load} = \sum_{t=1}^{96} P_{load}^{total}(t) \cdot 0.25 \text{ kWh}$$

**Total Curtailment (24h)**:
$$E_{curtail} = \sum_{t=1}^{96} P_{curtail}(t) \cdot 0.25 \text{ kWh}$$

**Renewable Penetration**:
$$\text{Penetration \%} = \frac{E_{renewable}}{E_{load}} \times 100$$

Target: 40% penetration

### 5.2 Battery Performance Metrics

**Average State of Charge**:
$$\overline{SOC} = \frac{1}{96 \times 5} \sum_{t=1}^{96} \sum_{b=1}^{5} SOC_b(t)$$

**Final SOC**: $SOC_b(t=96)$ for each battery $b$

**Battery Utilization**:
- Cycle count estimation
- Depth of discharge analysis
- Energy throughput

### 5.3 Voltage Quality Metrics

**Average System Voltage**:
$$\overline{V}_{system}(t) = \frac{1}{33} \sum_{i=1}^{33} V_{bus,i}(t)$$

**Minimum Bus Voltage**:
$$V_{min}(t) = \min_{i \in [1,33]} V_{bus,i}(t)$$

**Maximum Bus Voltage**:
$$V_{max}(t) = \max_{i \in [1,33]} V_{bus,i}(t)$$

**Voltage Unbalance**:
$$\Delta V(t) = V_{max}(t) - V_{min}(t)$$

### 5.4 Demand Response Effectiveness

**Peak Load Reduction**:
$$\Delta P_{peak} = P_{peak}^{no-DR} - P_{peak}^{with-DR}$$

**DR Capacity**:
$$P_{DR}^{capacity} = 0.7 \times 800 \times P_{avg}^{base} \times 0.15$$

Where:
- 0.7 = 70% participation
- 800 = number of loads
- 0.15 = 15% reduction factor

---

## 6. Simulation Algorithm

### Pseudocode

```
INITIALIZE:
  Create 10 solar PV (2-5 kW each)
  Create 2 wind turbines (100 kW each)
  Create 5 batteries (50 kWh, 25 kW each, SOC=50%)
  Create 800 loads (0.5-3 kW each)
  
FOR t = 0 TO 86400 STEP 900:  // 24 hours, 15-min steps
  hour = t / 3600
  
  // Calculate renewable generation
  cloud_factor = 0.8 + 0.2 * random()
  P_solar = SUM(solar_pv.generate(hour, cloud_factor))
  
  wind_speed = 5.0 + 5.0 * random()
  P_wind = SUM(wind_turbine.generate(wind_speed))
  
  P_renewable = P_solar + P_wind
  
  // Calculate load
  dr_active = (17 <= hour < 22)
  P_load = SUM(load.calculate(hour, dr_active))
  
  // Net power
  P_net = P_load - P_renewable
  
  // Battery dispatch
  IF P_net < 0:  // Excess generation
    P_battery = -charge_batteries(|P_net|)
  ELSE IF P_net > 0:  // Deficit
    P_battery = discharge_batteries(P_net)
  
  P_net_final = P_net + P_battery
  
  // Curtailment
  P_curtail = MAX(0, -P_net_final)
  
  // Voltage calculation
  FOR bus = 1 TO 33:
    P_bus = calculate_bus_power(bus)
    V_bus = 1.0 - 0.00001 * P_bus * bus
  
  // Store metrics
  RECORD(P_renewable, P_load, P_net_final, P_curtail, V_bus[], SOC[])
  
  // Time advancement
  IF use_helics:
    current_time = helics_request_time(t + 900)
  ELSE:
    current_time = t + 900

// Generate report
CALCULATE(
  total_energy,
  curtailment_percentage,
  voltage_statistics,
  battery_statistics
)
```

---

## 7. Key Assumptions and Limitations

### Assumptions

1. **Perfect Forecasting**: No prediction errors for generation or load
2. **Instantaneous Response**: All components respond without delay
3. **Linear Models**: Simplified physics for voltage and power flow
4. **No Losses**: Neglects line losses, transformer losses (except battery efficiency)
5. **Balanced Three-Phase**: Single-phase equivalent analysis
6. **No Contingencies**: No equipment failures or outages
7. **No Market**: No economic dispatch or pricing signals
8. **Fixed Topology**: No network reconfiguration

### Limitations

1. **Voltage Model**: Simplified linear drop; real systems need AC power flow
2. **No Reactive Power**: Only active power (P) considered, no Q or power factor
3. **No Harmonics**: Pure sinusoidal assumption
4. **Weather Model**: Simplified stochastic; no correlation or persistence
5. **Battery Model**: No degradation, temperature effects, or non-linear behavior
6. **Load Model**: Fixed profiles; no elasticity or real-time pricing response
7. **No Inverter Limits**: No consideration of inverter constraints or control modes

---

## 8. Future Enhancements

### Model Improvements

1. **Full AC Power Flow**: Newton-Raphson or Fast Decoupled Load Flow
2. **Reactive Power Control**: Voltage regulation via inverters
3. **Detailed Battery Model**: Include degradation, temperature, C-rate effects
4. **Weather Correlation**: Time-series models for solar and wind
5. **Economic Optimization**: Optimal dispatch considering costs
6. **Forecasting Errors**: Add uncertainty and model predictive control

### Analysis Extensions

1. **Reliability Analysis**: SAIDI, SAIFI metrics
2. **Hosting Capacity**: Maximum DER penetration analysis
3. **Protection Coordination**: Fault analysis with high DER
4. **Transient Stability**: Dynamic response to disturbances
5. **Long-term Planning**: Multi-year scenarios with growth

---

## 9. Validation and Verification

### Verification Checks

**Energy Balance**:
$$E_{renewable} + E_{grid} = E_{load} + E_{curtail} + E_{losses}$$

In this simplified model:
$$E_{renewable} = E_{load} + E_{curtail} + \Delta E_{battery}$$

**Power Balance at Each Timestep**:
$$P_{renewable}(t) + P_{battery}(t) + P_{curtail}(t) = P_{load}(t)$$

**SOC Limits**:
$$\forall t, b: \quad 0.2 \leq SOC_b(t) \leq 0.95$$

**Voltage Limits** (ideally):
$$\forall t, i: \quad 0.95 \leq V_{bus,i}(t) \leq 1.05$$

### Validation Approach

1. **Component Testing**: Validate each model independently
2. **Benchmark Comparison**: Compare with standard IEEE test cases
3. **Sensitivity Analysis**: Vary parameters and observe response
4. **Physical Plausibility**: Check for non-physical results
5. **Statistical Analysis**: Verify stochastic distributions

---

## 10. References and Standards

### Technical Standards

- **IEEE 33-Bus Test System**: Standard distribution test feeder
- **ANSI C84.1**: Voltage ratings for electric power systems
- **IEEE 1547**: Interconnection standards for distributed resources
- **IEC 61850**: Communication networks and systems for power utility automation

### Modeling References

- Solar PV modeling: King et al., Sandia Array Performance Model
- Wind turbine curves: IEC 61400-12-1 power performance measurements
- Battery modeling: Shepherd model, equivalent circuit models
- Load profiles: NREL Residential Load Data

### HELICS Co-Simulation

- HELICS Documentation: https://docs.helics.org/
- Co-simulation paradigms for cross-domain analysis
- Time synchronization and data exchange protocols

---

## Appendix: Notation Table

| Symbol | Description | Units |
|--------|-------------|-------|
| $P$ | Active power | kW |
| $E$ | Energy | kWh |
| $V$ | Voltage | p.u. |
| $SOC$ | State of charge | - (0-1) |
| $\eta$ | Efficiency | - (0-1) |
| $h$ | Hour of day | hours (0-24) |
| $t$ | Time | seconds |
| $\Delta t$ | Time step | hours (0.25) |
| $v$ | Wind speed | m/s |
| $C_{cloud}$ | Cloud factor | - (0.8-1.0) |
| $\lambda$ | Load factor | - |
| $\alpha_{DR}$ | DR reduction | - (0.85) |
| $k_{drop}$ | Voltage drop factor | p.u./kW |
| $U(0,1)$ | Uniform random [0,1] | - |

---

**Document Version**: 1.0  
**Last Updated**: January 11, 2026  
**Simulation Code**: scenario_e1.py
