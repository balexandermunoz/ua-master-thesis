"""
Basic Mosaik Framework Examples - Minimal Simulations for Testing

This file contains the simplest possible Mosaik simulations to verify
that Mosaik is installed correctly and working properly.

Examples:
1. Energy: Simple power generator and consumer
2. Mobility: Basic vehicle position update
"""

import mosaik
import mosaik.util
import mosaik_api_v3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# EXAMPLE 1: SIMPLE ENERGY SYSTEM - Simulator Definitions
# ============================================================================

META_GENERATOR = {
    'type': 'event-based',
    'models': {
        'Generator': {
            'public': True,
            'params': [],
            'attrs': ['power'],
        },
    },
}

class GeneratorSimulator(mosaik_api_v3.Simulator):
    """Simple power generator simulator"""
    
    def __init__(self):
        super().__init__(META_GENERATOR)
        self.eid_prefix = 'Generator_'
        self.entities = {}
        self.time_step = 1
        
    def init(self, sid, time_resolution=1.0):
        return self.meta
        
    def create(self, num, model):
        entities = []
        for i in range(num):
            eid = f'{self.eid_prefix}{i}'
            self.entities[eid] = {'power': 0.0}
            entities.append({'eid': eid, 'type': model})
        return entities
        
    def step(self, time, inputs, max_advance):
        # Generator produces power that varies with time
        for eid in self.entities:
            power_generated = 100.0 + (50.0 * (time / 10.0))  # 100-150 kW
            self.entities[eid]['power'] = power_generated
        return time + self.time_step
        
    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid][attr]
        return data


META_CONSUMER = {
    'type': 'event-based',
    'models': {
        'Consumer': {
            'public': True,
            'params': [],
            'attrs': ['power_received'],
        },
    },
}

class ConsumerSimulator(mosaik_api_v3.Simulator):
    """Simple power consumer simulator"""
    
    def __init__(self):
        super().__init__(META_CONSUMER)
        self.eid_prefix = 'Consumer_'
        self.entities = {}
        self.time_step = 1
        
    def init(self, sid, time_resolution=1.0):
        return self.meta
        
    def create(self, num, model):
        entities = []
        for i in range(num):
            eid = f'{self.eid_prefix}{i}'
            self.entities[eid] = {'power_received': 0.0}
            entities.append({'eid': eid, 'type': model})
        return entities
        
    def step(self, time, inputs, max_advance):
        # Consumer reads incoming power
        for eid, values in inputs.items():
            if 'power_received' in values:
                power_values = values['power_received'].values()
                total_power = sum(power_values) if power_values else 0.0
                self.entities[eid]['power_received'] = total_power
        return time + self.time_step
        
    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid][attr]
        return data


# Collector to display output in main process
class EnergyCollector(mosaik_api_v3.Simulator):
    """Collector to display energy data in main process"""
    
    def __init__(self):
        super().__init__({
            'type': 'event-based',
            'models': {
                'Collector': {
                    'public': True,
                    'params': [],
                    'attrs': ['gen_power', 'con_power'],
                }
            }
        })
        self.time_step = 1
        
    def init(self, sid, time_resolution=1.0):
        return self.meta
        
    def create(self, num, model):
        return [{'eid': 'Collector_0', 'type': model}]
        
    def step(self, time, inputs, max_advance):
        for eid, attrs in inputs.items():
            gen_power = list(attrs.get('gen_power', {}).values())[0] if 'gen_power' in attrs else 0.0
            con_power = list(attrs.get('con_power', {}).values())[0] if 'con_power' in attrs else 0.0
            print(f"Time {time}s: Generator={gen_power:.2f} kW, Consumer received={con_power:.2f} kW")
        return time + self.time_step


