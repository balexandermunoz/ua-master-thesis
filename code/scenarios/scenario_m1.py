"""
Scenario M1: Urban Traffic Congestion Management

5km x 5km urban grid with intelligent traffic management
- 25 signalized intersections (5x5 grid)
- 2,500 vehicles with varied origin-destination pairs
- Adaptive traffic signal control system
- Real-time traffic information system
"""

import helics as h
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class SignalPhase(Enum):
    """Traffic signal phases"""
    NORTH_SOUTH = "ns"
    EAST_WEST = "ew"


class Vehicle:
    """Vehicle agent with route and state"""
    
    def __init__(self, vehicle_id: int, origin: Tuple[int, int], destination: Tuple[int, int]):
        self.id = vehicle_id
        self.origin = origin
        self.destination = destination
        self.current_position = origin
        self.route: List[Tuple[int, int]] = []
        self.current_route_index = 0
        
        # State
        self.speed_mps = 0.0  # meters per second
        self.max_speed_mps = 13.9  # 50 km/h urban speed limit
        self.completed = False
        self.travel_time = 0.0
        self.total_delay = 0.0
        self.distance_traveled = 0.0
        
        # Emissions (simplified CO2 model)
        self.emissions_g = 0.0
        self.fuel_consumption_factor = 2.31  # g CO2/s at idle
        self.moving_factor = 0.15  # g CO2/m while moving
        
    def calculate_emissions(self, dt: float):
        """Calculate emissions based on speed"""
        if self.speed_mps < 1.0:  # Idling/stopped
            self.emissions_g += self.fuel_consumption_factor * dt
        else:  # Moving
            self.emissions_g += self.moving_factor * self.speed_mps * dt
            
    def update_position(self, new_position: Tuple[int, int], dt: float):
        """Update vehicle position and metrics"""
        if new_position != self.current_position:
            # Calculate distance (Manhattan distance in meters)
            distance = 500  # Grid spacing = 500m
            self.distance_traveled += distance
            self.speed_mps = distance / dt if dt > 0 else 0
        else:
            self.speed_mps = 0.0  # Stopped
            self.total_delay += dt
            
        self.current_position = new_position
        self.travel_time += dt
        self.calculate_emissions(dt)


