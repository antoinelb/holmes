# GR4J Model

## Overview

GR4J (Génie Rural à 4 paramètres Journalier) is a daily lumped rainfall-runoff model developed by IRSTEA (formerly Cemagref) in France. The name translates to "Rural Engineering with 4 Daily Parameters," reflecting both its origins in French agricultural water management and its parsimonious design.

GR4J has become one of the most widely used conceptual hydrological models worldwide, appearing in hundreds of research publications and operational forecasting systems. Its popularity stems from a careful balance: it is simple enough to calibrate reliably with limited data, yet complex enough to capture the essential dynamics of catchment hydrology. With only four parameters, GR4J avoids the overparameterization problems that plague more complex models while still achieving strong predictive performance across diverse climatic and physiographic conditions.

The model represents a catchment as two interconnected reservoirs: a production store that handles soil moisture accounting and a routing store that controls baseflow generation. Water moves through the system via two parallel pathways with different response times, allowing the model to reproduce both the quick response to rainfall events and the slower baseflow recession.

## Key Concepts

- **Lumped model**: Treats the entire catchment as a single unit without spatial discretization. All processes are averaged over the catchment area.

- **Conceptual approach**: Uses reservoirs and transfer functions to represent physical processes rather than solving the underlying physics directly. This trades some physical realism for practical applicability.

- **Production store**: The upper reservoir that partitions incoming water between storage, evaporation, and percolation. Think of it as representing the soil's capacity to absorb and hold water.

- **Routing store**: The lower reservoir that generates baseflow and receives water from the production store. Represents the slower groundwater component of streamflow.

- **Unit hydrographs**: Mathematical functions that distribute flow in time, representing the delay between water entering the system and appearing at the outlet. GR4J uses two unit hydrographs with different lengths.

- **Groundwater exchange**: A term allowing water to enter or leave the modeled system, representing interactions with deep aquifers or neighboring catchments that cannot be directly measured.

## How It Works

GR4J operates on a daily time step, processing precipitation and potential evapotranspiration to produce streamflow. The model structure can be understood as a series of water transformations:

**Step 1: Net inputs**. The model first determines whether the day is wet (precipitation exceeds PET) or dry (PET exceeds precipitation). This determines whether water enters or leaves the production store.

**Step 2: Production store dynamics**. During wet periods, precipitation fills the production store following a saturation curve—a nearly empty store accepts water readily, while a nearly full store accepts little. During dry periods, evaporation depletes the store following a similar nonlinear relationship. Water that cannot enter the store becomes available for routing.

**Step 3: Percolation**. A fraction of water in the production store percolates downward regardless of conditions. This percolation increases nonlinearly as the store fills, representing gravity-driven drainage.

**Step 4: Flow partitioning**. Water available for routing (surface excess plus percolation) splits between two pathways: 90% follows a slower route through the routing store, while 10% takes a faster direct path.

**Step 5: Unit hydrograph convolution**. Each pathway's water is delayed by a unit hydrograph that spreads the response over multiple days. The slow pathway uses a longer hydrograph (up to $X_4$ days), while the fast pathway uses a shorter one (up to $2X_4$ days, but quicker peak).

**Step 6: Routing store and exchange**. Water from the slow pathway enters the routing store, which generates outflow following a power-law relationship. Simultaneously, groundwater exchange adds or removes water from the system.

**Step 7: Total streamflow**. The model sums outflow from the routing store and the direct pathway to produce total streamflow.

## Parameters

GR4J has exactly four parameters that must be calibrated:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ | Production store capacity | 10–1500 | mm | Maximum soil water storage. Larger values indicate greater soil depth or water-holding capacity. |
| $X_2$ | Groundwater exchange coefficient | -5 to 3 | mm/day | Water exchange with deep aquifers. Negative values indicate losses; positive indicates gains. |
| $X_3$ | Routing store capacity | 10–400 | mm | Size of the baseflow reservoir. Controls the volume of slow-release storage. |
| $X_4$ | Unit hydrograph time base | 0.8–10 | days | Characteristic response time. Controls how quickly the catchment responds to rainfall. |

**Practical guidance on parameters:**

- **$X_1$** typically ranges from 100–500 mm for most catchments. Very large values (>1000 mm) may indicate model identifiability problems.
- **$X_2$** is often negative (water loss to deep aquifers is common). Values near zero suggest a closed water balance.
- **$X_3$** interacts with $X_4$ in controlling recession behavior. Larger $X_3$ produces more sustained baseflow.
- **$X_4$** reflects catchment size and slope. Smaller, steeper catchments have lower $X_4$; larger, flatter catchments have higher values.

