# Scenario T1: 5G Slice Resource Allocation - Technical Documentation

## Overview

This document provides a comprehensive technical explanation of Scenario T1, including all mathematical formulas, algorithms, and core concepts used in the simulation.

**Simulation Type**: 5G NR resource-block scheduling across three network slices  
**Time Horizon**: 1 hour  
**Time Resolution**: 100 ms intervals (36,000 timesteps)  
**Network Elements**: 3 gNBs, 200 mobile users

---

## 1. Network Topology

### Cell Layout

- **Configuration**: 3 gNBs arranged in a triangular layout covering a 2 km × 2 km urban area
- **gNB Positions**: Equispaced to provide overlapping coverage
  - gNB 0: (500, 500) m
  - gNB 1: (1500, 500) m
  - gNB 2: (1000, 1500) m
- **Cell Radius**: ~800 m effective coverage per gNB
- **Inter-Site Distance**: ~1000 m

### Resource Configuration

Each gNB manages a fixed pool of resource blocks (RBs):
- **Total RBs per gNB**: 100 (representing a 20 MHz NR carrier with 15 kHz SCS)
- **Minimum RB allocation per slice**: 5 RBs (guaranteed floor)

---

## 2. Network Slice Definitions

Three slices serve distinct smart city applications:

### 2.1 eMBB (Enhanced Mobile Broadband)

- **User Count**: 100 users (50% of total)
- **Application**: Video surveillance, AR/VR municipal services
- **RB Requirement**: 2 RBs per user per step for QoS satisfaction
- **Throughput Target**: High (best-effort above minimum)
- **Static Allocation**: 50% of total RBs (50 RBs per gNB)

### 2.2 URLLC (Ultra-Reliable Low-Latency Communication)

- **User Count**: 40 users (20% of total)
- **Application**: Traffic signal control commands, emergency response
- **RB Requirement**: 2 RBs per user per step for QoS satisfaction
- **Latency Target**: Strict (must be served within current step)
- **Static Allocation**: 30% of total RBs (30 RBs per gNB)

### 2.3 mMTC (Massive Machine-Type Communication)

- **User Count**: 60 users (30% of total)
- **Application**: Smart meters, environmental sensors, IoT gateways
- **RB Requirement**: 1 RB per user per step for QoS satisfaction
- **Traffic Pattern**: Periodic reporting with bursty peaks
- **Static Allocation**: 20% of total RBs (20 RBs per gNB)

---

## 3. User Mobility Model

### 3.1 Random Waypoint

Users move within the 2 km × 2 km area using the Random Waypoint model:

1. Each user starts at a uniformly random position $(x_0, y_0) \sim U(0, 2000) \times U(0, 2000)$ m
2. A random waypoint is selected: $(x_w, y_w) \sim U(0, 2000) \times U(0, 2000)$ m
3. The user moves toward the waypoint at a constant speed:

$$v_{user} \sim U(0.5, 2.0) \text{ m/s}$$

representing pedestrian-speed mobility (1.8–7.2 km/h).

4. Upon reaching the waypoint (within 5 m), a new waypoint is selected.

### 3.2 Position Update

At each time step $\Delta t = 0.1$ s:

$$\theta = \arctan2(y_w - y, x_w - x)$$

$$x_{new} = x + v \cdot \Delta t \cdot \cos(\theta)$$

$$y_{new} = y + v \cdot \Delta t \cdot \sin(\theta)$$

Positions are clamped to the area boundaries $[0, 2000] \times [0, 2000]$ m.

---

## 4. Radio Propagation Model

### 4.1 3GPP Urban Macro Path Loss

The received power from gNB $j$ at user position $d$ meters away:

$$PL(d) = 128.1 + 37.6 \cdot \log_{10}(d) \quad \text{[dB]}$$

where $d$ is the 2D Euclidean distance in **km**:

$$d = \frac{\sqrt{(x_{user} - x_{gNB})^2 + (y_{user} - y_{gNB})^2}}{1000}$$

A minimum distance of 10 m is enforced to prevent numerical singularity.

### 4.2 Received Signal Strength

$$P_{rx}(d) = P_{tx} - PL(d) \quad \text{[dBm]}$$

where $P_{tx} = 46$ dBm (typical macro gNB transmit power).