class TrafficSignal:
    """Adaptive traffic signal controller"""
    
    def __init__(self, intersection_id: int, position: Tuple[int, int]):
        self.id = intersection_id
        self.position = position
        self.current_phase = SignalPhase.NORTH_SOUTH
        self.phase_time = 0.0
        
        # Adaptive parameters
        self.min_green_time = 15.0  # seconds
        self.max_green_time = 90.0  # seconds
        self.yellow_time = 3.0  # seconds
        
        # Queue sensing
        self.ns_queue_length = 0
        self.ew_queue_length = 0
        
    def update(self, dt: float, ns_demand: int, ew_demand: int) -> bool:
        """Update signal state with adaptive timing. Returns True if phase changed."""
        self.phase_time += dt
        self.ns_queue_length = ns_demand
        self.ew_queue_length = ew_demand
        
        # Adaptive green time based on queue ratio
        total_demand = ns_demand + ew_demand
        if total_demand > 0:
            if self.current_phase == SignalPhase.NORTH_SOUTH:
                target_green = self.min_green_time + (self.max_green_time - self.min_green_time) * (ns_demand / total_demand)
            else:
                target_green = self.min_green_time + (self.max_green_time - self.min_green_time) * (ew_demand / total_demand)
        else:
            target_green = self.min_green_time
            
        # Switch phase if time elapsed
        if self.phase_time >= target_green:
            self.current_phase = (SignalPhase.EAST_WEST if self.current_phase == SignalPhase.NORTH_SOUTH 
                                 else SignalPhase.NORTH_SOUTH)
            self.phase_time = 0.0
            return True
        return False
        
    def can_pass(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """Check if vehicle can pass through intersection"""
        # Determine direction of movement
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        
        # North-South movement
        if dx != 0 and dy == 0:
            return self.current_phase == SignalPhase.NORTH_SOUTH
        # East-West movement
        elif dx == 0 and dy != 0:
            return self.current_phase == SignalPhase.EAST_WEST
        return False


class TrafficNetwork:
    """Urban traffic network with 5x5 grid"""
    
    def __init__(self, grid_size: int = 5, spacing_m: float = 1000.0):
        self.grid_size = grid_size
        self.spacing = spacing_m
        self.intersections = {}
        self.signals = {}
        
        # Create intersections and signals
        for i in range(grid_size):
            for j in range(grid_size):
                pos = (i, j)
                intersection_id = i * grid_size + j
                self.intersections[pos] = intersection_id
                self.signals[pos] = TrafficSignal(intersection_id, pos)
                
    def get_neighbors(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get valid neighboring intersections"""
        x, y = position
        neighbors = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                neighbors.append((nx, ny))
        return neighbors
        
    def shortest_path(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Calculate shortest path (A* algorithm)"""
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
            
        from heapq import heappush, heappop
        
        frontier = [(0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}
        
        while frontier:
            _, current = heappop(frontier)
            
            if current == end:
                break
                
            for next_pos in self.get_neighbors(current):
                new_cost = cost_so_far[current] + 1
                if next_pos not in cost_so_far or new_cost < cost_so_far[next_pos]:
                    cost_so_far[next_pos] = new_cost
                    priority = new_cost + heuristic(next_pos, end)
                    heappush(frontier, (priority, next_pos))
                    came_from[next_pos] = current
                    
        # Reconstruct path
        path = []
        current = end
        while current is not None:
            path.append(current)
            current = came_from.get(current)
        path.reverse()
        return path
        
    def get_alternative_routes(self, start: Tuple[int, int], end: Tuple[int, int], 
                               num_routes: int = 3) -> List[List[Tuple[int, int]]]:
        """Generate alternative routes"""
        routes = []
        
        # Main shortest path
        main_route = self.shortest_path(start, end)
        routes.append(main_route)
        
        # Alternative routes with slight detours
        for _ in range(num_routes - 1):
            # Add randomness to create alternatives
            alt_route = []
            current = start
            while current != end:
                neighbors = self.get_neighbors(current)
                # Prefer direction toward goal but add randomness
                weights = []
                for n in neighbors:
                    if n not in alt_route:  # Avoid loops
                        dist_to_goal = abs(n[0] - end[0]) + abs(n[1] - end[1])
                        weights.append(1.0 / (dist_to_goal + 1) + np.random.random() * 0.3)
                    else:
                        weights.append(0.0)
                        
                if sum(weights) > 0:
                    weights = np.array(weights) / sum(weights)
                    next_pos = neighbors[np.random.choice(len(neighbors), p=weights)]
                    alt_route.append(current)
                    current = next_pos
                else:
                    break
                    
            alt_route.append(end)
            if len(alt_route) > 2:  # Valid route
                routes.append(alt_route)
                
        return routes


class TrafficSimulation:
    """Main traffic simulation with HELICS support"""
    
    def __init__(self, name: str = "TrafficSim", use_helics: bool = False, 
                 adaptive_signals: bool = True):
        self.name = name
        self.federate = None
        self.use_helics = use_helics
        self.adaptive_signals = adaptive_signals
        
        # Network
        self.network = TrafficNetwork(grid_size=5, spacing_m=1000.0)
        self.vehicles: List[Vehicle] = []
        
        # Simulation parameters
        self.time_step = 1.0  # 1 second
        self.sim_duration = 3 * 3600  # 3 hours in seconds
        
        # Metrics
        self.completed_vehicles = []
        self.average_travel_times = []
        self.total_emissions = []
        self.queue_lengths = {pos: [] for pos in self.network.intersections.keys()}
        self.intersection_delays = {pos: [] for pos in self.network.intersections.keys()}
        
    def initialize_vehicles(self, num_vehicles: int = 2500):
        """Initialize vehicles with random OD pairs"""
        logger.info(f"Initializing {num_vehicles} vehicles...")
        
        for i in range(num_vehicles):
            # Random origin and destination
            origin = (np.random.randint(0, 5), np.random.randint(0, 5))
            destination = (np.random.randint(0, 5), np.random.randint(0, 5))
            
            while origin == destination:
                destination = (np.random.randint(0, 5), np.random.randint(0, 5))
                
            vehicle = Vehicle(i, origin, destination)
            
            # Assign route (select from alternatives based on traffic info)
            routes = self.network.get_alternative_routes(origin, destination)
            vehicle.route = routes[np.random.randint(0, min(len(routes), 3))]
            
            self.vehicles.append(vehicle)
            
        logger.info(f"Created {len(self.vehicles)} vehicles")
        
    def update_traffic_signals(self, dt: float):
        """Update all traffic signals"""
        for pos, signal in self.network.signals.items():
            # Count vehicles waiting at intersection
            ns_demand = sum(1 for v in self.vehicles 
                           if not v.completed and v.current_position == pos and 
                           len(v.route) > v.current_route_index + 1)
            ew_demand = sum(1 for v in self.vehicles 
                           if not v.completed and v.current_position == pos)
            
            if self.adaptive_signals:
                signal.update(dt, ns_demand, ew_demand)
            else:
                # Fixed timing
                signal.update(dt, 1, 1)  # Equal weights
                
    def move_vehicles(self, dt: float):
        """Move all vehicles"""
        for vehicle in self.vehicles:
            if vehicle.completed:
                continue
                
            # Check if reached destination
            if vehicle.current_position == vehicle.destination:
                vehicle.completed = True
                self.completed_vehicles.append(vehicle)
                continue
                
            # Get next position in route
            if vehicle.current_route_index < len(vehicle.route) - 1:
                next_pos = vehicle.route[vehicle.current_route_index + 1]
                
                # Check traffic signal
                signal = self.network.signals[vehicle.current_position]
                if signal.can_pass(vehicle.current_position, next_pos):
                    # Move to next position
                    vehicle.update_position(next_pos, dt)
                    vehicle.current_route_index += 1
                else:
                    # Stopped at signal
                    vehicle.update_position(vehicle.current_position, dt)
            else:
                vehicle.completed = True
                
    def collect_metrics(self):
        """Collect simulation metrics"""
        # Queue lengths at each intersection
        for pos in self.network.intersections.keys():
            queue = sum(1 for v in self.vehicles 
                       if not v.completed and v.current_position == pos)
            self.queue_lengths[pos].append(queue)
            
        # Average emissions
        total_emissions = sum(v.emissions_g for v in self.vehicles)
        self.total_emissions.append(total_emissions)
        
        # Average travel time of completed vehicles
        if self.completed_vehicles:
            avg_time = np.mean([v.travel_time for v in self.completed_vehicles])
            self.average_travel_times.append(avg_time)
            
    def run_simulation(self):
        """Run 3-hour traffic simulation"""
        logger.info(f"Starting 3-hour simulation with {'adaptive' if self.adaptive_signals else 'fixed'} signals")
        
        self.initialize_vehicles()
        
        current_time = 0.0
        step = 0
        
        while current_time < self.sim_duration:
            # Update traffic signals
            self.update_traffic_signals(self.time_step)
            
            # Move vehicles
            self.move_vehicles(self.time_step)
            
            # Collect metrics
            self.collect_metrics()
            
            # Time advancement
            if self.use_helics and self.federate:
                current_time = h.helicsFederateRequestTime(self.federate, 
                                                           current_time + self.time_step)
            else:
                current_time += self.time_step
                
            step += 1
            if step % 900 == 0:  # Log every 15 minutes
                logger.info(f"Step {step}: Time {current_time/3600:.2f}h, "
                          f"Completed: {len(self.completed_vehicles)}/{len(self.vehicles)}, "
                          f"Avg Travel Time: {np.mean([v.travel_time for v in self.completed_vehicles]) if self.completed_vehicles else 0:.1f}s")
                          
        logger.info("Simulation completed")
        
    def generate_report(self) -> Dict:
        """Generate simulation report"""
        completed = [v for v in self.vehicles if v.completed]
        
        # Calculate average metrics
        avg_travel_time = np.mean([v.travel_time for v in completed]) if completed else 0
        avg_delay = np.mean([v.total_delay for v in completed]) if completed else 0
        total_emissions_kg = sum(v.emissions_g for v in self.vehicles) / 1000.0
        
        # Queue statistics
        max_queue = max(max(queues) for queues in self.queue_lengths.values() if queues)
        avg_queue = np.mean([np.mean(queues) for queues in self.queue_lengths.values() if queues])
        
        # Throughput
        throughput = len(completed) / (self.sim_duration / 3600.0)  # vehicles per hour
        
        report = {
            "scenario": "M1 - Urban Traffic Congestion Management",
            "simulation_duration_hours": 3,
            "time_step_seconds": 1,
            "signal_control": "adaptive" if self.adaptive_signals else "fixed",
            "components": {
                "total_vehicles": len(self.vehicles),
                "num_intersections": len(self.network.intersections),
                "network_size_km": 5,
            },
            "metrics": {
                "completed_vehicles": len(completed),
                "completion_rate_pct": (len(completed) / len(self.vehicles)) * 100,
                "avg_travel_time_min": avg_travel_time / 60.0,
                "avg_delay_min": avg_delay / 60.0,
                "total_emissions_kg_co2": total_emissions_kg,
                "emissions_per_vehicle_g": total_emissions_kg * 1000 / len(self.vehicles),
                "max_queue_length": max_queue,
                "avg_queue_length": avg_queue,
                "throughput_veh_per_hour": throughput,
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


def run_scenario_m1(use_helics: bool = False, adaptive_signals: bool = True):
    """Run Scenario M1
    
    Args:
        use_helics: If True, use HELICS for co-simulation
        adaptive_signals: If True, use adaptive signal control
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("="*70)
    logger.info("Scenario M1: Urban Traffic Congestion Management")
    logger.info("="*70)
    
    # Create and run simulation
    sim = TrafficSimulation("TrafficSim_M1", use_helics=use_helics, 
                           adaptive_signals=adaptive_signals)
    sim.run_simulation()
    
    # Generate report
    report = sim.generate_report()
    
    # Print report
    logger.info("\n" + "="*70)
    logger.info("SIMULATION REPORT")
    logger.info("="*70)
    logger.info(f"Scenario: {report['scenario']}")
    logger.info(f"Signal Control: {report['signal_control'].upper()}")
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
    sim.cleanup()
    
    return report


def compare_signal_strategies(use_helics: bool = False):
    """Compare fixed vs adaptive signal control"""
    logger.info("="*70)
    logger.info("COMPARING SIGNAL CONTROL STRATEGIES")
    logger.info("="*70)
    
    results = {}
    
    for adaptive in [False, True]:
        strategy = "adaptive" if adaptive else "fixed"
        logger.info(f"\nRunning {strategy} signal control...")
        report = run_scenario_m1(use_helics, adaptive)
        results[strategy] = report
        
    # Print comparison
    logger.info("\n" + "="*70)
    logger.info("STRATEGY COMPARISON")
    logger.info("="*70)
    
    for strategy, report in results.items():
        logger.info(f"\n{strategy.upper()}:")
        logger.info(f"  Avg Travel Time: {report['metrics']['avg_travel_time_min']:.2f} min")
        logger.info(f"  Avg Delay: {report['metrics']['avg_delay_min']:.2f} min")
        logger.info(f"  Total Emissions: {report['metrics']['total_emissions_kg_co2']:.2f} kg CO2")
        logger.info(f"  Throughput: {report['metrics']['throughput_veh_per_hour']:.0f} veh/h")
        
    return results
