"""
Scenario T1: 5G Slice Resource Allocation

3 gNBs serving 200 mobile users across three network slices (eMBB, URLLC, mMTC).
Two slicing strategies are compared:
  - Static: fixed RB fractions per slice
  - Dynamic: demand-proportional allocation with guaranteed floor
"""

import helics as h
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SlicingStrategy(Enum):
    """Resource allocation strategies"""
    STATIC = "static"
    DYNAMIC = "dynamic"


class SliceType(Enum):
    """Network slice types"""
    EMBB = "eMBB"
    URLLC = "URLLC"
    MMTC = "mMTC"


# Slice configuration: (fraction for static, RBs required per user for QoS)
SLICE_CONFIG = {
    SliceType.EMBB:  {"static_fraction": 0.50, "rb_requirement": 2},
    SliceType.URLLC: {"static_fraction": 0.30, "rb_requirement": 2},
    SliceType.MMTC:  {"static_fraction": 0.20, "rb_requirement": 1},
}


class GNodeB:
    """5G base station (gNB) with resource block pool"""

    def __init__(self, gnb_id: int, position: Tuple[float, float], total_rbs: int = 100):
        self.id = gnb_id
        self.position = position
        self.total_rbs = total_rbs
        self.tx_power_dbm = 46.0  # Typical macro gNB transmit power

    def path_loss(self, user_position: Tuple[float, float]) -> float:
        """3GPP Urban Macro path loss model (dB)"""
        dx = user_position[0] - self.position[0]
        dy = user_position[1] - self.position[1]
        dist_m = max(10.0, np.sqrt(dx**2 + dy**2))  # minimum 10 m
        dist_km = dist_m / 1000.0
        return 128.1 + 37.6 * np.log10(dist_km)

    def received_power(self, user_position: Tuple[float, float], shadow_fading_db: float = 0.0) -> float:
        """Received power at user position (dBm)"""
        return self.tx_power_dbm - self.path_loss(user_position) + shadow_fading_db


class MobileUser:
    """Mobile user with slice affiliation and random waypoint mobility"""

    def __init__(self, user_id: int, slice_type: SliceType, area_size: float = 2000.0):
        self.id = user_id
        self.slice_type = slice_type
        self.area_size = area_size

        # Position and mobility
        self.x = np.random.uniform(0, area_size)
        self.y = np.random.uniform(0, area_size)
        self.speed = np.random.uniform(0.5, 2.0)  # m/s (pedestrian)
        self.waypoint_x = np.random.uniform(0, area_size)
        self.waypoint_y = np.random.uniform(0, area_size)

        # Serving cell
        self.serving_gnb: Optional[int] = None
        self.handover_cooldown = 0  # steps remaining before next handover allowed

        # Per-step state
        self.qos_satisfied = False
        self.rb_allocated = 0
        self.active = True  # mMTC may toggle
        self.handover_failed = False

    def move(self, dt: float):
        """Move toward waypoint using random waypoint model"""
        dx = self.waypoint_x - self.x
        dy = self.waypoint_y - self.y
        dist = np.sqrt(dx**2 + dy**2)

        if dist < 5.0:
            # Reached waypoint, pick a new one
            self.waypoint_x = np.random.uniform(0, self.area_size)
            self.waypoint_y = np.random.uniform(0, self.area_size)
            return

        # Normalize and step
        step = self.speed * dt
        self.x += (dx / dist) * step
        self.y += (dy / dist) * step

        # Clamp to area
        self.x = np.clip(self.x, 0, self.area_size)
        self.y = np.clip(self.y, 0, self.area_size)


