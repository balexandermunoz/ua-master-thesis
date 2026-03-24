"""
Co-Simulation Framework for Cross-Domain Interactions
Testing energy systems, mobility networks, and telecommunications domains
"""

import helics as h
import logging
from scenarios.scenario_e1 import run_scenario_e1
from scenarios.scenario_e2 import run_scenario_e2, compare_strategies, ChargingStrategy
from scenarios.scenario_m1 import run_scenario_m1, compare_signal_strategies


def main():
    """
    Main entry point for the co-simulation framework.
    Runs six distinct scenarios to validate cross-domain interactions.
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    logger.info("Co-Simulation Framework Initialized")
    logger.info("=" * 70)
    logger.info("Available Scenarios:")
    logger.info("E1. Smart Grid with Renewable Integration")
    logger.info("E2. Electric Vehicle Charging Infrastructure")
    logger.info("M1. Urban Traffic Congestion Management")
    logger.info("E3. [Not yet implemented]")
    logger.info("E4. [Not yet implemented]")
    logger.info("E5. [Not yet implemented]")
    logger.info("=" * 70)
    
    # Select scenario to run
    scenario = input("\nSelect scenario (E1/E2/M1) or 'compare' (E2/M1): ").strip().upper()
    
    if scenario == "E1" or scenario == "1":
        logger.info("\nRunning Scenario E1...")
        report = run_scenario_e1()
    elif scenario == "E2" or scenario == "2":
        logger.info("\nRunning Scenario E2...")
        strategy = input("Select strategy (uncoordinated/smart/v2g) [smart]: ").strip().lower()
        if strategy == "uncoordinated":
            report = run_scenario_e2(strategy=ChargingStrategy.UNCOORDINATED)
        elif strategy == "v2g":
            report = run_scenario_e2(strategy=ChargingStrategy.V2G)
        else:
            report = run_scenario_e2(strategy=ChargingStrategy.SMART)
    elif scenario == "M1" or scenario == "3":
        logger.info("\nRunning Scenario M1...")
        adaptive = input("Use adaptive signals? (y/n) [y]: ").strip().lower()
        use_adaptive = adaptive != "n"
        report = run_scenario_m1(adaptive_signals=use_adaptive)
    elif scenario == "COMPARE":
        compare_type = input("Compare E2 or M1? [E2]: ").strip().upper()
        if compare_type == "M1":
            logger.info("\nComparing M1 signal control strategies...")
            results = compare_signal_strategies()
        else:
            logger.info("\nComparing E2 charging strategies...")
            results = compare_strategies()
    else:
        logger.error("Invalid selection!")
        return
    
    logger.info("\nSimulation completed!")


if __name__ == "__main__":
    main()