### 4.3 Shadow Fading

A log-normal shadow fading component is added:

$$P_{rx,faded} = P_{rx} + X_\sigma, \quad X_\sigma \sim \mathcal{N}(0, \sigma^2)$$

with $\sigma = 4$ dB (moderate urban environment).

---

## 5. Serving Cell Selection and Handover

### 5.1 Serving Cell

Each user is served by the gNB providing the strongest received signal:

$$\text{serving\_gNB}(u) = \arg\max_{j \in \{0,1,2\}} P_{rx,j}(u)$$

### 5.2 Handover Trigger

A handover occurs when a neighboring cell's signal exceeds the serving cell's signal by a hysteresis margin:

$$P_{rx,neighbor} > P_{rx,serving} + H_{margin}$$

where $H_{margin} = 3$ dB.

### 5.3 Handover Outcome

Each triggered handover succeeds with probability:

$$P_{success} = 0.95$$

A failed handover results in one simulation step of QoS outage for that user.

---

## 6. Slice Resource Allocation Strategies

### 6.1 Static Slicing

Each gNB divides its RB pool into fixed fractions, regardless of instantaneous demand:

| Slice | Fraction | RBs (out of 100) |
|-------|----------|-------------------|
| eMBB  | 50%      | 50                |
| URLLC | 30%      | 30                |
| mMTC  | 20%      | 20                |

Within each slice, available RBs are distributed equally among connected users belonging to that slice. If the per-user allocation meets or exceeds the slice's RB requirement, QoS is satisfied.

**Per-user allocation (static)**:

$$RB_{user} = \left\lfloor \frac{RB_{slice}}{N_{slice,gNB}} \right\rfloor$$

where $N_{slice,gNB}$ is the number of users of that slice type connected to the gNB.

### 6.2 Dynamic Slicing

RBs are allocated proportionally to each slice's instantaneous demand, with a guaranteed minimum floor:

**Demand per slice**:

$$D_{slice} = N_{slice,gNB} \cdot RB_{req,slice}$$

where $RB_{req,slice}$ is the per-user RB requirement for the slice type.

**Proportional allocation**:

$$RB_{slice} = \max\!\left(RB_{min},\; \left\lfloor \frac{D_{slice}}{D_{total}} \cdot RB_{total} \right\rfloor\right)$$

where $RB_{min} = 5$ is the guaranteed floor and $D_{total} = \sum_{s} D_s$.

After flooring, any remaining RBs (due to rounding) are left unallocated.

This is analogous to the adaptive signal timing in Scenario M1 (Equation for $T_{green}$), where green time is allocated proportionally to queue demand.

### 6.3 QoS Evaluation

For each user $u$ in slice $s$ at gNB $j$, QoS is satisfied when:

$$RB_{user}(u) \geq RB_{req}(s)$$

A user undergoing a failed handover automatically has QoS = unsatisfied for that step.

---

## 7. Traffic Demand Variation

### 7.1 mMTC Bursty Traffic

mMTC devices have a time-varying activity probability that simulates synchronized reporting bursts:

$$P_{active}(t) = 0.3 + 0.5 \cdot \left|\sin\!\left(\frac{2\pi \cdot t}{T_{burst}}\right)\right|$$

where $T_{burst} = 900$ s (15-minute reporting cycle). Activity ranges from 30% (trough) to 80% (peak).

Only active mMTC users generate demand in a given step.

### 7.2 eMBB and URLLC

eMBB and URLLC users are always active (100% duty cycle) while connected to the network.

---

## 8. Performance Metrics

### 8.1 Per-Slice QoS Satisfaction Rate

$$QoS_{slice} = \frac{\sum_{t} \sum_{u \in slice} \mathbb{1}[RB_{user}(u,t) \geq RB_{req}(slice)]}{\sum_{t} N_{active,slice}(t)} \times 100\%$$

### 8.2 Slice Utilization

$$U_{slice} = \frac{\text{RBs actually used by slice}}{\text{RBs allocated to slice}} \times 100\%$$

### 8.3 Resource Waste

$$W = \frac{\text{RBs allocated but unused (across all slices)}}{\text{Total RBs}} \times 100\%$$

### 8.4 Handover Statistics

