"""
Scenario E2: Electric Vehicle Charging Infrastructure

Modified IEEE 13-node test feeder with EV charging impact analysis
- 100 electric vehicles with varying arrival times and charging needs
- 20 Level 2 charging stations (7.2 kW) in residential areas
- 5 DC fast charging stations (50 kW) in commercial zones
- Time-of-use tariff structure
"""

import helics as h
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ChargingStrategy(Enum):
    """Charging control strategies"""
    UNCOORDINATED = "uncoordinated"  # Immediate charging upon arrival
    SMART = "smart"  # Coordinated charging with grid awareness
    V2G = "v2g"  # Vehicle-to-Grid capable


class ChargerType(Enum):
    """EV charger types"""
    LEVEL_2 = "level_2"  # 7.2 kW residential
    DC_FAST = "dc_fast"  # 50 kW commercial


class ElectricVehicle:
    """Electric vehicle model with battery and charging characteristics"""
    
    def __init__(self, ev_id: int, battery_capacity_kwh: float, initial_soc: float):
        self.id = ev_id
        self.battery_capacity_kwh = battery_capacity_kwh
        self.soc = initial_soc  # State of charge (0-1)
        self.soc_min = 0.1  # Minimum SOC (10%)
        self.soc_max = 0.9  # Maximum SOC (90%, battery health)
        self.soc_target = 0.8  # Target SOC before departure
        
        # Charging parameters
        self.max_charge_rate_kw = 11.0  # Vehicle onboard charger limit
        self.charging_efficiency = 0.90  # 90% efficiency
        
        # V2G parameters
        self.v2g_enabled = np.random.random() > 0.5  # 50% V2G capable
        self.max_discharge_rate_kw = 10.0 if self.v2g_enabled else 0.0
        
        # Trip characteristics
        self.arrival_time = 0.0  # seconds
        self.departure_time = 0.0  # seconds
        self.is_connected = False
        self.charging_station_id = None
        
        # Energy tracking
        self.energy_charged_kwh = 0.0
        self.energy_discharged_kwh = 0.0
        self.charging_cost = 0.0
        
    def connect(self, arrival_time: float, departure_time: float, station_id: int):
        """Connect vehicle to charging station"""
        self.arrival_time = arrival_time
        self.departure_time = departure_time
        self.charging_station_id = station_id
        self.is_connected = True
        
    def disconnect(self):
        """Disconnect vehicle from charging station"""
        self.is_connected = False
        self.charging_station_id = None
        
    def charge(self, power_kw: float, dt_hours: float, price_per_kwh: float) -> float:
        """Charge the vehicle battery"""
        if not self.is_connected:
            return 0.0
            
        # Limit by vehicle charger, available capacity, and requested power
        max_charge = min(power_kw, self.max_charge_rate_kw)
        available_capacity = (self.soc_max - self.soc) * self.battery_capacity_kwh
        energy_charged = min(max_charge * dt_hours * self.charging_efficiency, 
                            available_capacity)
        
        # Update SOC
        self.soc += energy_charged / self.battery_capacity_kwh
        self.energy_charged_kwh += energy_charged
        self.charging_cost += energy_charged * price_per_kwh
        
        return energy_charged / dt_hours  # Return average power
        
    def discharge(self, power_kw: float, dt_hours: float, price_per_kwh: float) -> float:
        """Discharge battery for V2G"""
        if not self.is_connected or not self.v2g_enabled:
            return 0.0
            
        # Limit by discharge rate and available energy
        max_discharge = min(power_kw, self.max_discharge_rate_kw)
        available_energy = (self.soc - self.soc_min) * self.battery_capacity_kwh
        energy_discharged = min(max_discharge * dt_hours, available_energy)
        
        # Update SOC
        self.soc -= energy_discharged / self.battery_capacity_kwh
        self.energy_discharged_kwh += energy_discharged
        # V2G compensation (sell back to grid)
        self.charging_cost -= energy_discharged * price_per_kwh * 1.2  # 20% premium
        
        return energy_discharged / self.charging_efficiency  # Account for losses
        
    def get_energy_need_kwh(self) -> float:
        """Calculate energy needed to reach target SOC"""
        return max(0, (self.soc_target - self.soc) * self.battery_capacity_kwh)
        
    def get_available_time_hours(self, current_time: float) -> float:
        """Calculate remaining connection time"""
        if not self.is_connected:
            return 0.0
        return max(0, (self.departure_time - current_time) / 3600.0)


