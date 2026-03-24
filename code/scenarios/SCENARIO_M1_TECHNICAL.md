# Scenario M1: Urban Traffic Congestion Management - Technical Documentation

## Overview

This scenario simulates a 5km × 5km urban traffic network with intelligent traffic management systems to evaluate the effectiveness of adaptive signal control versus traditional fixed-time signals in reducing congestion, travel times, and emissions.

### System Configuration

- **Network**: 5×5 grid with 25 signalized intersections
- **Intersections**: 1 km spacing (500m link length)
- **Vehicles**: 2,500 vehicles with random origin-destination pairs
- **Simulation Duration**: 3 hours (10,800 seconds)
- **Time Step**: 1 second
- **Speed Limit**: 50 km/h (13.9 m/s)

---

## 1. Core Mathematical Models

### 1.1 A* Pathfinding Algorithm

The shortest path calculation uses the A* algorithm with Manhattan distance heuristic.

#### Heuristic Function

$$
h(n) = |x_n - x_{goal}| + |y_n - y_{goal}|
$$

where:
- $h(n)$ = estimated cost from node $n$ to goal
- $(x_n, y_n)$ = coordinates of node $n$
- $(x_{goal}, y_{goal})$ = coordinates of goal node

#### Cost Function

$$
f(n) = g(n) + h(n)
$$

where:
- $f(n)$ = total estimated cost of path through node $n$
- $g(n)$ = actual cost from start to node $n$
- $h(n)$ = heuristic estimated cost from node $n$ to goal

#### Path Reconstruction

Once the goal is reached, the path is reconstructed by backtracking through the `came_from` mapping:

$$
path = [goal, parent(goal), parent(parent(goal)), ..., start]
$$

**Implementation Details**:
- Priority queue maintains frontier nodes sorted by $f(n)$
- Each edge has unit cost (cost = 1)
- Admissible heuristic guarantees optimal path

---

### 1.2 Adaptive Traffic Signal Control

#### Green Time Calculation

The adaptive signal system adjusts green time based on real-time queue lengths:

$$
T_{green} = T_{min} + (T_{max} - T_{min}) \cdot \frac{Q_{phase}}{Q_{total}}
$$

where:
- $T_{green}$ = green time for current phase (seconds)
- $T_{min}$ = minimum green time = 15 seconds
- $T_{max}$ = maximum green time = 90 seconds
- $Q_{phase}$ = queue length for current phase direction
- $Q_{total}$ = total queue length ($Q_{NS} + Q_{EW}$)

#### Queue Ratio

$$
r_{queue} = \frac{Q_{phase}}{Q_{total}}
$$

This ratio determines the proportional allocation of green time based on demand.

#### Phase Cycle

Each intersection cycles between two phases:
1. **North-South (NS)**: Allows north-south movement
2. **East-West (EW)**: Allows east-west movement

$$
Phase_{next} = 
\begin{cases}
EW & \text{if } Phase_{current} = NS \\
NS & \text{if } Phase_{current} = EW
\end{cases}
$$

**Yellow Time**: Fixed at 3 seconds between phase transitions.

---

### 1.3 Vehicle Dynamics and Movement

#### Speed Calculation

When a vehicle moves from position $p_i$ to $p_{i+1}$:

$$
v = \frac{d}{\Delta t}
$$

where:
- $v$ = vehicle speed (m/s)
- $d$ = distance traveled = 500 m (grid spacing)
- $\Delta t$ = time step = 1 second

#### Position Update

$$
p(t + \Delta t) = 
\begin{cases}
p_{next} & \text{if signal allows passage} \\
p(t) & \text{if stopped at signal}
\end{cases}
$$

#### Travel Time Accumulation

$$
T_{travel}(t + \Delta t) = T_{travel}(t) + \Delta t
$$

#### Delay Accumulation

Delay is accumulated when vehicle is stopped:

$$
T_{delay}(t + \Delta t) = 
\begin{cases}
T_{delay}(t) + \Delta t & \text{if } v < 1.0 \text{ m/s} \\
T_{delay}(t) & \text{otherwise}
\end{cases}
$$

---

### 1.4 Emissions Model

The CO₂ emissions model distinguishes between idle and moving states.

#### Idle Emissions

When vehicle speed $v < 1.0$ m/s (stopped or nearly stopped):

$$
E_{CO_2}(t + \Delta t) = E_{CO_2}(t) + \alpha_{idle} \cdot \Delta t
$$

where:
- $\alpha_{idle}$ = 2.31 g CO₂/s (idle emission factor)

#### Moving Emissions

When vehicle speed $v \geq 1.0$ m/s:

$$
E_{CO_2}(t + \Delta t) = E_{CO_2}(t) + \alpha_{move} \cdot v \cdot \Delta t
$$

