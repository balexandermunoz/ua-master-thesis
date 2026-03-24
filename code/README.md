# Co-Simulation Framework

## Overview
This project implements a co-simulation framework using HELICS to validate cross-domain interactions across energy systems, mobility networks, and telecommunications domains. The framework enables realistic modeling of complex interactions between different infrastructure systems.

## Simulation Scenarios

To validate the proposed co-simulation framework and evaluate its effectiveness in modeling cross-domain interactions, six distinct scenarios were designed:

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

### Scenarios E2-E6: Coming Soon

2. **Mobility Network Simulation** - Modeling transportation and vehicle networks
3. **Telecommunications Domain Simulation** - Simulating network communication and data flows
4. **Energy-Mobility Integration** - Cross-domain interactions between energy and mobility
5. **Mobility-Telecommunications Integration** - Cross-domain interactions between mobility and telecom
6. **Full Cross-Domain Integration** - Complete integration across all three domains

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

### Running Scenario E1 (Standalone Mode)

The simulation runs in standalone mode by default, which doesn't require HELICS broker infrastructure:

```bash
python main.py
```

### Running with HELICS Co-Simulation

To enable HELICS for multi-federate co-simulation:

1. Start a HELICS broker in a separate terminal:
   ```bash
   helics_broker --federates=1
   ```

2. Run the simulation (modify main.py to pass `use_helics=True`):
   ```python
   report = run_scenario_e1(use_helics=True)
   ```

### Simulation Output

The simulation provides comprehensive metrics including:

```
Components:
  solar_pv_count: 10
  solar_capacity_kw: 35.2
  wind_turbine_count: 2
  wind_capacity_kw: 200.0
  battery_count: 5
  battery_capacity_kwh: 250.0
  load_count: 800

Metrics:
  total_renewable_generation_kwh: 1523.45
  total_load_kwh: 1847.23
  total_curtailment_kwh: 12.34
  curtailment_percentage: 0.81
  avg_voltage_pu: 0.998
  min_voltage_pu: 0.995
  max_voltage_pu: 1.002
  voltage_violations: 0
  avg_battery_soc: 0.52
```

## Dependencies

- **helics** (>=3.4.0) - Co-simulation framework
- **numpy** (>=1.24.0) - Numerical computations
- **Python 3.8+** - Core language

See [requirements.txt](requirements.txt) for complete dependency list.

## Project Structure

```
ua-master-code/
├── main.py                 # Main simulation entry point
├── README.md              # Project documentation
├── requirements.txt       # Python dependencies
└── scenarios/
    ├── __init__.py       # Package initializer
    └── scenario_e1.py    # Smart Grid with Renewable Integration
```

## Architecture

### Component Models

**SolarPV**: Simulates rooftop solar installations with:
- Time-of-day irradiance modeling (sine curve 6:00-18:00)
- Cloud factor variability
- 85% system efficiency

**WindTurbine**: Models wind power generation with:
- Realistic power curve (cubic region below rated speed)
- Cut-in, rated, and cut-out wind speeds
- Stochastic wind speed variations

**BatteryStorage**: Energy storage system featuring:
- State-of-charge (SOC) management (20%-95%)
- Charge/discharge power limits (0.5C rate)
- 92% round-trip efficiency
- Smart dispatch based on grid conditions

**ResidentialLoad**: Smart meter-enabled loads with:
- Time-varying consumption profiles
- Demand response participation (70% of loads)
- 15% peak reduction capability (17:00-22:00)
- Stochastic load variations

### Simulation Flow

1. **Initialization**: Create grid components and distribute across 33-bus network
2. **Time Loop**: Iterate through 96 time steps (15-min intervals)
3. **Generation Calculation**: Compute solar and wind output
4. **Load Calculation**: Determine residential consumption with DR
5. **Battery Dispatch**: Balance grid using energy storage
6. **Voltage Analysis**: Calculate bus voltages
7. **Metrics Collection**: Store all simulation data
8. **Reporting**: Generate comprehensive performance report

## Future Work

- Implementation of scenarios E2-E6
- Enhanced power flow analysis (replacing simplified voltage model)
- Integration with real-world grid data
- Advanced forecasting and optimization algorithms
- Multi-federate HELICS co-simulation across domains
- Visualization and plotting capabilities
- Database storage for simulation results

## License

[Add your license information here]

## Contributors

[Add contributor information here]

## References

- HELICS Documentation: https://docs.helics.org/
- IEEE 33-Bus Test System: [Add reference]
