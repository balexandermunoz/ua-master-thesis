"""
Cross-Domain Scenario E2+M1: Energy–Mobility Integration

EVs physically navigate the M1 traffic network to reach charging stations
placed at grid intersections.  Charging demand feeds back into the E2
grid model, coupling travel delay with grid load.

Comparison modes:
  - coupled   : EVs drive through traffic to reach their station
  - uncoupled : EVs teleport to the station (baseline without cross-domain effects)
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum

from engine.base import BaseFederate, print_report
from scenarios.scenario_m1 import (
    TrafficNetwork, Vehicle as M1Vehicle,
    create_random_vehicles, update_signals, move_vehicles_step,
    collect_queue_lengths,
)
from scenarios.scenario_e2 import (
    ElectricVehicle, ChargingStation, ChargerType,
    TransformerModel, TimeOfUseTariff, SmartChargingController,
    ChargingStrategy,
    calculate_base_load, uncoordinated_alloc,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  EV vehicle that combines M1 traffic movement with E2 charging
# ---------------------------------------------------------------------------

class EVTrafficVehicle(M1Vehicle):
    """An EV that drives through traffic to a charging station, charges, and
    optionally drives back.  Inherits M1 movement mechanics and adds E2
    battery / charging state."""

    class Phase(Enum):
        DRIVING_TO_STATION = "driving_to_station"
        CHARGING = "charging"
        DRIVING_BACK = "driving_back"
        DONE = "done"

    def __init__(self, vehicle_id: int, origin: Tuple[int, int],
                 station_pos: Tuple[int, int], ev: ElectricVehicle,
                 return_destination: Tuple[int, int]):
        super().__init__(vehicle_id, origin, station_pos)
        self.ev = ev  # E2 battery model
        self.station_pos = station_pos
        self.return_destination = return_destination
        self.phase = self.Phase.DRIVING_TO_STATION

        # Charging bookkeeping
        self.charging_station: Optional[ChargingStation] = None
        self.arrived_at_intersection_time: Optional[float] = None
        self.arrived_at_station_time: Optional[float] = None
        self.charging_complete = False

    # ----- convenience -----
    @property
    def at_station(self) -> bool:
        return (self.completed and
                self.phase == self.Phase.DRIVING_TO_STATION)


# ---------------------------------------------------------------------------
#  Cross-domain simulation
# ---------------------------------------------------------------------------

class CrossDomainE2M1(BaseFederate):
    """Coupled Energy–Mobility simulation on a shared 5×5 traffic grid."""

    def __init__(self, name: str = "CrossE2M1",
                 use_helics: bool = False,
                 coupled: bool = True,
                 num_evs: int = 500,
                 num_background: int = 2000,
                 grid_size: int = 5,
                 sim_duration_hours: int = 3,
                 charging_strategy: ChargingStrategy = ChargingStrategy.SMART):
        super().__init__(name, use_helics,
                         time_step=1.0,
                         sim_duration=sim_duration_hours * 3600)
        self.coupled = coupled
        self.num_evs = num_evs
        self.num_background = num_background
        self.grid_size = grid_size
        self.charging_strategy = charging_strategy

        # ---- shared network (M1 grid) ----
        self.network = TrafficNetwork(grid_size=grid_size, spacing_m=1250.0)

        # ---- traffic ----
        self.background_vehicles: List[M1Vehicle] = []
        self.ev_vehicles: List[EVTrafficVehicle] = []
        self.all_vehicles: List[M1Vehicle] = []   # union for signal updates
        self.completed_vehicles: List[M1Vehicle] = []

        # ---- charging infrastructure (E2) ----
        self.charging_stations: List[ChargingStation] = []
        self.transformers: List[TransformerModel] = []
        self.tariff = TimeOfUseTariff()
        self.smart_controller: Optional[SmartChargingController] = None

        # Grid params
        self.grid_capacity_kw = 2500.0
        self.base_load_kw = 2000.0

        # ---- metrics storage ----
        self.queue_lengths: Dict[Tuple[int, int], List[int]] = {
            pos: [] for pos in self.network.intersections
        }
        self.load_profile: List[float] = []
        self.peak_load_kw = 0.0
        self.v2g_energy_kwh = 0.0

    # ------------------------------------------------------------------
    #  Initialization
    # ------------------------------------------------------------------

    def initialize_components(self):
        self._place_charging_stations()
        self._create_transformers()
        self._create_evs()
        self._create_background_vehicles()
        if self.coupled:
            self.all_vehicles = list(self.ev_vehicles) + list(self.background_vehicles)
        else:
            self.all_vehicles = list(self.background_vehicles)  # EVs not in traffic
        self.smart_controller = SmartChargingController(
            self.charging_stations, self.tariff)

    def _place_charging_stations(self):
        """Place 5 DC-fast stations at inner intersections and
        8 Level-2 stations at perimeter intersections."""
        dc_positions = [(1, 1), (1, 3), (2, 2), (3, 1), (3, 3)]
        l2_positions = [(0, 0), (0, 2), (0, 4), (2, 0),
                        (2, 4), (4, 0), (4, 2), (4, 4)]

        sid = 0
        for pos in dc_positions:
            self.charging_stations.append(
                ChargingStation(sid, ChargerType.DC_FAST,
                                node_id=sid, num_ports=4))
            self.charging_stations[-1]._grid_pos = pos  # tag with grid pos
            sid += 1
        for pos in l2_positions:
            self.charging_stations.append(
                ChargingStation(sid, ChargerType.LEVEL_2,
                                node_id=sid, num_ports=4))
            self.charging_stations[-1]._grid_pos = pos
            sid += 1

        self._station_by_pos: Dict[Tuple[int, int], ChargingStation] = {
            s._grid_pos: s for s in self.charging_stations
        }
        logger.info(f"Placed {len(dc_positions)} DC-fast + "
                     f"{len(l2_positions)} L2 stations on the grid")

    def _create_transformers(self):
        for i, station in enumerate(self.charging_stations):
            cap = np.random.uniform(500, 1000) if station.charger_type == ChargerType.DC_FAST \
                  else np.random.uniform(150, 300)
            self.transformers.append(TransformerModel(i, cap, station.node_id))

    def _create_evs(self):
        """Create EV traffic vehicles with random origins, each assigned
        to the nearest charging station (random tie-breaking distributes
        EVs across both DC-fast and L2 stations)."""
        station_positions = list(self._station_by_pos.keys())

        for i in range(self.num_evs):
            origin = (np.random.randint(0, self.grid_size),
                      np.random.randint(0, self.grid_size))

            # Pick nearest station with random tie-breaking
            candidates = [p for p in station_positions if p != origin]
            best_pos = min(candidates,
                           key=lambda p: (abs(p[0]-origin[0]) + abs(p[1]-origin[1]),
                                          np.random.random()))

            # Fallback if all stations are origin (impossible with 13 stations)
            if not candidates:
                best_pos = station_positions[0]

            # Return destination (random, different from station)
            ret = (np.random.randint(0, self.grid_size),
                   np.random.randint(0, self.grid_size))
            while ret == best_pos:
                ret = (np.random.randint(0, self.grid_size),
                       np.random.randint(0, self.grid_size))

            # E2 battery model
            capacity = np.random.uniform(40.0, 100.0)
            initial_soc = np.random.uniform(0.2, 0.5)
            ev = ElectricVehicle(i, capacity, initial_soc)
            ev.v2g_enabled = (self.charging_strategy == ChargingStrategy.V2G
                              and np.random.random() > 0.5)

            # Traffic vehicle
            ev_veh = EVTrafficVehicle(i, origin, best_pos, ev, ret)
            routes = self.network.get_alternative_routes(origin, best_pos)
            ev_veh.route = routes[np.random.randint(0, min(len(routes), 3))]
            ev_veh.departure_time = np.random.uniform(0, 3600)

            self.ev_vehicles.append(ev_veh)

        logger.info(f"Created {len(self.ev_vehicles)} EVs heading to stations")

    def _create_background_vehicles(self):
        """Create regular (non-EV) traffic vehicles identical to M1."""
        self.background_vehicles = create_random_vehicles(
            self.num_background, self.grid_size, self.network,
            id_offset=self.num_evs)

    # ------------------------------------------------------------------
    #  Traffic simulation helpers (reuse M1 logic)
    # ------------------------------------------------------------------

    def _update_traffic_signals(self, dt: float):
        update_signals(self.all_vehicles, self.network, dt, adaptive=True)

    def _move_vehicles(self, dt: float, current_time: float):
        """Move all vehicles (background + EVs) through the traffic grid."""
        move_vehicles_step(self.all_vehicles, self.network, dt,
                           current_time, self.completed_vehicles)

    def _teleport_evs(self, current_time: float):
        """Uncoupled mode: teleport EVs directly to their destination,
        bypassing the traffic network entirely."""
        for ev_veh in self.ev_vehicles:
            if ev_veh.completed or ev_veh.phase == EVTrafficVehicle.Phase.DONE:
                continue
            if current_time < ev_veh.departure_time:
                continue
            if not ev_veh.departed:
                ev_veh.departed = True
            # Teleport to destination in one step
            ev_veh.current_position = ev_veh.destination
            ev_veh.current_route_index = len(ev_veh.route) - 1
            ev_veh.completed = True

    # ------------------------------------------------------------------
    #  EV lifecycle: arrive at station → charge → depart
    # ------------------------------------------------------------------

    def _handle_ev_arrivals(self, current_time: float):
        """When an EV reaches its station intersection, connect it."""
        for ev_veh in self.ev_vehicles:
            if ev_veh.phase != EVTrafficVehicle.Phase.DRIVING_TO_STATION:
                continue
            if not ev_veh.at_station:
                continue

            # Record first arrival at station intersection
            if ev_veh.arrived_at_intersection_time is None:
                ev_veh.arrived_at_intersection_time = current_time

            station = self._station_by_pos.get(ev_veh.station_pos)
            if station is None:
                continue

            if station.can_accept_vehicle():
                station.add_vehicle(ev_veh.ev)
                ev_veh.ev.connect(current_time,
                                  current_time + 7200,   # max 2 h dwell
                                  station.id)
                ev_veh.charging_station = station
                ev_veh.arrived_at_station_time = current_time
                ev_veh.phase = EVTrafficVehicle.Phase.CHARGING
            # else: stays "completed" at intersection waiting for a port
            # (will retry next step)

    def _handle_charging(self, current_time: float, dt: float):
        """Charge connected EVs (runs every 5-min window)."""
        hour = (current_time / 3600.0) % 24
        price = self.tariff.get_price(hour)
        dt_hours = dt / 3600.0
        base_load = calculate_base_load(hour)

        # Determine power allocation
        if self.charging_strategy == ChargingStrategy.UNCOORDINATED:
            allocation = uncoordinated_alloc(self.charging_stations)
        else:
            allocation = self.smart_controller.optimize_charging(
                current_time, base_load, self.grid_capacity_kw)

        total_ev_load = 0.0
        for ev_veh in self.ev_vehicles:
            if ev_veh.phase != EVTrafficVehicle.Phase.CHARGING:
                continue
            evobj = ev_veh.ev
            if not evobj.is_connected:
                continue

            # V2G discharge during peak
            if (self.charging_strategy == ChargingStrategy.V2G
                    and evobj.v2g_enabled
                    and 17 <= hour < 21
                    and evobj.soc > evobj.soc_min + 0.05):
                discharged = evobj.discharge(
                    evobj.max_discharge_rate_kw, dt_hours, price)
                total_ev_load -= discharged
                self.v2g_energy_kwh += discharged * dt_hours
            elif evobj.id in allocation and allocation[evobj.id] > 0:
                actual = evobj.charge(allocation[evobj.id], dt_hours, price)
                total_ev_load += actual

            # Check if charged enough or dwell expired
            if (evobj.soc >= evobj.soc_target or
                    current_time >= evobj.departure_time):
                ev_veh.charging_complete = True

        total_load = base_load + total_ev_load
        self.load_profile.append(total_load)
        self.peak_load_kw = max(self.peak_load_kw, total_load)

        # Transformer loading
        for t in self.transformers:
            node_load = total_load / max(len(self.transformers), 1)
            t.calculate_loading(node_load)

    def _handle_ev_departures(self, current_time: float):
        """Disconnect charged EVs from stations and send them back."""
        for ev_veh in self.ev_vehicles:
            if ev_veh.phase != EVTrafficVehicle.Phase.CHARGING:
                continue
            if not ev_veh.charging_complete:
                continue

            station = ev_veh.charging_station
            if station:
                station.remove_vehicle(ev_veh.ev)
            ev_veh.ev.disconnect()

            # Prepare return trip
            ev_veh.phase = EVTrafficVehicle.Phase.DRIVING_BACK
            ev_veh.destination = ev_veh.return_destination
            ev_veh.completed = False
            ev_veh.current_route_index = 0
            routes = self.network.get_alternative_routes(
                ev_veh.current_position, ev_veh.return_destination)
            ev_veh.route = routes[np.random.randint(0, min(len(routes), 3))]
            ev_veh.departed = True
            ev_veh.travel_countdown = 0

    # ------------------------------------------------------------------
    #  Metrics collection
    # ------------------------------------------------------------------

    def _collect_queue_metrics(self):
        collect_queue_lengths(self.all_vehicles, self.network.intersections,
                              self.queue_lengths)

    # ------------------------------------------------------------------
    #  Main loop
    # ------------------------------------------------------------------

    def run_simulation(self):
        mode = "coupled" if self.coupled else "uncoupled"
        logger.info(f"Starting {self.sim_duration/3600:.0f}h E2+M1 simulation "
                    f"({mode}, {self.charging_strategy.value})")
        self.initialize_components()

        current_time = 0.0
        step = 0
        charging_interval = 300  # apply charging every 300 steps (5 min)

        while current_time < self.sim_duration:
            # 1. Traffic signals (adaptive)
            self._update_traffic_signals(self.time_step)

            # 2. Move all vehicles
            self._move_vehicles(self.time_step, current_time)
            if not self.coupled:
                self._teleport_evs(current_time)

            # 3. EV lifecycle
            self._handle_ev_arrivals(current_time)
            if step % charging_interval == 0:
                self._handle_charging(current_time, charging_interval)
            self._handle_ev_departures(current_time)

            # 4. Re-add EVs that finished return trips
            for ev_veh in self.ev_vehicles:
                if (ev_veh.phase == EVTrafficVehicle.Phase.DRIVING_BACK
                        and ev_veh.completed):
                    ev_veh.phase = EVTrafficVehicle.Phase.DONE

            # 5. Metrics
            self._collect_queue_metrics()

            current_time = self.advance_time(current_time)
            step += 1

            if step % 900 == 0:
                evs_at_station = sum(1 for e in self.ev_vehicles
                                     if e.phase == EVTrafficVehicle.Phase.CHARGING)
                evs_done = sum(1 for e in self.ev_vehicles
                               if e.phase == EVTrafficVehicle.Phase.DONE)
                logger.info(
                    f"Step {step}: t={current_time/3600:.2f}h | "
                    f"Charging: {evs_at_station} | Done: {evs_done}/{self.num_evs} | "
                    f"Background completed: "
                    f"{sum(1 for v in self.background_vehicles if v.completed)}"
                    f"/{self.num_background}")

        logger.info("Simulation completed")

    # ------------------------------------------------------------------
    #  Report
    # ------------------------------------------------------------------

    def generate_report(self) -> Dict:
        # -- traffic metrics (all vehicles) --
        all_completed = [v for v in self.all_vehicles if v.completed]
        bg_completed = [v for v in self.background_vehicles if v.completed]
        ev_completed_drive = [e for e in self.ev_vehicles
                              if e.phase in (EVTrafficVehicle.Phase.DONE,
                                             EVTrafficVehicle.Phase.CHARGING,
                                             EVTrafficVehicle.Phase.DRIVING_BACK)]

        ev_to_station_times = [
            e.arrived_at_station_time - e.departure_time
            for e in self.ev_vehicles
            if e.arrived_at_station_time is not None
        ]
        avg_ev_travel_to_station = float(np.mean(ev_to_station_times)) if ev_to_station_times else 0.0

        ev_drive_times = [
            e.arrived_at_intersection_time - e.departure_time
            for e in self.ev_vehicles
            if e.arrived_at_intersection_time is not None
        ]
        avg_ev_drive_time = float(np.mean(ev_drive_times)) if ev_drive_times else 0.0

        ev_queue_times = [
            e.arrived_at_station_time - e.arrived_at_intersection_time
            for e in self.ev_vehicles
            if e.arrived_at_station_time is not None
                and e.arrived_at_intersection_time is not None
        ]
        avg_ev_queue_time = float(np.mean(ev_queue_times)) if ev_queue_times else 0.0

        bg_avg_travel = float(np.mean([v.travel_time for v in bg_completed])) if bg_completed else 0.0
        bg_avg_delay = float(np.mean([v.total_delay for v in bg_completed])) if bg_completed else 0.0

        total_emissions_kg = sum(v.emissions_g for v in self.all_vehicles) / 1000.0

        max_queue = max(
            (max(q) for q in self.queue_lengths.values() if q), default=0)
        avg_queue = float(np.mean(
            [np.mean(q) for q in self.queue_lengths.values() if q]))

        # -- charging metrics --
        evs_charged = sum(1 for e in self.ev_vehicles
                          if e.ev.soc >= e.ev.soc_target)
        total_energy = sum(e.ev.energy_charged_kwh for e in self.ev_vehicles)
        total_cost = sum(e.ev.charging_cost for e in self.ev_vehicles)
        total_v2g_rev = sum(e.ev.v2g_revenue for e in self.ev_vehicles)
        avg_final_soc = float(np.mean([e.ev.soc for e in self.ev_vehicles]))

        max_loading = max(
            (max(t.loading_history) for t in self.transformers
             if t.loading_history), default=0.0)
        total_overloads = sum(t.overload_count for t in self.transformers)

        report = {
            "scenario": "E2+M1 Cross-Domain: Energy–Mobility",
            "mode": "coupled" if self.coupled else "uncoupled",
            "charging_strategy": self.charging_strategy.value,
            "components": {
                "ev_count": self.num_evs,
                "background_vehicles": self.num_background,
                "charging_stations": len(self.charging_stations),
                "intersections": len(self.network.intersections),
                "grid_capacity_kw": self.grid_capacity_kw,
            },
            "metrics": {
                # Traffic
                "bg_completion_rate_pct": float(
                    len(bg_completed) / max(self.num_background, 1) * 100),
                "bg_avg_travel_time_s": bg_avg_travel,
                "bg_avg_delay_s": bg_avg_delay,
                "total_emissions_kg_co2": float(total_emissions_kg),
                "max_queue_length": int(max_queue),
                "avg_queue_length": float(avg_queue),
                # EV travel
                "avg_ev_travel_to_station_s": avg_ev_travel_to_station,
                "avg_ev_drive_time_s": avg_ev_drive_time,
                "avg_ev_queue_time_s": avg_ev_queue_time,
                "evs_at_station_node": sum(
                    1 for e in self.ev_vehicles
                    if e.arrived_at_intersection_time is not None),
                "evs_reached_station": sum(
                    1 for e in self.ev_vehicles
                    if e.arrived_at_station_time is not None),
                # Charging
                "evs_meeting_soc_target": evs_charged,
                "avg_final_soc": avg_final_soc,
                "total_energy_charged_kwh": float(total_energy),
                "total_charging_cost_usd": float(total_cost),
                "peak_grid_load_kw": float(self.peak_load_kw),
                "max_transformer_loading_pct": float(max_loading),
                "transformer_overloads": int(total_overloads),
                "v2g_energy_kwh": float(self.v2g_energy_kwh),
                "v2g_revenue_usd": float(total_v2g_rev),
            },
        }
        return report


# ======================================================================
#  Public API
# ======================================================================

def run_scenario_e2m1(use_helics: bool = False,
                      coupled: bool = True,
                      charging_strategy: ChargingStrategy = ChargingStrategy.SMART,
                      **kwargs) -> Dict:
    """Run the E2+M1 cross-domain scenario.

    Args:
        use_helics: Enable HELICS co-simulation transport.
        coupled: If True, EVs drive through traffic. If False, EVs teleport
                 (baseline without cross-domain effects).
        charging_strategy: UNCOORDINATED, SMART, or V2G.
        **kwargs: Forwarded to CrossDomainE2M1 constructor
                  (num_evs, num_background, grid_size, sim_duration_hours).
    """
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("=" * 70)
    logger.info("Cross-Domain Scenario E2+M1: Energy–Mobility Integration")
    logger.info("=" * 70)

    sim = CrossDomainE2M1(name="CrossE2M1",
                          use_helics=use_helics,
                          coupled=coupled,
                          charging_strategy=charging_strategy,
                          **kwargs)
    sim.run_simulation()
    report = sim.generate_report()
    print_report(report, logger,
                 extra_headers={"Mode": "mode",
                                "Charging Strategy": "charging_strategy"})
    sim.cleanup()
    return report


def compare_coupling_modes(use_helics: bool = False,
                           charging_strategy: ChargingStrategy = ChargingStrategy.SMART,
                           **kwargs) -> Dict[str, Dict]:
    """Compare coupled vs uncoupled E2+M1 under the same RNG seed."""
    results = {}
    for coupled in [False, True]:
        np.random.seed(42)
        label = "coupled" if coupled else "uncoupled"
        logger.info(f"\nRunning {label} mode...")
        report = run_scenario_e2m1(use_helics, coupled=coupled,
                                   charging_strategy=charging_strategy,
                                   **kwargs)
        results[label] = report

    logger.info("\n" + "=" * 70)
    logger.info("COUPLING COMPARISON (E2+M1)")
    logger.info("=" * 70)

    for label, report in results.items():
        m = report["metrics"]
        logger.info(f"\n{label.upper()}:")
        logger.info(f"  Avg EV Drive Time to Station: {m['avg_ev_drive_time_s']:.1f} s")
        logger.info(f"  Avg EV Queue Time at Station: {m['avg_ev_queue_time_s']:.1f} s")
        logger.info(f"  EVs at Station Node: {m['evs_at_station_node']}")
        logger.info(f"  EVs Connected (got port): {m['evs_reached_station']}")
        logger.info(f"  EVs Meeting SOC Target: {m['evs_meeting_soc_target']}/{report['components']['ev_count']}")
        logger.info(f"  Peak Grid Load: {m['peak_grid_load_kw']:.1f} kW")
        logger.info(f"  Total Energy Charged: {m['total_energy_charged_kwh']:.1f} kWh")
        logger.info(f"  Total Charging Cost: ${m['total_charging_cost_usd']:.2f}")
        logger.info(f"  Background Avg Travel: {m['bg_avg_travel_time_s']:.1f} s")
        logger.info(f"  Background Avg Delay: {m['bg_avg_delay_s']:.1f} s")
        logger.info(f"  Total Emissions: {m['total_emissions_kg_co2']:.1f} kg CO\u2082")
        logger.info(f"  Max Queue: {m['max_queue_length']}")

    # Delta summary
    u_m = results["uncoupled"]["metrics"]
    c_m = results["coupled"]["metrics"]
    logger.info("\nCOUPLING DELTAS (coupled vs uncoupled):")
    logger.info(f"  EV Drive Time: +{c_m['avg_ev_drive_time_s'] - u_m['avg_ev_drive_time_s']:.1f} s")
    pct_em = (c_m['total_emissions_kg_co2'] / max(u_m['total_emissions_kg_co2'], 1) - 1) * 100
    logger.info(f"  Total Emissions: {pct_em:+.1f}%")
    pct_soc = (c_m['evs_meeting_soc_target'] / max(u_m['evs_meeting_soc_target'], 1) - 1) * 100
    logger.info(f"  EVs Meeting SOC: {pct_soc:+.1f}%")
    pct_energy = (c_m['total_energy_charged_kwh'] / max(u_m['total_energy_charged_kwh'], 1) - 1) * 100
    logger.info(f"  Energy Charged: {pct_energy:+.1f}%")

    return results