class ChargingStation:
    """EV charging station model"""
    
    def __init__(self, station_id: int, charger_type: ChargerType, 
                 node_id: int, num_ports: int = 1):
        self.id = station_id
        self.charger_type = charger_type
        self.node_id = node_id
        self.num_ports = num_ports
        
        # Charger specifications
        if charger_type == ChargerType.LEVEL_2:
            self.max_power_kw = 7.2
            self.area_type = "residential"
        else:  # DC_FAST
            self.max_power_kw = 50.0
            self.area_type = "commercial"
            
        # Connected vehicles
        self.connected_vehicles: List[ElectricVehicle] = []
        self.total_power_kw = 0.0
        
    def can_accept_vehicle(self) -> bool:
        """Check if station has available ports"""
        return len(self.connected_vehicles) < self.num_ports
        
    def add_vehicle(self, vehicle: ElectricVehicle):
        """Connect vehicle to this station"""
        if self.can_accept_vehicle():
            self.connected_vehicles.append(vehicle)
            return True
        return False
        
    def remove_vehicle(self, vehicle: ElectricVehicle):
        """Disconnect vehicle from this station"""
        if vehicle in self.connected_vehicles:
            self.connected_vehicles.remove(vehicle)


class TransformerModel:
    """Distribution transformer model"""
    
    def __init__(self, transformer_id: int, rated_capacity_kva: float, node_id: int):
        self.id = transformer_id
        self.rated_capacity_kva = rated_capacity_kva
        self.node_id = node_id
        self.loading_history = []
        self.overload_count = 0
        
    def calculate_loading(self, power_kw: float, power_factor: float = 0.95) -> float:
        """Calculate transformer loading percentage"""
        apparent_power_kva = power_kw / power_factor
        loading_pct = (apparent_power_kva / self.rated_capacity_kva) * 100
        
        self.loading_history.append(loading_pct)
        if loading_pct > 100:
            self.overload_count += 1
            
        return loading_pct


class TimeOfUseTariff:
    """Time-of-use electricity pricing structure"""
    
    def __init__(self):
        # Price per kWh for different periods
        self.off_peak_price = 0.08  # $0.08/kWh (00:00-07:00, 23:00-24:00)
        self.mid_peak_price = 0.12  # $0.12/kWh (07:00-17:00, 21:00-23:00)
        self.on_peak_price = 0.20   # $0.20/kWh (17:00-21:00)
        
    def get_price(self, hour: float) -> float:
        """Get electricity price for given hour"""
        if 0 <= hour < 7 or 23 <= hour < 24:
            return self.off_peak_price
        elif 17 <= hour < 21:
            return self.on_peak_price
        else:
            return self.mid_peak_price


class SmartChargingController:
    """Smart charging optimization controller"""
    
    def __init__(self, stations: List[ChargingStation], tariff: TimeOfUseTariff):
        self.stations = stations
        self.tariff = tariff
        
    def optimize_charging(self, current_time: float, grid_load_kw: float,
                         grid_capacity_kw: float) -> Dict[int, float]:
        """
        Optimize charging power allocation for all connected vehicles.
        Returns dictionary of {vehicle_id: power_kw}
        """
        power_allocation = {}
        
        # Get all connected vehicles
        all_vehicles = []
        for station in self.stations:
            all_vehicles.extend(station.connected_vehicles)
            
        if not all_vehicles:
            return power_allocation
            
        # Calculate priorities based on:
        # 1. Energy need
        # 2. Time until departure
        # 3. Current price
        hour = (current_time / 3600.0) % 24
        current_price = self.tariff.get_price(hour)
        
        priorities = []
        for vehicle in all_vehicles:
            energy_need = vehicle.get_energy_need_kwh()
            time_available = vehicle.get_available_time_hours(current_time)
            
            if time_available > 0:
                # Priority: higher if more urgent (less time, more energy needed)
                urgency = energy_need / max(time_available, 0.1)
                # Lower priority during peak prices (unless urgent)
                price_factor = 1.0 if current_price < 0.15 else 0.5
                priority = urgency * price_factor
                priorities.append((vehicle, priority, energy_need))
                
        # Sort by priority (highest first)
        priorities.sort(key=lambda x: x[1], reverse=True)
        
        # Allocate available grid capacity
        available_capacity = max(0, grid_capacity_kw - grid_load_kw)
        
        for vehicle, priority, energy_need in priorities:
            if available_capacity <= 0:
                power_allocation[vehicle.id] = 0.0
                continue
                
            # Find vehicle's station
            station = None
            for s in self.stations:
                if vehicle in s.connected_vehicles:
                    station = s
                    break
                    
            if station:
                # Allocate power (limited by station, vehicle, and grid)
                max_power = min(station.max_power_kw, 
                              vehicle.max_charge_rate_kw,
                              available_capacity)
                power_allocation[vehicle.id] = max_power
                available_capacity -= max_power
                
        return power_allocation