## Mathematical Formulation

### Initialization

The stores are initialized at half capacity:

$$S_0 = \frac{X_1}{2}, \quad R_0 = \frac{X_3}{2}$$

where $S$ is the production store level and $R$ is the routing store level.

### Net Precipitation and Evapotranspiration

Given precipitation $P$ and potential evapotranspiration $E$:

$$P_n = \max(P - E, 0)$$

$$E_n = \max(E - P, 0)$$

where $P_n$ is net precipitation (when $P > E$) and $E_n$ is net evapotranspiration (when $E > P$).

### Production Store

**Filling (wet conditions, $P_n > 0$):**

The fraction of net precipitation entering the store follows a saturation function:

$$P_s = \frac{X_1 \left(1 - \left(\frac{S}{X_1}\right)^2\right) \tanh\left(\frac{P_n}{X_1}\right)}{1 + \frac{S}{X_1} \tanh\left(\frac{P_n}{X_1}\right)}$$

The store is then updated: $S \leftarrow S + P_s$

**Emptying (dry conditions, $E_n > 0$):**

Actual evaporation from the store:

$$E_s = \frac{S \left(2 - \frac{S}{X_1}\right) \tanh\left(\frac{E_n}{X_1}\right)}{1 + \left(1 - \frac{S}{X_1}\right) \tanh\left(\frac{E_n}{X_1}\right)}$$

The store is then updated: $S \leftarrow S - E_s$

**Percolation:**

Water percolates from the production store regardless of wet/dry conditions:

$$\text{Perc} = S \left(1 - \left(1 + \left(\frac{4S}{9X_1}\right)^4\right)^{-0.25}\right)$$

The store is updated: $S \leftarrow S - \text{Perc}$

**Routing precipitation:**

Water available for routing combines surface excess and percolation:

$$P_r = P_n - P_s + \text{Perc}$$

(In dry conditions, $P_n = P_s = 0$, so $P_r = \text{Perc}$)

### Unit Hydrographs

GR4J uses two unit hydrographs to distribute flow in time. Both are based on S-curves (cumulative distributions):

**UH1 (for 90% of flow, slower pathway):**

$$SH_1(t) = \begin{cases}
0 & t = 0 \\
\left(\frac{t}{X_4}\right)^{2.5} & 0 < t < X_4 \\
1 & t \geq X_4
\end{cases}$$

**UH2 (for 10% of flow, faster pathway):**

$$SH_2(t) = \begin{cases}
0 & t = 0 \\
\frac{1}{2}\left(\frac{t}{X_4}\right)^{2.5} & 0 < t < X_4 \\
1 - \frac{1}{2}\left(2 - \frac{t}{X_4}\right)^{2.5} & X_4 \leq t < 2X_4 \\
1 & t \geq 2X_4
\end{cases}$$

The unit hydrograph ordinates are computed as:

$$UH_1(j) = SH_1(j) - SH_1(j-1), \quad j = 1, 2, \ldots, \lceil X_4 \rceil$$

$$UH_2(j) = SH_2(j) - SH_2(j-1), \quad j = 1, 2, \ldots, \lceil 2X_4 \rceil$$

The routed flows are computed by convolution:

$$Q_9(t) = 0.9 \sum_{j=1}^{\lceil X_4 \rceil} UH_1(j) \cdot P_r(t-j+1)$$

$$Q_1(t) = 0.1 \sum_{j=1}^{\lceil 2X_4 \rceil} UH_2(j) \cdot P_r(t-j+1)$$

### Groundwater Exchange

The exchange term depends on the routing store level:

$$F = X_2 \left(\frac{R}{X_3}\right)^{3.5}$$

A positive $X_2$ adds water to the system; negative $X_2$ removes water.

### Routing Store

The routing store receives water from UH1 and exchanges with groundwater:

$$R \leftarrow \max(R + Q_9 + F, 0)$$

Outflow from the routing store follows a power relationship:

$$Q_r = R \left(1 - \left(1 + \left(\frac{R}{X_3}\right)^4\right)^{-0.25}\right)$$

The store is then depleted: $R \leftarrow R - Q_r$

### Direct Flow

The direct pathway also receives the groundwater exchange:

$$Q_d = \max(Q_1 + F, 0)$$

### Total Streamflow

$$Q = Q_r + Q_d$$

## References

Perrin, C., Michel, C., & Andréassian, V. (2003). Improvement of a parsimonious model for streamflow simulation. *Journal of Hydrology*, 279(1-4), 275-289. [https://doi.org/10.1016/S0022-1694(03)00225-7](https://doi.org/10.1016/S0022-1694(03)00225-7)
