"""
Scenario E1: Smart Grid with Renewable Integration

IEEE 33-bus distribution system with 40% renewable penetration
- 10 rooftop solar PV installations (2-5 kW each)
- 2 wind turbines (100 kW each)
- 5 battery energy storage systems (50 kWh each)
- 800 residential loads with smart meters
"""

import helics as h
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class SolarPV:
    """Solar PV installation model"""
    
    def __init__(self, pv_id: int, capacity_kw: float, bus_id: int):
        self.id = pv_id
        self.capacity_kw = capacity_kw
        self.bus_id = bus_id
        self.generation_kw = 0.0
        
    def calculate_generation(self, hour: float, cloud_factor: float = 1.0) -> float:
        """Calculate solar generation based on time of day"""
        # Simple solar irradiance model (peak at noon)
        if 6 <= hour <= 18:
            # Sine curve for daylight hours
            time_factor = np.sin((hour - 6) * np.pi / 12)
            self.generation_kw = self.capacity_kw * time_factor * cloud_factor * 0.85  # 85% efficiency
        else:
            self.generation_kw = 0.0
        return self.generation_kw


class WindTurbine:
    """Wind turbine model"""
    
    def __init__(self, turbine_id: int, capacity_kw: float, bus_id: int):
        self.id = turbine_id
        self.capacity_kw = capacity_kw
        self.bus_id = bus_id
        self.generation_kw = 0.0
        
    def calculate_generation(self, wind_speed_ms: float) -> float:
        """Calculate wind generation based on wind speed (m/s)"""
        # Simplified power curve
        cut_in = 3.0  # m/s
        rated = 12.0  # m/s
        cut_out = 25.0  # m/s
        
        if wind_speed_ms < cut_in or wind_speed_ms > cut_out:
            self.generation_kw = 0.0
        elif wind_speed_ms < rated:
            # Cubic relationship in this region
            self.generation_kw = self.capacity_kw * ((wind_speed_ms - cut_in) / (rated - cut_in)) ** 3
        else:
            self.generation_kw = self.capacity_kw
            
        return self.generation_kw


class BatteryStorage:
    """Battery Energy Storage System"""
    
    def __init__(self, battery_id: int, capacity_kwh: float, power_kw: float, bus_id: int):
        self.id = battery_id
        self.capacity_kwh = capacity_kwh
        self.power_kw = power_kw  # Max charge/discharge rate
        self.bus_id = bus_id
        self.soc = 0.5  # State of charge (0-1)
        self.soc_min = 0.2
        self.soc_max = 0.95
        self.efficiency = 0.92
        
    def charge(self, power_kw: float, dt_hours: float) -> float:
        """Charge battery, returns actual power drawn from grid"""
        grid_power = min(power_kw, self.power_kw)
        energy_stored = grid_power * dt_hours * self.efficiency
        available_capacity = (self.soc_max - self.soc) * self.capacity_kwh
        if energy_stored > available_capacity:
            energy_stored = available_capacity
            grid_power = energy_stored / (dt_hours * self.efficiency)
        self.soc += energy_stored / self.capacity_kwh
        return grid_power  # Power drawn from grid
        
    def discharge(self, power_kw: float, dt_hours: float) -> float:
        """Discharge battery, returns actual power delivered to grid"""
        battery_power = min(power_kw, self.power_kw)
        energy_from_battery = battery_power * dt_hours
        available_energy = (self.soc - self.soc_min) * self.capacity_kwh
        if energy_from_battery > available_energy:
            energy_from_battery = available_energy
            battery_power = energy_from_battery / dt_hours
        self.soc -= energy_from_battery / self.capacity_kwh
        return battery_power * self.efficiency  # Power delivered to grid