def example_energy_mosaik():
    """
    Most basic energy example in Mosaik: One generator publishing power,
    one consumer subscribing to that power value.
    
    This demonstrates:
    - Creating simulators
    - Starting entities
    - Connecting data flows
    - Running simulation
    """
    print("=" * 70)
    print("EXAMPLE 1: Simple Energy System (Generator -> Consumer) - Mosaik")
    print("=" * 70)
    
    # Simulation configuration
    SIM_CONFIG = {
        'GeneratorSim': {
            'python': 'Examples_Mosaik:GeneratorSimulator',
        },
        'ConsumerSim': {
            'python': 'Examples_Mosaik:ConsumerSimulator',
        },
        'Collector': {
            'python': 'Examples_Mosaik:EnergyCollector',
        },
    }
    
    # Create world
    world = mosaik.World(SIM_CONFIG)
    
    # Start simulators
    generator_sim = world.start('GeneratorSim')
    consumer_sim = world.start('ConsumerSim')
    collector_sim = world.start('Collector')
    
    # Create entities
    generator = generator_sim.Generator.create(1)[0]
    consumer = consumer_sim.Consumer.create(1)[0]
    collector = collector_sim.Collector.create(1)[0]
    
    # Connect generator output to consumer input
    world.connect(generator, consumer, ('power', 'power_received'))
    
    # Connect to collector for display
    world.connect(generator, collector, ('power', 'gen_power'))
    world.connect(consumer, collector, ('power_received', 'con_power'))
    
    print("\nStarting simulation for 10 seconds...")
    print("-" * 70)
    
    # Run simulation (output will appear from step methods)
    world.run(until=10)
    
    print("-" * 70)
    
    print("-" * 70)
    print("✓ Energy example completed successfully!\n")


# ============================================================================
# EXAMPLE 2: SIMPLE MOBILITY SYSTEM - Simulator Definitions
# ============================================================================

META_VEHICLE = {
    'type': 'event-based',
    'models': {
        'Vehicle': {
            'public': True,
            'params': [],
            'attrs': ['position_x', 'position_y', 'speed'],
        },
    },
}

class VehicleSimulator(mosaik_api_v3.Simulator):
    """Simple vehicle simulator"""
    
    def __init__(self):
        super().__init__(META_VEHICLE)
        self.eid_prefix = 'Vehicle_'
        self.entities = {}
        self.time_step = 1
        
    def init(self, sid, time_resolution=1.0):
        return self.meta
        
    def create(self, num, model):
        entities = []
        for i in range(num):
            eid = f'{self.eid_prefix}{i}'
            self.entities[eid] = {
                'position_x': 0.0,
                'position_y': 0.0,
                'speed': 10.0  # m/s
            }
            entities.append({'eid': eid, 'type': model})
        return entities
        
    def step(self, time, inputs, max_advance):
        # Vehicle moves along x-axis at constant speed
        for eid in self.entities:
            speed = self.entities[eid]['speed']
            self.entities[eid]['position_x'] += speed * self.time_step
            # position_y remains 0
        return time + self.time_step
        
    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid][attr]
        return data


META_MONITOR = {
    'type': 'event-based',
    'models': {
        'Monitor': {
            'public': True,
            'params': [],
            'attrs': ['vehicle_x', 'vehicle_y', 'vehicle_speed'],
        },
    },
}

class MonitorSimulator(mosaik_api_v3.Simulator):
    """Traffic monitor simulator"""
    
    def __init__(self):
        super().__init__(META_MONITOR)
        self.eid_prefix = 'Monitor_'
        self.entities = {}
        self.time_step = 1
        
    def init(self, sid, time_resolution=1.0):
        return self.meta
        
    def create(self, num, model):
        entities = []
        for i in range(num):
            eid = f'{self.eid_prefix}{i}'
            self.entities[eid] = {
                'vehicle_x': 0.0,
                'vehicle_y': 0.0,
                'vehicle_speed': 0.0
            }
            entities.append({'eid': eid, 'type': model})
        return entities
        
    def step(self, time, inputs, max_advance):
        # Monitor receives vehicle data
        for eid, values in inputs.items():
            if 'vehicle_x' in values:
                x_values = list(values['vehicle_x'].values())
                self.entities[eid]['vehicle_x'] = x_values[0] if x_values else 0.0
            if 'vehicle_y' in values:
                y_values = list(values['vehicle_y'].values())
                self.entities[eid]['vehicle_y'] = y_values[0] if y_values else 0.0
            if 'vehicle_speed' in values:
                speed_values = list(values['vehicle_speed'].values())
                self.entities[eid]['vehicle_speed'] = speed_values[0] if speed_values else 0.0
        
        return time + self.time_step
        
    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid][attr]
        return data


