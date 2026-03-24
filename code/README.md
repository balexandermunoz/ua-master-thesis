# Co-Simulation Framework

## Overview
This project implements a co-simulation framework using HELICS to validate cross-domain interactions across energy systems, mobility networks, and telecommunications domains. The framework enables realistic modeling of complex interactions between different infrastructure systems.

## Simulation Scenarios

Three scenarios have been implemented to validate the proposed co-simulation framework across energy and mobility domains. Each scenario supports both standalone execution and HELICS co-simulation mode.

---

### Scenario E1: Smart Grid with Renewable Integration ✅ **Implemented**

Simulates an IEEE 33-bus distribution network with high penetration of renewable energy sources and distributed storage systems.

**Grid Configuration:**
- IEEE 33-bus distribution system with 40% renewable penetration
- 24-hour simulation with 15-minute time steps (96 steps)
- Standalone or HELICS co-simulation mode

**Components:**
- 10 rooftop solar PV installations (2-5 kW each)
- 2 wind turbines (100 kW each)
- 5 battery energy storage systems (50 kWh each, 25 kW max power)
- 800 residential loads with smart meters (70% DR participation)

**Simulation Objectives:**
- Analyze voltage profile stability under variable renewable generation
- Evaluate energy storage dispatch strategies
- Assess demand response effectiveness during peak hours (17:00-22:00)
- Quantify renewable energy curtailment

**Key Outputs:**
- Voltage profiles for all 33 buses (min/max/avg in per-unit)
- Power flows and net system power over 24 hours
- Battery state-of-charge (SOC) trajectories
- Renewable curtailment metrics and percentages
- Demand response impact analysis

**Model Features:**
- Realistic solar generation with time-of-day irradiance model
- Wind turbine power curve (cut-in: 3 m/s, rated: 12 m/s, cut-out: 25 m/s)
- Battery efficiency modeling (92% round-trip efficiency)
- Time-varying residential load profiles with stochastic variations
- Intelligent battery dispatch for grid balancing

---

### Scenario E2: Electric Vehicle Charging Infrastructure ✅ **Implemented**

Simulates an IEEE 13-node test feeder with EV charging impact analysis, including coordinated and uncoordinated charging strategies and Vehicle-to-Grid (V2G) capabilities.

**Grid Configuration:**
- Modified IEEE 13-node test feeder
- 24-hour simulation with time-of-use tariff structure
- Three charging control strategies: Uncoordinated, Smart, and V2G

**Components:**
- 100 electric vehicles with varied arrival/departure times and battery sizes
- 20 Level 2 charging stations (7.2 kW) in residential areas
- 5 DC fast charging stations (50 kW) in commercial zones
- 50% of EVs are V2G-capable

**Simulation Objectives:**
- Evaluate grid impact under different EV charging strategies
- Compare peak load profiles across uncoordinated, smart, and V2G modes
- Assess cost savings from coordinated and V2G charging
- Analyze energy flows from V2G discharge

**Key Outputs:**
- Total energy charged/discharged per strategy
- Peak grid demand and average charging power
- Charging cost per vehicle and total cost
- Grid stress metrics (peak demand, load factor)

**Strategy Comparison:**
Run `python main.py` and select `compare` → `E2` to compare all three strategies side by side.

---

### Scenario M1: Urban Traffic Congestion Management ✅ **Implemented**

Simulates a 5×5 km urban road grid with agent-based vehicles and adaptive traffic signal control, comparing fixed-cycle vs. demand-responsive signal strategies.

**Network Configuration:**
- 5×5 km urban grid with 500 m block spacing
- 25 signalized intersections (5×5 layout)
- 2-hour peak-hour simulation with 1-second time steps

**Components:**
- 2,500 vehicles with randomized origin-destination pairs
- 25 adaptive traffic signal controllers (15–90 s green time range)
- Real-time queue-sensing and demand-responsive phase switching
- Simplified CO₂ emissions model per vehicle

**Simulation Objectives:**
- Evaluate adaptive vs. fixed-cycle signal control performance
- Measure average travel time and total vehicle delay
- Quantify emissions reduction from adaptive signals
- Analyze intersection throughput and congestion hotspots

**Key Outputs:**
- Average travel time and total vehicle delay (seconds)
- Vehicle throughput and completion rate
- CO₂ emissions per strategy (grams)
- Average queue length per intersection

**Strategy Comparison:**
Run `python main.py` and select `compare` → `M1` to compare fixed vs. adaptive signal schemes.

---

### Scenarios E3–E6: Planned

- **E3**: Telecommunications Domain Simulation
- **E4**: Energy–Mobility Integration (EV charging + grid co-simulation)
- **E5**: Mobility–Telecommunications Integration
- **E6**: Full Cross-Domain Integration (all three domains via HELICS)

## Setup

### Prerequisites
- Python 3.8 or higher
- Virtual environment (recommended)

