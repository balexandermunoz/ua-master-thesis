"""
Basic HELICS Examples - Minimal Simulations for Testing

This file contains the simplest possible HELICS simulations to verify
that HELICS is installed correctly and working properly.

Examples:
1. Energy: Simple power generator and consumer
2. Mobility: Basic vehicle position update
"""

import helics as h
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# EXAMPLE 1: SIMPLE ENERGY SYSTEM
# ============================================================================

def example_energy_simple():
    """
    Most basic energy example: One generator publishing power,
    one consumer subscribing to that power value.
    
    This demonstrates:
    - Creating federates
    - Publishing and subscribing to values
    - Time coordination
    """
    logger.info("=" * 70)
    logger.info("EXAMPLE 1: Simple Energy System (Generator -> Consumer)")
    logger.info("=" * 70)
    
    # Create broker (coordinates the federation)
    broker = h.helicsCreateBroker("zmq", "broker", "--federates=2")
    time.sleep(0.5)  # Give broker time to start
    
    # Create generator federate (produces power)
    fed_info_gen = h.helicsCreateFederateInfo()
    h.helicsFederateInfoSetCoreTypeFromString(fed_info_gen, "zmq")
    h.helicsFederateInfoSetCoreInitString(fed_info_gen, "--federates=1")
    h.helicsFederateInfoSetTimeProperty(fed_info_gen, h.helics_property_time_delta, 1.0)
    generator = h.helicsCreateValueFederate("Generator", fed_info_gen)
    
    # Create consumer federate (consumes power)
    fed_info_con = h.helicsCreateFederateInfo()
    h.helicsFederateInfoSetCoreTypeFromString(fed_info_con, "zmq")
    h.helicsFederateInfoSetCoreInitString(fed_info_con, "--federates=1")
    h.helicsFederateInfoSetTimeProperty(fed_info_con, h.helics_property_time_delta, 1.0)
    consumer = h.helicsCreateValueFederate("Consumer", fed_info_con)
    
    # Generator publishes power output (kW)
    pub_power = h.helicsFederateRegisterGlobalPublication(
        generator, "generator/power", h.helics_data_type_double, ""
    )
    
    # Consumer subscribes to power
    sub_power = h.helicsFederateRegisterSubscription(
        consumer, "generator/power", ""
    )
    
    logger.info("Entering initialization mode...")
    # Enter initialization mode asynchronously to avoid blocking
    h.helicsFederateEnterInitializingModeAsync(generator)
    h.helicsFederateEnterInitializingModeAsync(consumer)
    h.helicsFederateEnterInitializingModeComplete(generator)
    h.helicsFederateEnterInitializingModeComplete(consumer)
    
    logger.info("Entering execution mode...")
    h.helicsFederateEnterExecutingModeAsync(generator)
    h.helicsFederateEnterExecutingModeAsync(consumer)
    h.helicsFederateEnterExecutingModeComplete(generator)
    h.helicsFederateEnterExecutingModeComplete(consumer)
    
    # Simulation parameters
    total_time = 10.0  # seconds
    time_step = 1.0
    
    logger.info(f"\nStarting simulation for {total_time} seconds...")
    logger.info("-" * 70)
    
    # Simulation loop
    current_time = 0.0
    while current_time < total_time:
        # Generator: produce power (varies with time)
        power_generated = 100.0 + (50.0 * (current_time / total_time))  # 100-150 kW
        h.helicsPublicationPublishDouble(pub_power, power_generated)
        
        # Request time advancement
        current_time = h.helicsFederateRequestTime(generator, current_time + time_step)
        consumer_time = h.helicsFederateRequestTime(consumer, current_time)
        
        # Consumer: read power value
        power_received = h.helicsInputGetDouble(sub_power)
        
        logger.info(f"Time {current_time:.1f}s: Generator={power_generated:.2f} kW, "
                   f"Consumer received={power_received:.2f} kW")
    
    logger.info("-" * 70)
    logger.info("Simulation complete. Finalizing...")
    
    # Clean up
    h.helicsFederateFinalize(generator)
    h.helicsFederateFinalize(consumer)
    h.helicsFederateFree(generator)
    h.helicsFederateFree(consumer)
    h.helicsCloseLibrary()
    
    logger.info("✓ Energy example completed successfully!\n")
    time.sleep(0.5)  # Give time for cleanup


# ============================================================================
# EXAMPLE 2: SIMPLE MOBILITY SYSTEM
# ============================================================================

