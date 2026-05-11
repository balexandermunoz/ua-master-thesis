"""
Cross-Domain Scenario M1+T1: Mobility–Telecommunications Integration

200 vehicles carrying connected user equipment (UE) navigate the M1 traffic
network.  Their positions are fed to the 5G radio model (T1), updating
the serving gNB and resource-block allocation.  Poor URLLC QoS at a gNB
disables adaptive signal control at nearby intersections, causing queue
build-up that in turn increases network congestion.

Comparison modes:
  - coupled   : vehicle positions drive UE locations; URLLC QoS degrades
                adaptive traffic signals in congested radio cells
  - uncoupled : telecom users move via random waypoint; no QoS feedback
                to traffic signal control (baseline)
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Set

from engine.base import BaseFederate, print_report
from scenarios.scenario_m1 import (
    TrafficNetwork, Vehicle as M1Vehicle,
    create_random_vehicles, update_signals, move_vehicles_step,
    collect_queue_lengths,
)
from scenarios.scenario_t1 import (
    GNodeB, MobileUser, SliceType, SlicingStrategy,
    SLICE_CONFIG, SliceResourceAllocator,
    assign_serving_gnb, check_handover, mmtc_activity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

#: gNB positions scaled to the M1 5×5 × 1250 m grid (5000 m × 5000 m area)
GNB_POSITIONS_5K: List[Tuple[float, float]] = [
    (1250.0, 1250.0),
    (3750.0, 1250.0),
    (2500.0, 3750.0),
]

AREA_SIZE: float = 5000.0          # metres — matches M1 grid extent
_COVERAGE_RADIUS_M: float = 1600.0 # degradation influence radius per gNB


# ---------------------------------------------------------------------------
#  Connected vehicle: M1 traffic agent that also hosts a 5G UE
# ---------------------------------------------------------------------------

class ConnectedVehicle(M1Vehicle):
    """A traffic vehicle that simultaneously hosts a mobile UE.

    Grid coordinates (integer col, row) are projected to the radio
    coordinate space with::

        x_m = col × spacing_m
        y_m = row × spacing_m

    Call :meth:`sync_position` after each M1 movement step to keep the
    UE position consistent with the vehicle's grid location.
    """

    def __init__(self, vehicle_id: int,
                 origin: Tuple[int, int],
                 destination: Tuple[int, int],
                 user: MobileUser,
                 spacing_m: float = 1250.0):
        super().__init__(vehicle_id, origin, destination)
        self.user = user
        self._spacing_m = spacing_m

    def sync_position(self) -> None:
        """Project current grid position onto the radio coordinate space."""
        col, row = self.current_position
        self.user.x = col * self._spacing_m
        self.user.y = row * self._spacing_m


# ---------------------------------------------------------------------------
#  Cross-domain simulation
# ---------------------------------------------------------------------------

class CrossDomainM1T1(BaseFederate):
    """Coupled Mobility–Telecommunications simulation on a shared 5×5 grid.

    The M1 traffic network provides vehicle positions that are mapped to 5G
    UE coordinates.  In coupled mode, poor URLLC QoS at a gNB disables
    adaptive signal control at nearby intersections, increasing congestion
    and emissions — a causal chain only visible through joint simulation.
    """

    def __init__(self,
                 name: str = "CrossM1T1",
                 use_helics: bool = False,
                 coupled: bool = True,
                 num_connected: int = 200,
                 num_background: int = 2300,
                 grid_size: int = 5,
                 sim_duration_hours: int = 3,
                 slicing_strategy: SlicingStrategy = SlicingStrategy.DYNAMIC,
                 urllc_qos_threshold: float = 0.80):
        super().__init__(name, use_helics,
                         time_step=1.0,
                         sim_duration=sim_duration_hours * 3600)
        self.coupled = coupled
        self.num_connected = num_connected
        self.num_background = num_background
        self.grid_size = grid_size
        self.slicing_strategy = slicing_strategy
        self.urllc_qos_threshold = urllc_qos_threshold

        # Shared traffic network
        self.network = TrafficNetwork(grid_size=grid_size, spacing_m=1250.0)

        # Vehicle agents
        self.connected_vehicles: List[ConnectedVehicle] = []
        self.background_vehicles: List[M1Vehicle] = []
        self.all_vehicles: List[M1Vehicle] = []
        self.completed_vehicles: List[M1Vehicle] = []

        # Telecom components
        self.gnbs: List[GNodeB] = []
        self.users: List[MobileUser] = []
        self.allocators: List[SliceResourceAllocator] = []

        # Telecom simulation parameters
        self.handover_hysteresis_db: float = 3.0
        self.handover_success_prob: float = 0.95
        self.shadow_std_db: float = 4.0
        self.burst_period: float = 900.0   # 15 min for mMTC burst cycle
        self.total_rbs_per_gnb: int = 100

        # Telecom metrics accumulators
        self.qos_counts = {s: {"satisfied": 0, "total": 0} for s in SliceType}
        self.rb_allocated_total = {s: 0 for s in SliceType}
        self.rb_used_total = {s: 0 for s in SliceType}
        self.total_rbs_available: int = 0
        self.total_rbs_used: int = 0
        self.handover_attempts: int = 0
        self.handover_successes: int = 0
        self.handover_failures: int = 0

        # Coupling / degradation state
        self.degraded_intersections: Set[Tuple[int, int]] = set()
        self.degradation_event_count: int = 0   # per-gNB below-threshold occurrences
        self.total_degradation_steps: int = 0   # sum over time of |degraded_intersections|
        self.affected_intersection_set: Set[Tuple[int, int]] = set()

        # Load-imbalance tracking (std dev of users-per-gNB sampled each step)
        self._load_std_history: List[float] = []

        # Traffic metrics
        self.queue_lengths: Dict[Tuple[int, int], List[int]] = {
            pos: [] for pos in self.network.intersections
        }

    # ------------------------------------------------------------------
    #  Initialisation
    # ------------------------------------------------------------------

    def initialize_components(self) -> None:
        self._create_gnbs()
        self._create_connected_vehicles()
        self._create_background_vehicles()
        self.all_vehicles = (list(self.connected_vehicles)
                             + list(self.background_vehicles))

        # Sync initial vehicle positions → UE coordinates (coupled mode)
        if self.coupled:
            for cv in self.connected_vehicles:
                cv.sync_position()

        # Assign initial serving gNB after positions are finalised
        for user in self.users:
            assign_serving_gnb(user, self.gnbs, self.shadow_std_db)

        logger.info(
            f"Initialised {len(self.users)} UEs "
            f"({sum(1 for u in self.users if u.slice_type == SliceType.EMBB)} eMBB, "
            f"{sum(1 for u in self.users if u.slice_type == SliceType.URLLC)} URLLC, "
            f"{sum(1 for u in self.users if u.slice_type == SliceType.MMTC)} mMTC) "
            f"and {len(self.all_vehicles)} vehicles"
        )

    def _create_gnbs(self) -> None:
        """Create 3 gNBs at scaled positions and one RB allocator each."""
        for i, pos in enumerate(GNB_POSITIONS_5K):
            self.gnbs.append(GNodeB(i, pos, self.total_rbs_per_gnb))
            self.allocators.append(
                SliceResourceAllocator(self.total_rbs_per_gnb, self.slicing_strategy)
            )

        # UE slice distribution: 50% eMBB / 25% URLLC / 25% mMTC
        embb_count = max(1, int(self.num_connected * 0.50))
        urllc_count = max(1, int(self.num_connected * 0.25))
        mmtc_count = max(1, self.num_connected - embb_count - urllc_count)

        slice_types: List[SliceType] = (
            [SliceType.EMBB] * embb_count
            + [SliceType.URLLC] * urllc_count
            + [SliceType.MMTC] * mmtc_count
        )
        np.random.shuffle(slice_types)

        for uid in range(self.num_connected):
            # area_size=AREA_SIZE so random positions span the full 5000 m grid
            user = MobileUser(uid, slice_types[uid], area_size=AREA_SIZE)
            self.users.append(user)

        logger.info(
            f"Created {len(self.gnbs)} gNBs with "
            f"{embb_count} eMBB / {urllc_count} URLLC / {mmtc_count} mMTC UEs"
        )

    def _create_connected_vehicles(self) -> None:
        """Create ConnectedVehicle agents, one per UE."""
        for i in range(self.num_connected):
            origin = (np.random.randint(0, self.grid_size),
                      np.random.randint(0, self.grid_size))
            dest = (np.random.randint(0, self.grid_size),
                    np.random.randint(0, self.grid_size))
            while dest == origin:
                dest = (np.random.randint(0, self.grid_size),
                        np.random.randint(0, self.grid_size))

            cv = ConnectedVehicle(i, origin, dest, self.users[i], spacing_m=1250.0)
            routes = self.network.get_alternative_routes(origin, dest)
            cv.route = routes[np.random.randint(0, min(len(routes), 3))]
            cv.departure_time = np.random.uniform(0, 3600)
            self.connected_vehicles.append(cv)

        logger.info(f"Created {self.num_connected} connected vehicles")

    def _create_background_vehicles(self) -> None:
        """Create regular (non-UE) background traffic vehicles."""
        self.background_vehicles = create_random_vehicles(
            self.num_background, self.grid_size, self.network,
            id_offset=self.num_connected,
        )
        logger.info(f"Created {self.num_background} background vehicles")

    # ------------------------------------------------------------------
    #  Telecom helpers
    # ------------------------------------------------------------------

    def _run_telecom_step(
        self, current_time: float
    ) -> Tuple[Dict, Dict[int, float]]:
        """Execute one telecom step.

        Returns
        -------
        step_qos : aggregate QoS dict keyed by SliceType
        gnb_urllc_rates : per-gNB URLLC satisfaction rate {gnb_id: rate}
        """
        # Handover checks
        for user in self.users:
            attempted, succeeded = check_handover(
                user, self.gnbs, self.shadow_std_db,
                self.handover_hysteresis_db, self.handover_success_prob,
                cooldown_steps=1,  # 1 s at 1 s time-step resolution
            )
            if attempted:
                self.handover_attempts += 1
                if succeeded:
                    self.handover_successes += 1
                else:
                    self.handover_failures += 1

        # mMTC activity toggle
        activity_prob = mmtc_activity(current_time, self.burst_period)
        for user in self.users:
            if user.slice_type == SliceType.MMTC:
                user.active = np.random.random() < activity_prob
            else:
                user.active = True

        # Resource allocation and QoS evaluation
        step_qos = {s: {"satisfied": 0, "total": 0} for s in SliceType}
        gnb_urllc_satisfied: Dict[int, int] = {gnb.id: 0 for gnb in self.gnbs}
        gnb_urllc_total: Dict[int, int] = {gnb.id: 0 for gnb in self.gnbs}
        step_rbs_used = 0

        for gnb_idx, gnb in enumerate(self.gnbs):
            users_at_gnb: Dict[SliceType, List[MobileUser]] = {
                s: [] for s in SliceType
            }
            for user in self.users:
                if user.serving_gnb == gnb.id and user.active:
                    users_at_gnb[user.slice_type].append(user)

            users_per_slice = {s: len(ul) for s, ul in users_at_gnb.items()}
            allocation = self.allocators[gnb_idx].allocate(users_per_slice)

            for s in SliceType:
                slice_users = users_at_gnb[s]
                n_users = len(slice_users)
                rb_for_slice = allocation[s]
                rb_req = SLICE_CONFIG[s]["rb_requirement"]

                if n_users > 0:
                    rb_per_user = rb_for_slice // n_users
                    rbs_used = min(
                        rb_for_slice,
                        n_users * min(rb_per_user, rb_req),
                    )
                else:
                    rb_per_user = 0
                    rbs_used = 0

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

                    if s == SliceType.URLLC:
                        gnb_urllc_total[gnb.id] += 1
                        if user.qos_satisfied:
                            gnb_urllc_satisfied[gnb.id] += 1

                self.rb_allocated_total[s] += rb_for_slice
                self.rb_used_total[s] += rbs_used
                step_rbs_used += rbs_used

        self.total_rbs_available += len(self.gnbs) * self.total_rbs_per_gnb
        self.total_rbs_used += step_rbs_used

        # Accumulate into global QoS counters
        for s in SliceType:
            self.qos_counts[s]["satisfied"] += step_qos[s]["satisfied"]
            self.qos_counts[s]["total"] += step_qos[s]["total"]

        # Compute per-gNB URLLC satisfaction rates
        gnb_urllc_rates: Dict[int, float] = {}
        for gnb in self.gnbs:
            t = gnb_urllc_total[gnb.id]
            s_count = gnb_urllc_satisfied[gnb.id]
            gnb_urllc_rates[gnb.id] = (s_count / t) if t > 0 else 1.0

        # Track per-step load-imbalance (std dev of total users across gNBs)
        loads = [
            sum(1 for u in self.users if u.serving_gnb == gnb.id)
            for gnb in self.gnbs
        ]
        self._load_std_history.append(float(np.std(loads)))

        return step_qos, gnb_urllc_rates

    def _apply_qos_feedback(self, gnb_urllc_rates: Dict[int, float]) -> None:
        """Map per-gNB URLLC QoS violations to intersection degradation.

        Any gNB whose current URLLC satisfaction rate falls below
        ``urllc_qos_threshold`` disables adaptive signal control at every
        grid intersection within ``_COVERAGE_RADIUS_M`` of that gNB.
        """
        new_degraded: Set[Tuple[int, int]] = set()

        for gnb in self.gnbs:
            rate = gnb_urllc_rates[gnb.id]
            if rate < self.urllc_qos_threshold:
                self.degradation_event_count += 1
                gx, gy = gnb.position
                for pos in self.network.intersections:
                    ix_m = pos[0] * 1250.0
                    iy_m = pos[1] * 1250.0
                    dist = np.sqrt((ix_m - gx) ** 2 + (iy_m - gy) ** 2)
                    if dist <= _COVERAGE_RADIUS_M:
                        new_degraded.add(pos)
                        self.affected_intersection_set.add(pos)

        self.degraded_intersections = new_degraded
        self.total_degradation_steps += len(new_degraded)

    # ------------------------------------------------------------------
    #  Main simulation loop
    # ------------------------------------------------------------------

    def run_simulation(self) -> None:
        mode = "coupled" if self.coupled else "uncoupled"
        logger.info(
            f"Starting {self.sim_duration / 3600:.0f}h M1+T1 simulation "
            f"({mode}, {self.slicing_strategy.value} slicing)"
        )
        self.initialize_components()

        current_time = 0.0
        step = 0

        while current_time < self.sim_duration:
            # 1. Traffic signals (adaptive, degraded intersections revert to fixed-time)
            update_signals(
                self.all_vehicles, self.network, self.time_step,
                degraded_intersections=self.degraded_intersections if self.coupled else None,
            )

            # 2. Move all traffic vehicles
            move_vehicles_step(
                self.all_vehicles, self.network, self.time_step,
                current_time, self.completed_vehicles,
            )

            # 3. Update UE positions
            if self.coupled:
                # Position driven by traffic grid
                for cv in self.connected_vehicles:
                    cv.sync_position()
            else:
                # Independent random-waypoint mobility
                for cv in self.connected_vehicles:
                    cv.user.move(self.time_step)

            # 4. Telecom step: handovers + RB allocation + QoS
            step_qos, gnb_urllc_rates = self._run_telecom_step(current_time)

            # 5. QoS → signal-degradation feedback (coupled only)
            if self.coupled:
                self._apply_qos_feedback(gnb_urllc_rates)

            # 6. Queue-length snapshot for traffic metrics
            collect_queue_lengths(
                self.all_vehicles, self.network.intersections,
                self.queue_lengths,
            )

            current_time = self.advance_time(current_time)
            step += 1

            if step % 900 == 0:
                urllc_t = step_qos[SliceType.URLLC]["total"]
                urllc_s = step_qos[SliceType.URLLC]["satisfied"]
                urllc_rate = (urllc_s / urllc_t * 100) if urllc_t > 0 else 100.0
                completed_cv = sum(
                    1 for v in self.connected_vehicles if v.completed
                )
                completed_bg = sum(
                    1 for v in self.background_vehicles if v.completed
                )
                logger.info(
                    f"Step {step}: t={current_time / 3600:.2f}h | "
                    f"URLLC QoS={urllc_rate:.1f}% | "
                    f"Degraded intersections={len(self.degraded_intersections)} | "
                    f"CV done={completed_cv}/{self.num_connected} | "
                    f"BG done={completed_bg}/{self.num_background}"
                )

        logger.info("Simulation completed")

    # ------------------------------------------------------------------
    #  Report generation
    # ------------------------------------------------------------------

    def generate_report(self) -> Dict:
        # ---- QoS metrics ----
        qos_rates: Dict[SliceType, float] = {}
        for s in SliceType:
            total = self.qos_counts[s]["total"]
            sat = self.qos_counts[s]["satisfied"]
            qos_rates[s] = float(sat / total * 100) if total > 0 else 0.0

        overall_util = (
            float(self.total_rbs_used / self.total_rbs_available * 100)
            if self.total_rbs_available > 0 else 0.0
        )
        resource_waste = 100.0 - overall_util

        ho_success_rate = (
            float(self.handover_successes / self.handover_attempts * 100)
            if self.handover_attempts > 0 else 100.0
        )
        handover_rate_per_min = (
            float(self.handover_attempts / (self.sim_duration / 60.0))
            if self.sim_duration > 0 else 0.0
        )
        avg_load_std = (
            float(np.mean(self._load_std_history))
            if self._load_std_history else 0.0
        )

        # ---- Traffic metrics ----
        bg_completed = [v for v in self.background_vehicles if v.completed]
        cv_completed = [v for v in self.connected_vehicles if v.completed]

        bg_avg_travel = (
            float(np.mean([v.travel_time for v in bg_completed]))
            if bg_completed else 0.0
        )
        bg_avg_delay = (
            float(np.mean([v.total_delay for v in bg_completed]))
            if bg_completed else 0.0
        )
        cv_avg_travel = (
            float(np.mean([v.travel_time for v in cv_completed]))
            if cv_completed else 0.0
        )

        total_emissions_kg = (
            sum(v.emissions_g for v in self.all_vehicles) / 1000.0
        )

        max_queue = max(
            (max(q) for q in self.queue_lengths.values() if q), default=0
        )
        avg_queue = float(
            np.mean([np.mean(q) for q in self.queue_lengths.values() if q])
        ) if any(self.queue_lengths.values()) else 0.0

        return {
            "scenario": "M1+T1 Cross-Domain: Mobility–Telecommunications",
            "mode": "coupled" if self.coupled else "uncoupled",
            "slicing_strategy": self.slicing_strategy.value,
            "components": {
                "connected_vehicles": self.num_connected,
                "background_vehicles": self.num_background,
                "gnb_count": len(self.gnbs),
                "ue_count": len(self.users),
                "intersections": len(self.network.intersections),
            },
            "metrics": {
                # Telecom
                "qos_satisfaction_embb_pct": qos_rates[SliceType.EMBB],
                "qos_satisfaction_urllc_pct": qos_rates[SliceType.URLLC],
                "qos_satisfaction_mmtc_pct": qos_rates[SliceType.MMTC],
                "overall_utilization_pct": overall_util,
                "resource_waste_pct": resource_waste,
                "handover_attempts": int(self.handover_attempts),
                "handover_successes": int(self.handover_successes),
                "handover_failures": int(self.handover_failures),
                "handover_success_rate_pct": ho_success_rate,
                "handover_rate_per_min": handover_rate_per_min,
                "load_imbalance_std_users": avg_load_std,
                # Coupling / signal degradation
                "degradation_events": int(self.degradation_event_count),
                "degradation_duration_s": int(self.total_degradation_steps),
                "affected_intersections": int(len(self.affected_intersection_set)),
                # Traffic
                "bg_completion_rate_pct": float(
                    len(bg_completed) / max(self.num_background, 1) * 100
                ),
                "bg_avg_travel_time_s": bg_avg_travel,
                "bg_avg_delay_s": bg_avg_delay,
                "cv_avg_travel_time_s": cv_avg_travel,
                "total_emissions_kg_co2": float(total_emissions_kg),
                "max_queue_length": int(max_queue),
                "avg_queue_length": float(avg_queue),
            },
        }


# ======================================================================
#  Public API
# ======================================================================

def run_scenario_m1t1(use_helics: bool = False,
                      coupled: bool = True,
                      slicing_strategy: SlicingStrategy = SlicingStrategy.DYNAMIC,
                      **kwargs) -> Dict:
    """Run the M1+T1 cross-domain scenario.

    Args:
        use_helics: Enable HELICS co-simulation transport.
        coupled: If True, vehicle positions drive UE locations and URLLC
                 QoS degradation disables adaptive signal control at nearby
                 intersections. If False, UEs move via random waypoint with
                 no feedback to traffic signals (baseline).
        slicing_strategy: DYNAMIC or STATIC resource-block allocation.
        **kwargs: Forwarded to CrossDomainM1T1 constructor
                  (num_connected, num_background, grid_size,
                  sim_duration_hours, urllc_qos_threshold).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 70)
    logger.info("Cross-Domain Scenario M1+T1: Mobility–Telecommunications")
    logger.info("=" * 70)

    sim = CrossDomainM1T1(
        name="CrossM1T1",
        use_helics=use_helics,
        coupled=coupled,
        slicing_strategy=slicing_strategy,
        **kwargs,
    )
    sim.run_simulation()
    report = sim.generate_report()
    print_report(
        report, logger,
        extra_headers={"Mode": "mode", "Slicing Strategy": "slicing_strategy"},
    )
    sim.cleanup()
    return report