### Installation

1. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```

2. **Activate the virtual environment:**
   - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
   - Windows (CMD): `.venv\Scripts\activate.bat`
   - Linux/Mac: `source .venv/bin/activate`

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run `python main.py` from the project root. You will be prompted to select a scenario:

```
Select scenario (E1/E2/M1) or 'compare' (E2/M1):
```

### Scenario E1 – Smart Grid (Standalone)

```bash
python main.py
# Select: E1
```

### Scenario E2 – EV Charging (with strategy selection)

```bash
python main.py
# Select: E2
# Then choose: uncoordinated / smart / v2g  (default: smart)
```

### Scenario M1 – Urban Traffic (with signal mode selection)

```bash
python main.py
# Select: M1
# Then choose: y/n for adaptive signals (default: y)
```

### Strategy Comparison Mode

```bash
python main.py
# Select: compare
# Then choose: E2 (charging strategies) or M1 (signal control)
```

### Running with HELICS Co-Simulation

All scenarios support HELICS. To enable it:

1. Start a HELICS broker in a separate terminal:
   ```bash
   helics_broker --federates=1
   ```

2. Pass `use_helics=True` when calling the scenario directly:
   ```python
   from scenarios.scenario_e1 import run_scenario_e1
   report = run_scenario_e1(use_helics=True)
   ```

## Dependencies

- **helics** (>=3.4.0) - Co-simulation framework
- **numpy** (>=1.24.0) - Numerical computations
- **Python 3.8+** - Core language

See [requirements.txt](requirements.txt) for complete dependency list.

## Project Structure

```
ua-master-code/
├── main.py                     # Main entry point — interactive scenario selector
├── README.md                   # Project documentation
├── requirements.txt            # Python dependencies
├── Examples_Helics.py          # HELICS usage examples
├── Examples_Mosaik.py          # Mosaik usage examples
└── scenarios/
    ├── __init__.py             # Package initializer
    ├── scenario_e1.py          # E1: Smart Grid with Renewable Integration
    ├── scenario_e2.py          # E2: Electric Vehicle Charging Infrastructure
    └── scenario_m1.py          # M1: Urban Traffic Congestion Management
```

## Architecture

### Component Models

#### Scenario E1 – Energy Domain

**SolarPV**: Simulates rooftop solar with time-of-day irradiance (sine curve 6:00–18:00) and 85% system efficiency.

**WindTurbine**: Models wind power with a realistic cubic power curve, cut-in/rated/cut-out speeds, and stochastic wind variations.

**BatteryStorage**: Energy storage with SOC management (20%–95%), 0.5C charge/discharge limits, 92% round-trip efficiency, and smart dispatch.

**ResidentialLoad**: Smart meter-enabled loads with time-varying profiles, 70% demand response participation, and 15% peak reduction (17:00–22:00).

#### Scenario E2 – EV Charging Domain

**ElectricVehicle**: EV agent with configurable battery, SOC tracking, charging efficiency (90%), and optional V2G discharge capability.

**ChargingStation**: Level 2 (7.2 kW residential) and DC fast (50 kW commercial) chargers with queue management.

**EVChargingFederate**: Orchestrates the full charging session lifecycle using one of three strategies: `Uncoordinated`, `Smart` (grid-aware scheduling), or `V2G` (bidirectional energy flow).

#### Scenario M1 – Mobility Domain

**Vehicle**: Agent-based vehicle with origin-destination routing, speed modeling, delay tracking, and CO₂ emissions estimation.

**TrafficSignal**: Adaptive controller with demand-responsive green time (15–90 s), phase-switching based on queue ratios, and yellow phase enforcement.

**TrafficSimulation**: Manages the full 5×5 grid, dispatches vehicles across intersections, and records throughput and delay metrics.

---

### Simulation Flow (All Scenarios)

1. **Initialization** — Create federate, configure HELICS or standalone mode
2. **Component Setup** — Instantiate domain-specific agents and infrastructure
3. **Time Loop** — Step through simulation time with configurable `dt`
4. **State Update** — Each agent updates based on current inputs and internal state
5. **Grid/Network Interaction** — Aggregate effects computed (voltage, congestion, load)
6. **Metrics Collection** — Per-step data recorded for all agents
7. **Report Generation** — Summary metrics and component statistics exported

## Future Work

- Implementation of scenarios E3–E6 (telecom, cross-domain integrations)
- Enhanced power flow analysis (replacing simplified voltage model)
- Multi-federate HELICS co-simulation connecting E1, E2, and M1 federates
- Advanced forecasting and optimization algorithms
- Visualization and plotting capabilities for simulation outputs
- Database storage for simulation results

## License

[Add your license information here]

## Contributors

[Add contributor information here]

## References

- HELICS Documentation: https://docs.helics.org/
- IEEE 33-Bus Test System: [Add reference]