class EVChargingFederate:
    """HELICS federate for EV charging simulation"""
    
    def __init__(self, name: str = "EVCharging", use_helics: bool = False,
                 strategy: ChargingStrategy = ChargingStrategy.SMART):
        self.name = name
        self.federate = None
        self.use_helics = use_helics
        self.strategy = strategy
        
        # Grid components
        self.vehicles: List[ElectricVehicle] = []
        self.charging_stations: List[ChargingStation] = []
        self.transformers: List[TransformerModel] = []
        self.tariff = TimeOfUseTariff()
        self.smart_controller = None
        
        # Simulation parameters
        self.time_step = 5 * 60  # 5 minutes in seconds
        self.sim_duration = 24 * 3600  # 24 hours in seconds
        
        # Grid parameters (IEEE 13-node)
        self.num_nodes = 13
        self.grid_capacity_kw = 5000  # Total grid capacity
        self.base_load_kw = 2000  # Base residential/commercial load
        
        # Metrics
        self.load_profiles = {"uncoordinated": [], "smart": [], "base": []}
        self.transformer_loading = []
        self.voltage_deviations = []
        self.total_charging_cost = 0.0
        self.peak_load_kw = 0.0
        self.v2g_energy_kwh = 0.0
        
    def initialize_components(self):
        """Initialize all EV charging components"""
        logger.info("Initializing EV charging infrastructure...")
        
        # Create 100 electric vehicles
        for i in range(100):
            # Battery capacities: 40-100 kWh (various EV models)
            capacity = np.random.uniform(40.0, 100.0)
            # Initial SOC: 20-50% (arrived from trip)
            initial_soc = np.random.uniform(0.2, 0.5)
            self.vehicles.append(ElectricVehicle(i, capacity, initial_soc))
            
        # Create 20 Level 2 charging stations (residential, nodes 1-8)
        for i in range(20):
            node_id = np.random.randint(1, 9)
            station = ChargingStation(i, ChargerType.LEVEL_2, node_id, num_ports=1)
            self.charging_stations.append(station)
            
        # Create 5 DC fast charging stations (commercial, nodes 9-13)
        for i in range(5):
            node_id = np.random.randint(9, 14)
            station = ChargingStation(20 + i, ChargerType.DC_FAST, node_id, num_ports=2)
            self.charging_stations.append(station)
            
        # Create transformers for each node
        for i in range(self.num_nodes):
            # Residential transformers: 150-300 kVA
            # Commercial transformers: 500-1000 kVA
            if i < 8:
                capacity = np.random.uniform(150, 300)
            else:
                capacity = np.random.uniform(500, 1000)
            self.transformers.append(TransformerModel(i, capacity, i + 1))
            
        # Initialize smart charging controller
        self.smart_controller = SmartChargingController(self.charging_stations, self.tariff)
        
        logger.info(f"Created {len(self.vehicles)} EVs, "
                   f"{len(self.charging_stations)} charging stations, "
                   f"{len(self.transformers)} transformers")
                   
    def generate_arrival_patterns(self):
        """Generate realistic EV arrival and departure times"""
        for i, vehicle in enumerate(self.vehicles):
            # Residential charging (evening arrival)
            if i < 80:  # 80% charge at home
                # Arrival: 17:00-20:00 (return from work)
                arrival_hour = np.random.normal(18.5, 1.0)
                arrival_hour = np.clip(arrival_hour, 17, 20)
                
                # Departure: 07:00-09:00 next day (leave for work)
                departure_hour = np.random.normal(8.0, 0.5)
                departure_hour = np.clip(departure_hour, 7, 9)
                if departure_hour < arrival_hour:
                    departure_hour += 24
                    
                # Find available Level 2 station
                for station in self.charging_stations:
                    if (station.charger_type == ChargerType.LEVEL_2 and 
                        station.can_accept_vehicle()):
                        arrival_time = arrival_hour * 3600
                        departure_time = departure_hour * 3600
                        vehicle.connect(arrival_time, departure_time, station.id)
                        station.add_vehicle(vehicle)
                        break
                        
            # Commercial/DC fast charging (daytime)
            else:  # 20% use fast charging
                # Arrival: random during day
                arrival_hour = np.random.uniform(8, 18)
                # Stay for 30-60 minutes only
                departure_hour = arrival_hour + np.random.uniform(0.5, 1.0)
                
                # Find available DC fast station
                for station in self.charging_stations:
                    if (station.charger_type == ChargerType.DC_FAST and 
                        station.can_accept_vehicle()):
                        arrival_time = arrival_hour * 3600
                        departure_time = departure_hour * 3600
                        vehicle.connect(arrival_time, departure_time, station.id)
                        station.add_vehicle(vehicle)
                        break
                        
    def calculate_base_load(self, hour: float) -> float:
        """Calculate base load without EV charging"""
        # Typical daily load profile
        if 0 <= hour < 6:
            load_factor = 0.5
        elif 6 <= hour < 9:
            load_factor = 0.75
        elif 9 <= hour < 17:
            load_factor = 0.8
        elif 17 <= hour < 22:
            load_factor = 1.0  # Peak
        else:
            load_factor = 0.6
            
        return self.base_load_kw * load_factor
        
    def uncoordinated_charging(self, current_time: float) -> Dict[int, float]:
        """Uncoordinated charging: charge immediately at max power"""
        power_allocation = {}
        
        for station in self.charging_stations:
            for vehicle in station.connected_vehicles:
                if vehicle.soc < vehicle.soc_target:
                    # Charge at maximum rate
                    power_allocation[vehicle.id] = min(
                        station.max_power_kw,
                        vehicle.max_charge_rate_kw
                    )
                else:
                    power_allocation[vehicle.id] = 0.0
                    
        return power_allocation
        
    def run_simulation(self):
        """Run the 24-hour EV charging simulation"""
        logger.info(f"Starting 24-hour simulation with {self.strategy.value} charging strategy")
        
        # Generate arrival/departure patterns
        self.generate_arrival_patterns()
        
        current_time = 0.0
        step = 0
        
        while current_time < self.sim_duration:
            hour_of_day = (current_time / 3600.0) % 24
            dt_hours = self.time_step / 3600.0
            
            # Calculate base load
            base_load = self.calculate_base_load(hour_of_day)
            self.load_profiles["base"].append(base_load)
            
            # Handle vehicle arrivals and departures
            for vehicle in self.vehicles:
                if not vehicle.is_connected and abs(current_time - vehicle.arrival_time) < self.time_step:
                    # Vehicle arriving - already connected in generate_arrival_patterns
                    pass
                elif vehicle.is_connected and current_time >= vehicle.departure_time:
                    # Vehicle departing
                    for station in self.charging_stations:
                        if vehicle in station.connected_vehicles:
                            station.remove_vehicle(vehicle)
                            vehicle.disconnect()
                            break
                            
            # Get electricity price
            price = self.tariff.get_price(hour_of_day)
            
            # Determine charging power allocation based on strategy
            if self.strategy == ChargingStrategy.UNCOORDINATED:
                power_allocation = self.uncoordinated_charging(current_time)
            else:  # SMART or V2G
                power_allocation = self.smart_controller.optimize_charging(
                    current_time, base_load, self.grid_capacity_kw
                )
                
            # Apply charging
            total_ev_load = 0.0
            for vehicle in self.vehicles:
                if vehicle.id in power_allocation:
                    power = power_allocation[vehicle.id]
                    if power > 0:
                        actual_power = vehicle.charge(power, dt_hours, price)
                        total_ev_load += actual_power
                    # V2G discharge (only in V2G strategy)
                    elif self.strategy == ChargingStrategy.V2G and power < 0:
                        # Discharge during peak hours if beneficial
                        if hour_of_day >= 17 and hour_of_day < 21:
                            discharged = vehicle.discharge(abs(power), dt_hours, price)
                            total_ev_load -= discharged
                            self.v2g_energy_kwh += discharged * dt_hours
                            
            # Total load
            total_load = base_load + total_ev_load
            self.load_profiles[self.strategy.value].append(total_load)
            self.peak_load_kw = max(self.peak_load_kw, total_load)
            
            # Calculate transformer loading
            for transformer in self.transformers:
                # Simple load distribution across nodes
                node_load = total_load / self.num_nodes
                loading = transformer.calculate_loading(node_load)
                
            # Voltage deviation (simplified model)
            voltage_deviation = min(0.05, total_load / self.grid_capacity_kw * 0.05)
            self.voltage_deviations.append(voltage_deviation)
            
            # Update station power
            for station in self.charging_stations:
                station.total_power_kw = sum(
                    power_allocation.get(v.id, 0) for v in station.connected_vehicles
                )
                
            # Time advancement
            if self.use_helics and self.federate:
                current_time = h.helicsFederateRequestTime(self.federate, 
                                                           current_time + self.time_step)
            else:
                current_time += self.time_step
                
            step += 1
            if step % 72 == 0:  # Log every 6 hours
                logger.info(f"Step {step}: Hour {hour_of_day:.1f}, "
                          f"Base Load: {base_load:.1f} kW, "
                          f"EV Load: {total_ev_load:.1f} kW, "
                          f"Total: {total_load:.1f} kW")
                          
        logger.info("Simulation completed")
        
        # Calculate total costs
        self.total_charging_cost = sum(v.charging_cost for v in self.vehicles)
        
    def generate_report(self) -> Dict:
        """Generate simulation report"""
        # Transformer statistics
        max_loading = max(max(t.loading_history) for t in self.transformers)
        avg_loading = np.mean([np.mean(t.loading_history) for t in self.transformers])
        total_overloads = sum(t.overload_count for t in self.transformers)
        
        # Vehicle statistics
        total_energy_charged = sum(v.energy_charged_kwh for v in self.vehicles)
        avg_final_soc = np.mean([v.soc for v in self.vehicles])
        v2g_capable_count = sum(1 for v in self.vehicles if v.v2g_enabled)
        
        report = {
            "scenario": "E2 - Electric Vehicle Charging Infrastructure",
            "simulation_duration_hours": 24,
            "time_step_minutes": 5,
            "charging_strategy": self.strategy.value,
            "components": {
                "num_vehicles": len(self.vehicles),
                "level_2_stations": sum(1 for s in self.charging_stations 
                                       if s.charger_type == ChargerType.LEVEL_2),
                "dc_fast_stations": sum(1 for s in self.charging_stations 
                                       if s.charger_type == ChargerType.DC_FAST),
                "num_transformers": len(self.transformers),
                "v2g_capable_vehicles": v2g_capable_count,
            },
            "metrics": {
                "peak_load_kw": self.peak_load_kw,
                "total_energy_charged_kwh": total_energy_charged,
                "total_charging_cost_usd": self.total_charging_cost,
                "avg_cost_per_vehicle_usd": self.total_charging_cost / len(self.vehicles),
                "avg_final_soc": avg_final_soc,
                "max_transformer_loading_pct": max_loading,
                "avg_transformer_loading_pct": avg_loading,
                "transformer_overload_count": total_overloads,
                "max_voltage_deviation_pu": max(self.voltage_deviations),
                "v2g_energy_provided_kwh": self.v2g_energy_kwh,
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


def run_scenario_e2(use_helics: bool = False, 
                   strategy: ChargingStrategy = ChargingStrategy.SMART):
    """Main function to run Scenario E2
    
    Args:
        use_helics: If True, use HELICS for co-simulation
        strategy: Charging control strategy to use
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("="*70)
    logger.info("Scenario E2: Electric Vehicle Charging Infrastructure")
    logger.info("="*70)
    
    # Create and initialize federate
    ev_sim = EVChargingFederate("EVCharging_E2", use_helics=use_helics, strategy=strategy)
    ev_sim.initialize_components()
    
    # Run simulation
    ev_sim.run_simulation()
    
    # Generate report
    report = ev_sim.generate_report()
    
    # Print report
    logger.info("\n" + "="*70)
    logger.info("SIMULATION REPORT")
    logger.info("="*70)
    logger.info(f"Scenario: {report['scenario']}")
    logger.info(f"Strategy: {report['charging_strategy'].upper()}")
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
    ev_sim.cleanup()
    
    return report


def compare_strategies(use_helics: bool = False):
    """Compare different charging strategies"""
    logger.info("="*70)
    logger.info("COMPARING CHARGING STRATEGIES")
    logger.info("="*70)
    
    strategies = [
        ChargingStrategy.UNCOORDINATED,
        ChargingStrategy.SMART,
        ChargingStrategy.V2G
    ]
    
    results = {}
    for strategy in strategies:
        logger.info(f"\nRunning {strategy.value} strategy...")
        report = run_scenario_e2(use_helics, strategy)
        results[strategy.value] = report
        
    # Print comparison
    logger.info("\n" + "="*70)
    logger.info("STRATEGY COMPARISON")
    logger.info("="*70)
    
    for strategy_name, report in results.items():
        logger.info(f"\n{strategy_name.upper()}:")
        logger.info(f"  Peak Load: {report['metrics']['peak_load_kw']:.2f} kW")
        logger.info(f"  Total Cost: ${report['metrics']['total_charging_cost_usd']:.2f}")
        logger.info(f"  Max Transformer Loading: {report['metrics']['max_transformer_loading_pct']:.1f}%")
        logger.info(f"  Overloads: {report['metrics']['transformer_overload_count']}")
        
    return results