where:
- $\alpha_{move}$ = 0.15 g CO₂/m (moving emission factor)
- $v$ = vehicle speed (m/s)

#### Total Emissions

$$
E_{total} = \sum_{i=1}^{N} E_{CO_2,i}
$$

where $N$ = total number of vehicles (2,500).

---

### 1.5 Alternative Route Generation

To distribute traffic and avoid concentration, vehicles are assigned routes from a set of alternatives.

#### Route Selection Probability

For each candidate neighbor $n$ when building alternative route:

$$
w_n = \frac{1}{d_n + 1} + \xi
$$

where:
- $d_n$ = Manhattan distance from neighbor $n$ to goal
- $\xi$ ~ $Uniform(0, 0.3)$ = random noise for variation

#### Normalized Probability

$$
P(n) = \frac{w_n}{\sum_{j} w_j}
$$

This creates routes that generally move toward the goal but with stochastic variation to generate diverse paths.

---

## 2. Performance Metrics

### 2.1 Average Travel Time

$$
\bar{T}_{travel} = \frac{1}{N_{completed}} \sum_{i=1}^{N_{completed}} T_{travel,i}
$$

where $N_{completed}$ = number of vehicles that reached their destination.

### 2.2 Average Delay

$$
\bar{T}_{delay} = \frac{1}{N_{completed}} \sum_{i=1}^{N_{completed}} T_{delay,i}
$$

### 2.3 Completion Rate

$$
CR = \frac{N_{completed}}{N_{total}} \times 100\%
$$

### 2.4 Throughput

$$
\Theta = \frac{N_{completed}}{T_{sim}} \text{ (vehicles/hour)}
$$

where $T_{sim}$ = 3 hours.

### 2.5 Queue Length Statistics

#### Average Queue Length

$$
\bar{Q} = \frac{1}{M \cdot T_{steps}} \sum_{m=1}^{M} \sum_{t=1}^{T_{steps}} Q_{m,t}
$$

where:
- $M$ = number of intersections = 25
- $T_{steps}$ = number of time steps = 10,800
- $Q_{m,t}$ = queue length at intersection $m$ at time step $t$

#### Maximum Queue Length

$$
Q_{max} = \max_{m,t} Q_{m,t}
$$

### 2.6 Emissions per Vehicle

$$
e_{avg} = \frac{E_{total}}{N_{total}} \text{ (g CO}_2\text{/vehicle)}
$$

---

## 3. Traffic Signal Strategies

### 3.1 Fixed-Time Control

Traditional signal control with equal green time allocation:

$$
T_{green,NS} = T_{green,EW} = \frac{T_{cycle} - 2 \cdot T_{yellow}}{2}
$$

For this scenario:
- Cycle time: Variable (60-180 seconds typical)
- Green time: Fixed at minimum (15 seconds) to maximum (90 seconds)
- No adaptation to traffic conditions

### 3.2 Adaptive Control

Queue-responsive signal control:

$$
T_{green,phase} = f(Q_{phase}, Q_{total})
$$

where $f$ is the adaptive green time function defined in Section 1.2.

#### Adaptation Benefits

1. **Queue Balance**: Longer green times for heavier traffic directions
2. **Dynamic Response**: Adjusts to changing traffic patterns
3. **Efficiency**: Reduces overall delay by prioritizing high-demand phases

---

## 4. Network Structure

### 4.1 Grid Topology

The network is represented as a graph $G = (V, E)$ where:

$$
V = \{(i, j) : 0 \leq i, j < 5\}
$$

$$
E = \{((i,j), (i',j')) : |i-i'| + |j-j'| = 1\}
$$

Total intersections: $|V| = 25$
Total links: $|E| = 40$ (bidirectional)

### 4.2 Intersection Coordinates

Each intersection $(i, j)$ has physical coordinates:

$$
(x, y) = (i \cdot 1000, j \cdot 1000) \text{ meters}
$$

---

## 5. Simulation Algorithm

### Pseudocode

```
INITIALIZE:
    Create 5×5 network with 25 traffic signals
    Generate 2,500 vehicles with random OD pairs
    Assign routes to vehicles (A* shortest path + alternatives)
    
FOR t = 0 TO 10,800 SECONDS (STEP 1 second):
    
    // Update Traffic Signals
    FOR each intersection m:
        Count vehicles in NS and EW directions
        IF adaptive_mode:
            Calculate green_time based on queue ratio
        ELSE:
            Use fixed green_time
        Update signal phase if green_time elapsed
    
    // Move Vehicles
    FOR each vehicle v:
        IF v.completed:
            CONTINUE
        
        IF v.position == v.destination:
            Mark v as completed
            CONTINUE
        
        Get next_position from v.route
        signal = get_signal(v.position)
        
        IF signal.can_pass(v.position, next_position):
            Move v to next_position
            Update v.speed, distance, travel_time
        ELSE:
            Keep v at current position (stopped)
            Update v.delay, emissions (idle)
        
        Calculate v.emissions based on speed
    
    // Collect Metrics
    Record queue lengths at all intersections
    Record average travel time of completed vehicles
    Record total emissions
    
END FOR

GENERATE REPORT:
    Calculate average metrics
    Compare strategies (if running comparison)
```

