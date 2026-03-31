"""
Base simulation federate and shared utilities.

Provides the domain-independent infrastructure described in Chapter 3:
- Agent lifecycle (initialize, step, report)
- HELICS federate setup / teardown
- Time advancement (standalone or co-simulation)
- Report printing
"""

import helics as h
import logging
from abc import ABC, abstractmethod
from typing import Dict

logger = logging.getLogger(__name__)


class BaseFederate(ABC):
    """Abstract base for all domain federates.

    Encapsulates the HELICS wiring and time-stepping logic so that
    domain modules only implement domain-specific behaviour.

    Subclasses must implement:
        initialize_components()
        run_simulation()
        generate_report() -> Dict
    """

    def __init__(self, name: str, use_helics: bool = False,
                 time_step: float = 1.0, sim_duration: float = 3600.0):
        self.name = name
        self.federate = None
        self.use_helics = use_helics
        self.time_step = time_step
        self.sim_duration = sim_duration

    # ------------------------------------------------------------------
    # HELICS lifecycle
    # ------------------------------------------------------------------

    def setup_federate(self):
        """Setup HELICS federate (optional for standalone simulation)."""
        if not self.use_helics:
            logger.info("Running in standalone mode (HELICS disabled)")
            return

        logger.info("Setting up HELICS federate...")
        try:
            fedinfo = h.helicsCreateFederateInfo()
            h.helicsFederateInfoSetCoreName(fedinfo, self.name)
            h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
            h.helicsFederateInfoSetCoreInitString(
                fedinfo, "--federates=1 --autobroker"
            )
            h.helicsFederateInfoSetTimeProperty(
                fedinfo, h.helics_property_time_delta, self.time_step
            )

            self.federate = h.helicsCreateValueFederate(self.name, fedinfo)
            logger.info(f"Federate '{self.name}' created")

            self._register_publications()

            h.helicsFederateEnterExecutingMode(self.federate)
            logger.info("Federate entering execution mode")
        except Exception as e:
            logger.warning(
                f"HELICS setup failed: {e}. Running in standalone mode."
            )
            self.federate = None
            self.use_helics = False

    def _register_publications(self):
        """Override to register domain-specific HELICS publications."""
        pass

    def advance_time(self, current_time: float) -> float:
        """Advance simulation clock by one time step."""
        if self.use_helics and self.federate:
            return h.helicsFederateRequestTime(
                self.federate, current_time + self.time_step
            )
        return current_time + self.time_step

    def cleanup(self):
        """Cleanup HELICS federate."""
        if self.use_helics and self.federate:
            try:
                h.helicsFederateFinalize(self.federate)
                h.helicsFederateFree(self.federate)
                h.helicsCloseLibrary()
                logger.info("Federate cleaned up")
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

    # ------------------------------------------------------------------
    # Contract methods (Chapter 3 engine interface)
    # ------------------------------------------------------------------

    @abstractmethod
    def initialize_components(self):
        """Create domain-specific agents and models."""
        ...

    @abstractmethod
    def run_simulation(self):
        """Execute the main simulation loop."""
        ...

    @abstractmethod
    def generate_report(self) -> Dict:
        """Return a report dict with 'scenario', 'components', and 'metrics' keys."""
        ...


# ------------------------------------------------------------------
# Shared utilities
# ------------------------------------------------------------------

def print_report(report: Dict, log: logging.Logger,
                 extra_headers: Dict[str, str] | None = None):
    """Print a simulation report in the standard format.

    Args:
        report: Dict returned by generate_report().
        log: Logger instance to use.
        extra_headers: Optional mapping of {label: report_key} printed
                       after the scenario name (e.g. {"Strategy": "charging_strategy"}).
    """
    log.info("\n" + "=" * 70)
    log.info("SIMULATION REPORT")
    log.info("=" * 70)
    log.info(f"Scenario: {report['scenario']}")

    if extra_headers:
        for label, key in extra_headers.items():
            log.info(f"{label}: {report[key].upper()}")

    log.info("\nComponents:")
    for key, value in report["components"].items():
        log.info(f"  {key}: {value}")

    log.info("\nMetrics:")
    for key, value in report["metrics"].items():
        if isinstance(value, float):
            log.info(f"  {key}: {value:.2f}")
        else:
            log.info(f"  {key}: {value}")
    log.info("=" * 70)