# Collector to display output in main process
class MobilityCollector(mosaik_api_v3.Simulator):
    """Collector to display mobility data in main process"""
    
    def __init__(self):
        super().__init__({
            'type': 'event-based',
            'models': {
                'Collector': {
                    'public': True,
                    'params': [],
                    'attrs': ['pos_x', 'pos_y', 'speed'],
                }
            }
        })
        self.time_step = 1
        
    def init(self, sid, time_resolution=1.0):
        return self.meta
        
    def create(self, num, model):
        return [{'eid': 'Collector_0', 'type': model}]
        
    def step(self, time, inputs, max_advance):
        for eid, attrs in inputs.items():
            pos_x = list(attrs.get('pos_x', {}).values())[0] if 'pos_x' in attrs else 0.0
            pos_y = list(attrs.get('pos_y', {}).values())[0] if 'pos_y' in attrs else 0.0
            speed = list(attrs.get('speed', {}).values())[0] if 'speed' in attrs else 0.0
            print(f"Time {time}s: Vehicle Position=({pos_x:.1f}, {pos_y:.1f}) m, Speed={speed:.1f} m/s")
        return time + self.time_step


def example_mobility_mosaik():
    """
    Most basic mobility example in Mosaik: One vehicle moving along a path,
    one traffic monitor observing its position.
    
    This demonstrates:
    - Multiple attribute connections
    - Position tracking over time
    - Vehicle state updates
    """
    print("=" * 70)
    print("EXAMPLE 2: Simple Mobility System (Vehicle -> Monitor) - Mosaik")
    print("=" * 70)
    
    # Simulation configuration
    SIM_CONFIG = {
        'VehicleSim': {
            'python': 'Examples_Mosaik:VehicleSimulator',
        },
        'MonitorSim': {
            'python': 'Examples_Mosaik:MonitorSimulator',
        },
        'Collector': {
            'python': 'Examples_Mosaik:MobilityCollector',
        },
    }
    
    # Create world
    world = mosaik.World(SIM_CONFIG)
    
    # Start simulators
    vehicle_sim = world.start('VehicleSim')
    monitor_sim = world.start('MonitorSim')
    collector_sim = world.start('Collector')
    
    # Create entities
    vehicle = vehicle_sim.Vehicle.create(1)[0]
    monitor = monitor_sim.Monitor.create(1)[0]
    collector = collector_sim.Collector.create(1)[0]
    
    # Connect vehicle outputs to monitor inputs
    world.connect(vehicle, monitor, ('position_x', 'vehicle_x'))
    world.connect(vehicle, monitor, ('position_y', 'vehicle_y'))
    world.connect(vehicle, monitor, ('speed', 'vehicle_speed'))
    
    # Connect monitor to collector for display
    world.connect(monitor, collector, ('vehicle_x', 'pos_x'))
    world.connect(monitor, collector, ('vehicle_y', 'pos_y'))
    world.connect(monitor, collector, ('vehicle_speed', 'speed'))
    
    print("\nStarting simulation for 10 seconds...")
    print("Vehicle moving at constant speed along X-axis")
    print("-" * 70)
    
    # Run simulation (output will appear from step methods)
    world.run(until=10)
    
    print("-" * 70)
    print("✓ Mobility example completed successfully!\n")


# ============================================================================
# MAIN: RUN EXAMPLES
# ============================================================================

def main():
    """Run all basic Mosaik examples"""
    print("\n" + "=" * 70)
    print("MOSAIK FRAMEWORK BASIC EXAMPLES - Verification Tests")
    print("=" * 70)
    print("\nThese examples demonstrate the most basic Mosaik functionality:")
    print("1. Energy: Simple generator-consumer power exchange")
    print("2. Mobility: Simple vehicle position tracking")
    print("\nIf these run successfully, Mosaik is properly installed!")
    print("=" * 70 + "\n")
    
    try:
        # Run energy example
        example_energy_mosaik()
        
        # Run mobility example
        example_mobility_mosaik()
        
        # Summary
        print("\n" + "=" * 70)
        print("✓ ALL MOSAIK EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nMosaik Framework is working correctly. You can now:")
        print("- Compare with HELICS examples (Examples.py)")
        print("- Build your own Mosaik co-simulation models")
        print("- Explore framework differences and capabilities")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        print("Please check your Mosaik installation.")
        print("Install with: pip install mosaik mosaik-api")
        raise


if __name__ == "__main__":
    main()