---

## 6. Key Assumptions

1. **Vehicle Behavior**:
   - Vehicles follow assigned routes without dynamic rerouting
   - No lane-changing or overtaking behavior
   - Instantaneous acceleration/deceleration

2. **Signal Timing**:
   - Yellow time fixed at 3 seconds
   - No all-red clearance interval
   - Phase changes occur instantaneously

3. **Network**:
   - Uniform grid spacing (1 km)
   - No turn restrictions
   - Unlimited link capacity (no gridlock modeling)

4. **Emissions**:
   - Simplified two-state model (idle vs. moving)
   - No acceleration/deceleration penalties
   - Constant emission factors

5. **Demand**:
   - Uniform spatial distribution of OD pairs
   - All vehicles enter network at t=0
   - No time-varying demand

---

## 7. Validation Criteria

### Expected Outcomes (Adaptive vs. Fixed Signals)

| Metric | Expected Change with Adaptive Control |
|--------|--------------------------------------|
| Average Travel Time | ↓ 15-25% reduction |
| Average Delay | ↓ 20-35% reduction |
| Total Emissions | ↓ 10-20% reduction |
| Throughput | ↑ 10-15% increase |
| Max Queue Length | ↓ 25-40% reduction |
| Completion Rate | ↑ Higher completion rate |

### Validation Checks

1. **Travel Time Consistency**: $\bar{T}_{travel} \geq \bar{T}_{free-flow}$
2. **Delay Logic**: $\bar{T}_{delay} \leq \bar{T}_{travel}$
3. **Emissions Positivity**: $E_{total} > 0$
4. **Queue Bounds**: $0 \leq Q_{m,t} \leq N_{total}$
5. **Speed Limit**: $v \leq 13.9$ m/s for all vehicles
6. **Conservation**: $N_{completed} + N_{in-network} = N_{total}$

---

## 8. Implementation Notes

### 8.1 Data Structures

- **Priority Queue**: Used in A* for efficient node selection (heapq)
- **Dictionary**: Maps intersection positions to signal objects
- **Lists**: Store vehicle objects and time-series metrics

### 8.2 Computational Complexity

- **A* Pathfinding**: $O(|E| \log |V|)$ per route = $O(40 \log 25)$ ≈ 56 operations
- **Signal Update**: $O(M)$ = $O(25)$ per time step
- **Vehicle Movement**: $O(N)$ = $O(2500)$ per time step
- **Total per Step**: $O(N + M)$ ≈ 2,525 operations
- **Full Simulation**: $O(T \cdot (N + M))$ = $O(10,800 \times 2,525)$ ≈ 27M operations

### 8.3 Performance Optimization

1. **Early Termination**: Stop when all vehicles completed
2. **Vectorization**: Use NumPy for batch calculations where possible
3. **Caching**: Precompute routes at initialization
4. **Sparse Updates**: Only update active vehicles and signals

---

## 9. Extensions and Future Work

1. **Dynamic Rerouting**: Allow vehicles to adapt routes based on real-time traffic
2. **Multi-Class Traffic**: Different vehicle types (cars, buses, trucks)
3. **Incident Modeling**: Random breakdowns or accidents
4. **Public Transit**: Add dedicated bus lanes and routes
5. **Parking**: Include parking search and dwell times
6. **Realistic Acceleration**: Model gradual speed changes
7. **Network Optimization**: Find optimal signal timing plans offline
8. **Machine Learning**: Use RL for signal control policies

---

## 10. References and Standards

1. **Highway Capacity Manual (HCM)**: Signal timing and capacity analysis
2. **IEEE Standards**: Traffic simulation best practices
3. **A* Algorithm**: Hart, P. E., Nilsson, N. J., & Raphael, B. (1968)
4. **Emissions**: COPERT emission factors (simplified)
5. **Signal Control**: Webster's method for optimal cycle length

---

## Conclusion

This scenario provides a comprehensive test of traffic management strategies in an urban environment. The adaptive signal control algorithm demonstrates how real-time optimization can significantly improve network performance compared to traditional fixed-time control.

The mathematical models capture essential traffic phenomena including route choice, signal timing, vehicle dynamics, and environmental impacts. The A* pathfinding ensures optimal routes, while the queue-based adaptive control balances traffic flows across the network.

Performance metrics enable quantitative comparison of strategies, providing evidence for the benefits of intelligent transportation systems in reducing congestion, travel times, and emissions in urban areas.