class SliceResourceAllocator:
    """Allocates RBs to slices within a single gNB"""

    def __init__(self, total_rbs: int, strategy: SlicingStrategy):
        self.total_rbs = total_rbs
        self.strategy = strategy
        self.min_rbs = 5  # guaranteed floor per slice

    def allocate(self, users_per_slice: Dict[SliceType, int]) -> Dict[SliceType, int]:
        """Return RB allocation per slice for this step"""
        if self.strategy == SlicingStrategy.STATIC:
            return self._static_allocate()
        else:
            return self._dynamic_allocate(users_per_slice)

    def _static_allocate(self) -> Dict[SliceType, int]:
        allocation = {}
        for s, cfg in SLICE_CONFIG.items():
            allocation[s] = int(self.total_rbs * cfg["static_fraction"])
        return allocation

    def _dynamic_allocate(self, users_per_slice: Dict[SliceType, int]) -> Dict[SliceType, int]:
        # Compute demand
        demands = {}
        total_demand = 0
        for s, cfg in SLICE_CONFIG.items():
            d = users_per_slice.get(s, 0) * cfg["rb_requirement"]
            demands[s] = d
            total_demand += d

        allocation = {}
        if total_demand == 0:
            for s in SLICE_CONFIG:
                allocation[s] = self.min_rbs
            return allocation

        for s in SLICE_CONFIG:
            proportional = int((demands[s] / total_demand) * self.total_rbs)
            allocation[s] = max(self.min_rbs, proportional)

        # Cap total to available RBs
        while sum(allocation.values()) > self.total_rbs:
            # Reduce largest allocation by 1
            largest = max(allocation, key=lambda k: allocation[k])
            allocation[largest] -= 1

        return allocation