- **Total handover attempts**: Count of triggered handovers
- **Handover success rate**: Successful / Total × 100%
- **Handover failures**: Count of failed handovers causing QoS outage

### 8.5 Overall System Utilization

$$U_{system} = \frac{\sum_{gNB} \text{RBs used}}{\sum_{gNB} RB_{total}} \times 100\%$$

---

## 9. Simulation Pseudocode

```
INITIALIZE:
    Create 3 gNBs at fixed positions
    Create 200 users:
        100 eMBB, 40 URLLC, 60 mMTC
        Random initial positions and waypoints
    Select slicing strategy (STATIC or DYNAMIC)

FOR t = 0 TO 3600 STEP 0.1:
    # 1. User Mobility
    FOR each user:
        Move toward waypoint at user speed × dt
        If reached waypoint: select new waypoint
        Clamp position to area bounds

    # 2. Path Loss & Serving Cell
    FOR each user:
        Calculate P_rx from each gNB (path loss + fading)
        Determine best gNB
        If best ≠ current serving AND P_rx,best > P_rx,serving + 3 dB:
            Trigger handover
            With P=0.95: succeed (update serving gNB)
            With P=0.05: fail (mark QoS unsatisfied)

    # 3. Determine Active Users
    FOR each mMTC user:
        Calculate P_active(t)
        Mark active/inactive stochastically

    # 4. Resource Allocation (per gNB)
    Count users per slice per gNB
    IF strategy == STATIC:
        RB_embb = 50, RB_urllc = 30, RB_mmtc = 20
    ELSE (DYNAMIC):
        Calculate demand per slice
        Allocate proportionally with floor = 5

    # 5. QoS Evaluation
    FOR each active user:
        RB_user = floor(RB_slice / N_slice_users)
        If RB_user >= RB_req: QoS satisfied
        Else: QoS unsatisfied
    Track allocated-but-unused RBs as waste

    # 6. Collect Metrics
    Record per-slice QoS, utilization, waste, handovers

GENERATE REPORT:
    Aggregate per-slice QoS satisfaction rates
    Calculate slice utilization and resource waste
    Summarize handover statistics
    Compare static vs. dynamic if both were run
```

---

## 10. Validation Criteria

### 10.1 Physical Plausibility

- Path loss increases with distance (monotonic)
- Received power is always below transmit power
- Users are always served by closest/strongest gNB (barring hysteresis)
- Handover rate increases with user speed

### 10.2 Strategy Differentiation

- Dynamic slicing must produce **higher overall QoS satisfaction** than static when demand is imbalanced
- Static slicing must produce **lower resource waste** when demand matches the fixed allocation ratios
- Under equal demand across slices, both strategies should converge to similar performance

### 10.3 Slice Isolation

- URLLC QoS should remain high (>95%) even during mMTC traffic bursts under dynamic slicing
- In static slicing, mMTC bursts should cause QoS degradation only within the mMTC slice

### 10.4 Conservation

- Total RBs allocated per gNB per step ≤ 100
- Total active users per step ≤ 200

---

## 11. Cross-Domain Coupling Points (Future)

### 11.1 T1 + M1 (Mobility–Telecommunications)

- **M1 → T1**: Vehicle positions from Scenario M1 serve as user positions for a subset of URLLC users (traffic signal control commands). Published via HELICS topic `vehicle_positions`.
- **T1 → M1**: QoS satisfaction for URLLC users determines whether adaptive signal control commands are delivered on time. Published via HELICS topic `urllc_qos_status`.

### 11.2 HELICS Publications

| Direction | Topic | Type | Unit |
|-----------|-------|------|------|
| T1 → M1 | `urllc_qos_status` | double | fraction (0–1) |
| T1 → E1 | `total_network_load` | double | W |
| M1 → T1 | `vehicle_positions` | string | JSON array |

---

## 12. Computational Complexity

- **Time steps**: 36,000
- **Per-step operations**:
  - Mobility update: O(200) = O(N_users)
  - Path loss calculation: O(200 × 3) = O(N_users × N_gNBs)
  - Resource allocation: O(3 × 3) = O(N_gNBs × N_slices)
  - QoS evaluation: O(200) = O(N_users)
- **Total**: O(36,000 × 200) ≈ 7.2 × 10⁶ operations
- **Expected runtime**: < 30 seconds on modern hardware