def compare_coupling_modes_m1t1(
    use_helics: bool = False,
    slicing_strategy: SlicingStrategy = SlicingStrategy.DYNAMIC,
    **kwargs,
) -> Dict[str, Dict]:
    """Compare coupled vs uncoupled M1+T1 under the same RNG seed.

    Uses ``np.random.seed(42)`` before each run for reproducibility.

    Returns
    -------
    dict with keys ``"uncoupled"`` and ``"coupled"``, each holding the
    report dict returned by :func:`run_scenario_m1t1`.
    """
    results: Dict[str, Dict] = {}

    for coupled in [False, True]:
        np.random.seed(42)
        label = "coupled" if coupled else "uncoupled"
        logger.info(f"\nRunning {label} mode…")
        report = run_scenario_m1t1(
            use_helics,
            coupled=coupled,
            slicing_strategy=slicing_strategy,
            **kwargs,
        )
        results[label] = report

    logger.info("\n" + "=" * 70)
    logger.info("COUPLING COMPARISON (M1+T1)")
    logger.info("=" * 70)

    for label, report in results.items():
        m = report["metrics"]
        logger.info(f"\n{label.upper()}:")
        logger.info(f"  eMBB QoS:          {m['qos_satisfaction_embb_pct']:.1f}%")
        logger.info(f"  URLLC QoS:         {m['qos_satisfaction_urllc_pct']:.1f}%")
        logger.info(f"  mMTC QoS:          {m['qos_satisfaction_mmtc_pct']:.1f}%")
        logger.info(f"  RB utilisation:    {m['overall_utilization_pct']:.1f}%")
        logger.info(
            f"  Handovers:         {m['handover_attempts']} "
            f"({m['handover_rate_per_min']:.1f}/min, "
            f"{m['handover_success_rate_pct']:.1f}% success)"
        )
        logger.info(f"  Load imbalance:    {m['load_imbalance_std_users']:.1f} users std dev")
        logger.info(f"  Degradation events:{m['degradation_events']}")
        logger.info(f"  Degradation dur.:  {m['degradation_duration_s']} s")
        logger.info(f"  Affected inters.:  {m['affected_intersections']}")
        logger.info(f"  BG avg travel:     {m['bg_avg_travel_time_s']:.1f} s")
        logger.info(f"  BG avg delay:      {m['bg_avg_delay_s']:.1f} s")
        logger.info(f"  Total emissions:   {m['total_emissions_kg_co2']:.1f} kg CO₂")
        logger.info(f"  Max queue:         {m['max_queue_length']}")

    if "uncoupled" in results and "coupled" in results:
        u_m = results["uncoupled"]["metrics"]
        c_m = results["coupled"]["metrics"]
        logger.info("\nCOUPLING DELTAS (coupled vs uncoupled):")
        d_urllc = c_m["qos_satisfaction_urllc_pct"] - u_m["qos_satisfaction_urllc_pct"]
        logger.info(f"  URLLC QoS:      {d_urllc:+.1f} pp")
        d_travel = c_m["bg_avg_travel_time_s"] - u_m["bg_avg_travel_time_s"]
        logger.info(f"  BG avg travel:  {d_travel:+.1f} s")
        d_delay = c_m["bg_avg_delay_s"] - u_m["bg_avg_delay_s"]
        logger.info(f"  BG avg delay:   {d_delay:+.1f} s")
        if u_m["total_emissions_kg_co2"] > 0:
            pct_em = (
                c_m["total_emissions_kg_co2"] / u_m["total_emissions_kg_co2"] - 1
            ) * 100
            logger.info(f"  Emissions:      {pct_em:+.1f}%")
        ho_delta = c_m["handover_attempts"] - u_m["handover_attempts"]
        if u_m["handover_attempts"] > 0:
            ho_pct = ho_delta / u_m["handover_attempts"] * 100
            logger.info(
                f"  Handovers:      {ho_delta:+d} ({ho_pct:+.1f}%)"
            )

    return results