class ResidentialLoad:
    """Residential load with smart meter"""
    
    def __init__(self, load_id: int, base_load_kw: float, bus_id: int):
        self.id = load_id
        self.base_load_kw = base_load_kw
        self.bus_id = bus_id
        self.current_load_kw = base_load_kw
        self.dr_participation = np.random.random() > 0.3  # 70% participate in DR
        
    def calculate_load(self, hour: float, dr_active: bool = False) -> float:
        """Calculate load based on time of day and demand response"""
        # Typical residential load profile
        if 0 <= hour < 6:
            load_factor = 0.5  # Night
        elif 6 <= hour < 9:
            load_factor = 0.8  # Morning
        elif 9 <= hour < 17:
            load_factor = 0.6  # Day
        elif 17 <= hour < 22:
            load_factor = 1.0  # Evening peak
        else:
            load_factor = 0.7  # Late evening
            
        # Add some randomness
        load_factor *= (0.9 + 0.2 * np.random.random())
        
        # Demand response reduction during peak hours
        if dr_active and self.dr_participation and 17 <= hour < 22:
            load_factor *= 0.85  # 15% reduction
            
        self.current_load_kw = self.base_load_kw * load_factor
        return self.current_load_kw


class SmartGridFederate:
    """HELICS federate for smart grid simulation"""
    
    def __init__(self, name: str = "SmartGrid", use_helics: bool = False):
        self.name = name
        self.federate = None
        self.use_helics = use_helics
        
        # Grid components
        self.solar_pvs: List[SolarPV] = []
        self.wind_turbines: List[WindTurbine] = []
        self.batteries: List[BatteryStorage] = []
        self.loads: List[ResidentialLoad] = []
        
        # Simulation parameters
        self.time_step = 15 * 60  # 15 minutes in seconds
        self.sim_duration = 24 * 3600  # 24 hours in seconds
        
        # Metrics
        self.voltage_profiles = []
        self.power_flows = []
        self.soc_history = []
        self.curtailment_history = []
        self.renewable_generation = []
        self.solar_generation = []
        self.wind_generation = []
        self.total_load = []
        self.hours_of_day = []
        self.battery_dispatch_history = []
        
    def initialize_components(self):
        """Initialize all grid components"""
        logger.info("Initializing grid components...")
        
        # Create 50 solar PV installations (5-10 kW each)
        for i in range(50):
            capacity = np.random.uniform(5.0, 10.0)
            bus_id = np.random.randint(1, 34)  # IEEE 33-bus system
            self.solar_pvs.append(SolarPV(i, capacity, bus_id))
            
        # Create 3 wind turbines (500 kW each)
        for i in range(3):
            bus_id = np.random.randint(1, 34)
            self.wind_turbines.append(WindTurbine(i, 500.0, bus_id))
            
        # Create 5 battery storage systems (50 kWh each)
        for i in range(5):
            bus_id = np.random.randint(1, 34)
            # Max power = 0.5C rate
            self.batteries.append(BatteryStorage(i, 50.0, 25.0, bus_id))
            
        # Create 800 residential loads
        for i in range(800):
            base_load = np.random.uniform(0.5, 3.0)  # 0.5-3 kW base
            bus_id = np.random.randint(1, 34)
            self.loads.append(ResidentialLoad(i, base_load, bus_id))
            
        logger.info(f"Created {len(self.solar_pvs)} solar PVs, "
                   f"{len(self.wind_turbines)} wind turbines, "
                   f"{len(self.batteries)} batteries, "
                   f"{len(self.loads)} loads")
        
    def setup_federate(self):
        """Setup HELICS federate (optional for standalone simulation)"""
        if not self.use_helics:
            logger.info("Running in standalone mode (HELICS disabled)")
            return
            
        logger.info("Setting up HELICS federate...")
        
        try:
            # Create federate info
            fedinfo = h.helicsCreateFederateInfo()
            h.helicsFederateInfoSetCoreName(fedinfo, self.name)
            h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
            h.helicsFederateInfoSetCoreInitString(fedinfo, "--federates=1 --autobroker")
            h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, self.time_step)
            
            # Create value federate
            self.federate = h.helicsCreateValueFederate(self.name, fedinfo)
            logger.info(f"Federate '{self.name}' created")
            
            # Register publications (outputs from this federate)
            self.pub_total_generation = h.helicsFederateRegisterGlobalPublication(
                self.federate, "total_renewable_generation", h.helics_data_type_double, "kW"
            )
            self.pub_total_load = h.helicsFederateRegisterGlobalPublication(
                self.federate, "total_load", h.helics_data_type_double, "kW"
            )
            self.pub_net_power = h.helicsFederateRegisterGlobalPublication(
                self.federate, "net_power", h.helics_data_type_double, "kW"
            )
            
            # Enter initialization mode
            h.helicsFederateEnterExecutingMode(self.federate)
            logger.info("Federate entering execution mode")
        except Exception as e:
            logger.warning(f"HELICS setup failed: {e}. Running in standalone mode.")
            self.federate = None
            self.use_helics = False
        
    def calculate_storage_dispatch(self, net_power: float) -> float:
        """Calculate battery dispatch strategy"""
        total_dispatch = 0.0
        dt_hours = self.time_step / 3600.0
        
        if net_power < 0:  # Excess generation - charge batteries
            power_per_battery = abs(net_power) / len(self.batteries)
            for battery in self.batteries:
                charged = battery.charge(power_per_battery, dt_hours)
                total_dispatch += charged
        elif net_power > 0:  # Deficit - discharge batteries
            power_per_battery = net_power / len(self.batteries)
            for battery in self.batteries:
                discharged = battery.discharge(power_per_battery, dt_hours)
                total_dispatch -= discharged
                
        return total_dispatch
        
    def calculate_voltage_profile(self, net_power: float) -> Dict[int, float]:
        """Simplified voltage profile calculation"""
        # Simplified model - in reality would use power flow analysis
        base_voltage = 1.0  # p.u.
        voltage_drop_factor = 0.00002  # Simplified impedance effect
        
        voltages = {}
        for bus_id in range(1, 34):
            # Calculate power at this bus
            bus_power = sum(load.current_load_kw for load in self.loads if load.bus_id == bus_id)
            bus_power -= sum(pv.generation_kw for pv in self.solar_pvs if pv.bus_id == bus_id)
            bus_power -= sum(wt.generation_kw for wt in self.wind_turbines if wt.bus_id == bus_id)
            
            # Simplified voltage drop
            voltage_drop = voltage_drop_factor * bus_power * bus_id  # Distance factor
            voltages[bus_id] = base_voltage - voltage_drop
            
        return voltages
        
    def run_simulation(self):
        """Run the 24-hour simulation"""
        logger.info("Starting 24-hour simulation with 15-minute time steps")
        
        current_time = 0.0
        step = 0
        
        while current_time < self.sim_duration:
            # Convert to hours for easier calculations
            hour_of_day = (current_time / 3600.0) % 24
            
            # Calculate renewable generation
            # Solar generation
            cloud_factor = 0.8 + 0.2 * np.random.random()
            solar_total = sum(pv.calculate_generation(hour_of_day, cloud_factor) 
                            for pv in self.solar_pvs)
            
            # Wind generation
            wind_speed = 5.0 + 7.0 * np.random.random()  # 5-12 m/s range
            wind_total = sum(wt.calculate_generation(wind_speed) 
                           for wt in self.wind_turbines)
            
            total_renewable = solar_total + wind_total
            
            # Calculate load
            dr_active = 17 <= hour_of_day < 22  # DR active during peak
            total_load_kw = sum(load.calculate_load(hour_of_day, dr_active) 
                               for load in self.loads)
            
            # Net power (negative = excess generation)
            net_power = total_load_kw - total_renewable
            
            # Battery dispatch
            battery_dispatch = self.calculate_storage_dispatch(net_power)
            net_power += battery_dispatch
            
            # Calculate curtailment (if still excess after battery charge)
            curtailment = max(0, -net_power)
            
            # Calculate voltage profile
            voltages = self.calculate_voltage_profile(net_power)
            
            # Store metrics
            self.renewable_generation.append(total_renewable)
            self.solar_generation.append(solar_total)
            self.wind_generation.append(wind_total)
            self.total_load.append(total_load_kw)
            self.power_flows.append(net_power)
            self.curtailment_history.append(curtailment)
            self.voltage_profiles.append(voltages)
            self.soc_history.append([b.soc for b in self.batteries])
            self.hours_of_day.append(hour_of_day)
            self.battery_dispatch_history.append(battery_dispatch)
            
            # Publish values to HELICS (if enabled)
            if self.use_helics and self.federate:
                h.helicsPublicationPublishDouble(self.pub_total_generation, total_renewable)
                h.helicsPublicationPublishDouble(self.pub_total_load, total_load_kw)
                h.helicsPublicationPublishDouble(self.pub_net_power, net_power)
                
                # Request time advancement
                current_time = h.helicsFederateRequestTime(self.federate, current_time + self.time_step)
            else:
                # Standalone mode - just advance time
                current_time += self.time_step
            
            step += 1
            if step % 16 == 0:  # Log every 4 hours
                logger.info(f"Step {step}: Hour {hour_of_day:.1f}, "
                          f"Generation: {total_renewable:.1f} kW, "
                          f"Load: {total_load_kw:.1f} kW, "
                          f"Curtailment: {curtailment:.1f} kW")
                
        logger.info("Simulation completed")
        
    def generate_report(self) -> Dict:
        """Generate simulation report with all metrics"""
        avg_voltages = []
        min_voltages = []
        max_voltages = []
        
        for vp in self.voltage_profiles:
            voltages = list(vp.values())
            avg_voltages.append(np.mean(voltages))
            min_voltages.append(np.min(voltages))
            max_voltages.append(np.max(voltages))
        
        # Identify peak-hour steps (17:00-22:00)
        peak_mask = [17 <= h < 22 for h in self.hours_of_day]
        off_peak_mask = [not p for p in peak_mask]
        
        peak_loads = [self.total_load[i] for i in range(len(self.total_load)) if peak_mask[i]]
        off_peak_loads = [self.total_load[i] for i in range(len(self.total_load)) if off_peak_mask[i]]
        
        # Estimate DR impact: 70% of loads participate with 15% reduction during peak
        # Reverse the DR factor to estimate load without DR
        dr_participation_rate = 0.70
        dr_reduction_factor = 0.85
        avg_peak_load_with_dr = np.mean(peak_loads) if peak_loads else 0
        # Estimated load without DR = actual / (1 - participation_rate * (1 - reduction_factor))
        estimated_peak_load_without_dr = avg_peak_load_with_dr / (1 - dr_participation_rate * (1 - dr_reduction_factor))
        dr_load_reduction_kw = estimated_peak_load_without_dr - avg_peak_load_with_dr
        dr_load_reduction_pct = (dr_load_reduction_kw / estimated_peak_load_without_dr * 100) if estimated_peak_load_without_dr > 0 else 0
        
        # Curtailment-battery correlation: verify curtailment only when batteries
        # cannot absorb more surplus (full capacity or max charge rate)
        curtailment_steps = sum(1 for c in self.curtailment_history if c > 0)
        curtailment_with_saturated_battery = 0
        total_max_charge_rate = sum(b.power_kw for b in self.batteries)
        for i, c in enumerate(self.curtailment_history):
            if c > 0:
                batteries_full = all(soc >= 0.94 for soc in self.soc_history[i])
                batteries_rate_limited = abs(self.battery_dispatch_history[i]) >= total_max_charge_rate * 0.99
                if batteries_full or batteries_rate_limited:
                    curtailment_with_saturated_battery += 1
            
        report = {
            "scenario": "E1 - Smart Grid with Renewable Integration",
            "simulation_duration_hours": 24,
            "time_step_minutes": 15,
            "components": {
                "solar_pv_count": len(self.solar_pvs),
                "solar_capacity_kw": sum(pv.capacity_kw for pv in self.solar_pvs),
                "wind_turbine_count": len(self.wind_turbines),
                "wind_capacity_kw": sum(wt.capacity_kw for wt in self.wind_turbines),
                "battery_count": len(self.batteries),
                "battery_capacity_kwh": sum(b.capacity_kwh for b in self.batteries),
                "load_count": len(self.loads),
            },
            "metrics": {
                "total_renewable_generation_kwh": sum(self.renewable_generation) * (15/60),
                "total_solar_generation_kwh": sum(self.solar_generation) * (15/60),
                "total_wind_generation_kwh": sum(self.wind_generation) * (15/60),
                "renewable_penetration_pct": (sum(self.renewable_generation) / sum(self.total_load) * 100) if sum(self.total_load) > 0 else 0,
                "total_load_kwh": sum(self.total_load) * (15/60),
                "total_curtailment_kwh": sum(self.curtailment_history) * (15/60),
                "curtailment_percentage": (sum(self.curtailment_history) / 
                                          sum(self.renewable_generation) * 100) if sum(self.renewable_generation) > 0 else 0,
                "avg_voltage_pu": np.mean(avg_voltages),
                "min_voltage_pu": np.min(min_voltages),
                "max_voltage_pu": np.max(max_voltages),
                "voltage_violations": sum(1 for v_min, v_max in zip(min_voltages, max_voltages) if v_min < 0.95 or v_max > 1.05),
                "final_battery_soc": [float(b.soc) for b in self.batteries],
                "avg_battery_soc": np.mean([np.mean(soc_step) for soc_step in self.soc_history]),
                # Peak load and DR validation metrics
                "peak_load_kw": max(self.total_load),
                "avg_peak_hour_load_kw": avg_peak_load_with_dr,
                "avg_off_peak_load_kw": np.mean(off_peak_loads) if off_peak_loads else 0,
                "estimated_dr_load_reduction_kw": dr_load_reduction_kw,
                "estimated_dr_load_reduction_pct": dr_load_reduction_pct,
                # Curtailment-battery validation metrics
                "curtailment_steps": curtailment_steps,
                "curtailment_with_saturated_battery": curtailment_with_saturated_battery,
                "curtailment_battery_validation": "PASS" if (curtailment_steps == 0 or curtailment_with_saturated_battery == curtailment_steps) else "FAIL",
            }
        }
        
        return report
        
    def cleanup(self):
        """Cleanup HELICS federate"""
        if self.use_helics and self.federate:
            try:
                h.helicsFederateFinalize(self.federate)
                h.helicsFederateFree(self.federate)
                h.helicsCloseLibrary()
                logger.info("Federate cleaned up")
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")


def run_scenario_e1(use_helics: bool = False):
    """Main function to run Scenario E1
    
    Args:
        use_helics: If True, use HELICS for co-simulation. If False, run standalone.
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("="*70)
    logger.info("Scenario E1: Smart Grid with Renewable Integration")
    logger.info("="*70)
    
    # Create and initialize federate
    grid = SmartGridFederate("SmartGrid_E1", use_helics=use_helics)
    grid.initialize_components()
    grid.setup_federate()
    
    # Run simulation
    grid.run_simulation()
    
    # Generate report
    report = grid.generate_report()
    
    # Print report
    logger.info("\n" + "="*70)
    logger.info("SIMULATION REPORT")
    logger.info("="*70)
    logger.info(f"Scenario: {report['scenario']}")
    logger.info(f"\nComponents:")
    for key, value in report['components'].items():
        logger.info(f"  {key}: {value}")
    logger.info(f"\nMetrics:")
    for key, value in report['metrics'].items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.2f}")
        else:
            logger.info(f"  {key}: {value}")
    logger.info("="*70)
    
    # Cleanup
    grid.cleanup()
    
    return report