def example_mobility_simple():
    """
    Most basic mobility example: One vehicle moving along a straight path,
    one traffic monitor observing its position.
    
    This demonstrates:
    - Vector/array data exchange
    - Position updates over time
    - Multiple value publications
    """
    logger.info("=" * 70)
    logger.info("EXAMPLE 2: Simple Mobility System (Vehicle -> Monitor)")
    logger.info("=" * 70)
    
    # Create broker
    broker = h.helicsCreateBroker("zmq", "broker", "--federates=2")
    time.sleep(0.5)  # Give broker time to start
    
    # Create vehicle federate (moves along a path)
    fed_info_veh = h.helicsCreateFederateInfo()
    h.helicsFederateInfoSetCoreTypeFromString(fed_info_veh, "zmq")
    h.helicsFederateInfoSetCoreInitString(fed_info_veh, "--federates=1")
    h.helicsFederateInfoSetTimeProperty(fed_info_veh, h.helics_property_time_delta, 1.0)
    vehicle = h.helicsCreateValueFederate("Vehicle", fed_info_veh)
    
    # Create monitor federate (tracks vehicle)
    fed_info_mon = h.helicsCreateFederateInfo()
    h.helicsFederateInfoSetCoreTypeFromString(fed_info_mon, "zmq")
    h.helicsFederateInfoSetCoreInitString(fed_info_mon, "--federates=1")
    h.helicsFederateInfoSetTimeProperty(fed_info_mon, h.helics_property_time_delta, 1.0)
    monitor = h.helicsCreateValueFederate("Monitor", fed_info_mon)
    
    # Vehicle publishes position (x, y) and speed
    pub_x = h.helicsFederateRegisterGlobalPublication(
        vehicle, "vehicle/position_x", h.helics_data_type_double, "m"
    )
    pub_y = h.helicsFederateRegisterGlobalPublication(
        vehicle, "vehicle/position_y", h.helics_data_type_double, "m"
    )
    pub_speed = h.helicsFederateRegisterGlobalPublication(
        vehicle, "vehicle/speed", h.helics_data_type_double, "m/s"
    )
    
    # Monitor subscribes to vehicle data
    sub_x = h.helicsFederateRegisterSubscription(monitor, "vehicle/position_x", "")
    sub_y = h.helicsFederateRegisterSubscription(monitor, "vehicle/position_y", "")
    sub_speed = h.helicsFederateRegisterSubscription(monitor, "vehicle/speed", "")
    
    logger.info("Entering initialization mode...")
    # Enter initialization mode asynchronously to avoid blocking
    h.helicsFederateEnterInitializingModeAsync(vehicle)
    h.helicsFederateEnterInitializingModeAsync(monitor)
    h.helicsFederateEnterInitializingModeComplete(vehicle)
    h.helicsFederateEnterInitializingModeComplete(monitor)
    
    logger.info("Entering execution mode...")
    h.helicsFederateEnterExecutingModeAsync(vehicle)
    h.helicsFederateEnterExecutingModeAsync(monitor)
    h.helicsFederateEnterExecutingModeComplete(vehicle)
    h.helicsFederateEnterExecutingModeComplete(monitor)
    
    # Simulation parameters
    total_time = 10.0  # seconds
    time_step = 1.0
    
    # Vehicle initial state
    pos_x = 0.0  # meters
    pos_y = 0.0
    speed = 10.0  # m/s (constant speed, moving in +x direction)
    
    logger.info(f"\nStarting simulation for {total_time} seconds...")
    logger.info("Vehicle moving at constant speed along X-axis")
    logger.info("-" * 70)
    
    # Simulation loop
    current_time = 0.0
    while current_time < total_time:
        # Vehicle: update position and publish
        pos_x += speed * time_step
        h.helicsPublicationPublishDouble(pub_x, pos_x)
        h.helicsPublicationPublishDouble(pub_y, pos_y)
        h.helicsPublicationPublishDouble(pub_speed, speed)
        
        # Request time advancement
        current_time = h.helicsFederateRequestTime(vehicle, current_time + time_step)
        monitor_time = h.helicsFederateRequestTime(monitor, current_time)
        
        # Monitor: read vehicle data
        received_x = h.helicsInputGetDouble(sub_x)
        received_y = h.helicsInputGetDouble(sub_y)
        received_speed = h.helicsInputGetDouble(sub_speed)
        
        logger.info(f"Time {current_time:.1f}s: Vehicle Position=({received_x:.1f}, {received_y:.1f}) m, "
                   f"Speed={received_speed:.1f} m/s")
    
    logger.info("-" * 70)
    logger.info("Simulation complete. Finalizing...")
    
    # Clean up
    h.helicsFederateFinalize(vehicle)
    h.helicsFederateFinalize(monitor)
    h.helicsFederateFree(vehicle)
    h.helicsFederateFree(monitor)
    h.helicsCloseLibrary()
    
    logger.info("✓ Mobility example completed successfully!\n")
    time.sleep(0.5)  # Give time for cleanup


# ============================================================================
# MAIN: RUN EXAMPLES
# ============================================================================

def main():
    """Run all basic examples"""
    print("\n" + "=" * 70)
    print("HELICS BASIC EXAMPLES - Verification Tests")
    print("=" * 70)
    print("\nThese examples demonstrate the most basic HELICS functionality:")
    print("1. Energy: Simple generator-consumer power exchange")
    print("2. Mobility: Simple vehicle position tracking")
    print("\nIf these run successfully, HELICS is properly installed!")
    print("=" * 70 + "\n")
    
    try:
        # Run energy example
        example_energy_simple()
        
        # Run mobility example
        example_mobility_simple()
        
        # Summary
        print("\n" + "=" * 70)
        print("✓ ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nHELICS is working correctly. You can now:")
        print("- Run the full scenarios (E1, E2, M1) via main.py")
        print("- Build your own co-simulation models")
        print("=" * 70 + "\n")
        
    except Exception as e:
        logger.error(f"\n✗ Error running examples: {e}")
        logger.error("Please check your HELICS installation.")
        raise


if __name__ == "__main__":
    main()