class NetworkSlicingSimulation:
    """Main 5G slice resource allocation simulation with HELICS support"""

    def __init__(self, name: str = "SliceSim", use_helics: bool = False,
                 strategy: SlicingStrategy = SlicingStrategy.DYNAMIC):
        self.name = name
        self.federate = None
        self.use_helics = use_helics
        self.strategy = strategy

        # Network elements
        self.gnbs: List[GNodeB] = []
        self.users: List[MobileUser] = []

        # Simulation parameters
        self.time_step = 0.1  # 100 ms
        self.sim_duration = 3600.0  # 1 hour
        self.area_size = 2000.0  # 2 km × 2 km
        self.total_rbs = 100
        self.handover_hysteresis_db = 3.0
        self.handover_success_prob = 0.95
        self.shadow_std_db = 4.0

        # mMTC burst parameters
        self.burst_period = 900.0  # 15 minutes

        # Allocators (one per gNB)
        self.allocators: List[SliceResourceAllocator] = []

        # Metrics accumulators
        self.qos_counts = {s: {"satisfied": 0, "total": 0} for s in SliceType}
        self.rb_allocated_total = {s: 0 for s in SliceType}
        self.rb_used_total = {s: 0 for s in SliceType}
        self.total_rbs_available = 0
        self.total_rbs_used = 0
        self.handover_attempts = 0
        self.handover_successes = 0
        self.handover_failures = 0

        # Time-series for logging
        self.qos_history = {s: [] for s in SliceType}
        self.utilization_history = []
        self.waste_history = []

    def initialize_components(self):
        """Create gNBs and users"""
        logger.info("Initializing network components...")

        # 3 gNBs in triangular layout
        gnb_positions = [
            (500.0, 500.0),
            (1500.0, 500.0),
            (1000.0, 1500.0),
        ]
        for i, pos in enumerate(gnb_positions):
            self.gnbs.append(GNodeB(i, pos, self.total_rbs))
            self.allocators.append(SliceResourceAllocator(self.total_rbs, self.strategy))

        # 200 users: 100 eMBB, 40 URLLC, 60 mMTC
        user_id = 0
        for _ in range(100):
            self.users.append(MobileUser(user_id, SliceType.EMBB, self.area_size))
            user_id += 1
        for _ in range(40):
            self.users.append(MobileUser(user_id, SliceType.URLLC, self.area_size))
            user_id += 1
        for _ in range(60):
            self.users.append(MobileUser(user_id, SliceType.MMTC, self.area_size))
            user_id += 1

        # Initial serving cell assignment
        for user in self.users:
            self._assign_serving_gnb(user)

        logger.info(f"Created {len(self.gnbs)} gNBs and {len(self.users)} users "
                    f"(100 eMBB, 40 URLLC, 60 mMTC)")

    def setup_federate(self):
        """Setup HELICS federate (optional for standalone simulation)"""
        if not self.use_helics:
            logger.info("Running in standalone mode (HELICS disabled)")
            return

        logger.info("Setting up HELICS federate...")
        try:
            fedinfo = h.helicsCreateFederateInfo()
            h.helicsFederateInfoSetCoreName(fedinfo, self.name)
            h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
            h.helicsFederateInfoSetCoreInitString(fedinfo, "--federates=1 --autobroker")
            h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, self.time_step)

            self.federate = h.helicsCreateValueFederate(self.name, fedinfo)
            logger.info(f"Federate '{self.name}' created")

            # Register publications
            self.pub_urllc_qos = h.helicsFederateRegisterGlobalPublication(
                self.federate, "urllc_qos_status", h.helics_data_type_double, ""
            )
            self.pub_network_load = h.helicsFederateRegisterGlobalPublication(
                self.federate, "total_network_load", h.helics_data_type_double, "W"
            )

            h.helicsFederateEnterExecutingMode(self.federate)
            logger.info("Federate entering execution mode")
        except Exception as e:
            logger.warning(f"HELICS setup failed: {e}. Running in standalone mode.")
            self.federate = None
            self.use_helics = False

    def _assign_serving_gnb(self, user: MobileUser):
        """Assign user to strongest gNB"""
        best_gnb = None
        best_power = -999.0
        for gnb in self.gnbs:
            fading = np.random.normal(0, self.shadow_std_db)
            p_rx = gnb.received_power((user.x, user.y), fading)
            if p_rx > best_power:
                best_power = p_rx
                best_gnb = gnb.id
        user.serving_gnb = best_gnb

    def _check_handover(self, user: MobileUser):
        """Check and execute handover if needed"""
        if user.handover_cooldown > 0:
            user.handover_cooldown -= 1
            user.handover_failed = False
            return

        serving_power = self.gnbs[user.serving_gnb].received_power(
            (user.x, user.y), np.random.normal(0, self.shadow_std_db)
        )

        best_gnb = user.serving_gnb
        best_power = serving_power

        for gnb in self.gnbs:
            if gnb.id == user.serving_gnb:
                continue
            fading = np.random.normal(0, self.shadow_std_db)
            p_rx = gnb.received_power((user.x, user.y), fading)
            if p_rx > best_power:
                best_power = p_rx
                best_gnb = gnb.id

        if best_gnb != user.serving_gnb and (best_power - serving_power) > self.handover_hysteresis_db:
            self.handover_attempts += 1
            if np.random.random() < self.handover_success_prob:
                user.serving_gnb = best_gnb
                self.handover_successes += 1
                user.handover_failed = False
                user.handover_cooldown = 10  # 1 second cooldown (10 × 100ms)
            else:
                self.handover_failures += 1
                user.handover_failed = True
                user.handover_cooldown = 10  # cooldown even on failure
        else:
            user.handover_failed = False

    def _mmtc_activity(self, current_time: float) -> float:
        """mMTC activity probability at time t"""
        return 0.3 + 0.5 * abs(np.sin(2 * np.pi * current_time / self.burst_period))

    def run_simulation(self):
        """Run the 1-hour simulation"""
        logger.info(f"Starting 1-hour simulation with {self.strategy.value} slicing "
                    f"at 100 ms resolution")

        self.initialize_components()

        current_time = 0.0
        step = 0
        log_interval = int(300.0 / self.time_step)  # every 5 minutes

        while current_time < self.sim_duration:
            # 1. User mobility
            for user in self.users:
                user.move(self.time_step)

            # 2. Handover checks
            for user in self.users:
                self._check_handover(user)

            # 3. Determine mMTC activity
            activity_prob = self._mmtc_activity(current_time)
            for user in self.users:
                if user.slice_type == SliceType.MMTC:
                    user.active = np.random.random() < activity_prob
                else:
                    user.active = True

            # 4. Resource allocation per gNB
            step_qos = {s: {"satisfied": 0, "total": 0} for s in SliceType}
            step_rbs_used = 0

            for gnb_idx, gnb in enumerate(self.gnbs):
                # Count active users per slice at this gNB
                users_at_gnb = {s: [] for s in SliceType}
                for user in self.users:
                    if user.serving_gnb == gnb.id and user.active:
                        users_at_gnb[user.slice_type].append(user)

                users_per_slice = {s: len(ul) for s, ul in users_at_gnb.items()}

                # Allocate RBs
                allocation = self.allocators[gnb_idx].allocate(users_per_slice)

                # 5. QoS evaluation
                for s in SliceType:
                    slice_users = users_at_gnb[s]
                    n_users = len(slice_users)
                    rb_for_slice = allocation[s]
                    rb_req = SLICE_CONFIG[s]["rb_requirement"]

                    if n_users > 0:
                        rb_per_user = rb_for_slice // n_users
                        rbs_actually_used = min(rb_for_slice, n_users * min(rb_per_user, rb_req))
                    else:
                        rb_per_user = 0
                        rbs_actually_used = 0

                    for user in slice_users:
                        if user.handover_failed:
                            user.qos_satisfied = False
                            user.rb_allocated = 0
                        else:
                            user.rb_allocated = rb_per_user
                            user.qos_satisfied = rb_per_user >= rb_req

                        step_qos[s]["total"] += 1
                        if user.qos_satisfied:
                            step_qos[s]["satisfied"] += 1

                    # Track utilization
                    self.rb_allocated_total[s] += rb_for_slice
                    self.rb_used_total[s] += rbs_actually_used
                    step_rbs_used += rbs_actually_used

            # Accumulate total RBs and usage outside the gNB loop
            self.total_rbs_available += len(self.gnbs) * self.total_rbs
            self.total_rbs_used += step_rbs_used

            # Accumulate into global counters
            for s in SliceType:
                self.qos_counts[s]["satisfied"] += step_qos[s]["satisfied"]
                self.qos_counts[s]["total"] += step_qos[s]["total"]

            # Time-series snapshots (sample every log_interval steps)
            if step % log_interval == 0:
                for s in SliceType:
                    t = step_qos[s]["total"]
                    sat = step_qos[s]["satisfied"] / t * 100 if t > 0 else 100.0
                    self.qos_history[s].append(sat)

                gnb_rbs = len(self.gnbs) * self.total_rbs
                self.utilization_history.append(step_rbs_used / gnb_rbs * 100 if gnb_rbs > 0 else 0)
                self.waste_history.append((gnb_rbs - step_rbs_used) / gnb_rbs * 100 if gnb_rbs > 0 else 0)

            # HELICS publish
            if self.use_helics and self.federate:
                urllc_total = step_qos[SliceType.URLLC]["total"]
                urllc_sat = (step_qos[SliceType.URLLC]["satisfied"] / urllc_total
                             if urllc_total > 0 else 1.0)
                h.helicsPublicationPublishDouble(self.pub_urllc_qos, urllc_sat)
                h.helicsPublicationPublishDouble(self.pub_network_load, float(step_rbs_used))
                current_time = h.helicsFederateRequestTime(self.federate, current_time + self.time_step)
            else:
                current_time += self.time_step

            step += 1
            if step % log_interval == 0:
                elapsed_min = current_time / 60.0
                logger.info(
                    f"Step {step}: t={elapsed_min:.1f} min | "
                    f"eMBB QoS={step_qos[SliceType.EMBB]['satisfied']}/{step_qos[SliceType.EMBB]['total']} | "
                    f"URLLC QoS={step_qos[SliceType.URLLC]['satisfied']}/{step_qos[SliceType.URLLC]['total']} | "
                    f"mMTC QoS={step_qos[SliceType.MMTC]['satisfied']}/{step_qos[SliceType.MMTC]['total']}"
                )

        logger.info("Simulation completed")

    def generate_report(self) -> Dict:
        """Generate simulation report with all metrics"""
        # Per-slice QoS rates
        qos_rates = {}
        for s in SliceType:
            total = self.qos_counts[s]["total"]
            sat = self.qos_counts[s]["satisfied"]
            qos_rates[s.value] = float(sat / total * 100) if total > 0 else 0.0

        # Slice utilization
        slice_utilization = {}
        for s in SliceType:
            alloc = self.rb_allocated_total[s]
            used = self.rb_used_total[s]
            slice_utilization[s.value] = float(used / alloc * 100) if alloc > 0 else 0.0

        # Overall waste
        total_waste_pct = float(
            (self.total_rbs_available - self.total_rbs_used) / self.total_rbs_available * 100
        ) if self.total_rbs_available > 0 else 0.0

        overall_utilization_pct = float(
            self.total_rbs_used / self.total_rbs_available * 100
        ) if self.total_rbs_available > 0 else 0.0

        ho_success_rate = float(
            self.handover_successes / self.handover_attempts * 100
        ) if self.handover_attempts > 0 else 100.0

        report = {
            "scenario": "T1 - 5G Slice Resource Allocation",
            "simulation_duration_hours": 1,
            "time_step_ms": 100,
            "slicing_strategy": self.strategy.value,
            "components": {
                "num_gnbs": len(self.gnbs),
                "total_users": len(self.users),
                "embb_users": sum(1 for u in self.users if u.slice_type == SliceType.EMBB),
                "urllc_users": sum(1 for u in self.users if u.slice_type == SliceType.URLLC),
                "mmtc_users": sum(1 for u in self.users if u.slice_type == SliceType.MMTC),
                "rbs_per_gnb": self.total_rbs,
            },
            "metrics": {
                "qos_satisfaction_embb_pct": qos_rates[SliceType.EMBB.value],
                "qos_satisfaction_urllc_pct": qos_rates[SliceType.URLLC.value],
                "qos_satisfaction_mmtc_pct": qos_rates[SliceType.MMTC.value],
                "slice_utilization_embb_pct": slice_utilization[SliceType.EMBB.value],
                "slice_utilization_urllc_pct": slice_utilization[SliceType.URLLC.value],
                "slice_utilization_mmtc_pct": slice_utilization[SliceType.MMTC.value],
                "overall_utilization_pct": overall_utilization_pct,
                "resource_waste_pct": total_waste_pct,
                "handover_attempts": self.handover_attempts,
                "handover_success_rate_pct": ho_success_rate,
                "handover_failures": self.handover_failures,
            },
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


def run_scenario_t1(use_helics: bool = False,
                    strategy: SlicingStrategy = SlicingStrategy.DYNAMIC):
    """Run Scenario T1

    Args:
        use_helics: If True, use HELICS for co-simulation
        strategy: SlicingStrategy.STATIC or SlicingStrategy.DYNAMIC
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("=" * 70)
    logger.info("Scenario T1: 5G Slice Resource Allocation")
    logger.info("=" * 70)

    sim = NetworkSlicingSimulation(
        "SliceSim_T1", use_helics=use_helics, strategy=strategy
    )
    sim.setup_federate()
    sim.run_simulation()

    report = sim.generate_report()

    # Print report
    logger.info("\n" + "=" * 70)
    logger.info("SIMULATION REPORT")
    logger.info("=" * 70)
    logger.info(f"Scenario: {report['scenario']}")
    logger.info(f"Slicing Strategy: {report['slicing_strategy'].upper()}")
    logger.info(f"\nComponents:")
    for key, value in report['components'].items():
        logger.info(f"  {key}: {value}")
    logger.info(f"\nMetrics:")
    for key, value in report['metrics'].items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.2f}")
        else:
            logger.info(f"  {key}: {value}")
    logger.info("=" * 70)

    sim.cleanup()
    return report


def compare_slicing_strategies(use_helics: bool = False):
    """Compare static vs dynamic slicing strategies"""
    logger.info("=" * 70)
    logger.info("COMPARING SLICING STRATEGIES")
    logger.info("=" * 70)

    results = {}

    for strat in [SlicingStrategy.STATIC, SlicingStrategy.DYNAMIC]:
        np.random.seed(42)
        logger.info(f"\nRunning {strat.value} slicing...")
        report = run_scenario_t1(use_helics, strat)
        results[strat.value] = report

    # Print comparison
    logger.info("\n" + "=" * 70)
    logger.info("STRATEGY COMPARISON")
    logger.info("=" * 70)

    for strategy_name, report in results.items():
        m = report['metrics']
        logger.info(f"\n{strategy_name.upper()}:")
        logger.info(f"  eMBB QoS Satisfaction: {m['qos_satisfaction_embb_pct']:.1f}%")
        logger.info(f"  URLLC QoS Satisfaction: {m['qos_satisfaction_urllc_pct']:.1f}%")
        logger.info(f"  mMTC QoS Satisfaction: {m['qos_satisfaction_mmtc_pct']:.1f}%")
        logger.info(f"  Overall Utilization: {m['overall_utilization_pct']:.1f}%")
        logger.info(f"  Resource Waste: {m['resource_waste_pct']:.1f}%")
        logger.info(f"  Handover Success Rate: {m['handover_success_rate_pct']:.1f}%")
        logger.info(f"  Handover Failures: {m['handover_failures']}")

    return results
