# HYMOD Model

## Overview

HYMOD is a six-parameter daily lumped rainfall-runoff model introduced by Boyle (2000) and popularized for multi-criteria calibration studies by Wagener et al. (2001).
It sits in the same parsimony class as GR4J and the bucket model, but distinguishes itself with a spatially-distributed soil moisture accounting scheme borrowed from Moore (1985).

The defining feature of HYMOD is its **Pareto-distributed soil moisture store**.
Instead of treating the catchment as a single uniform bucket that either overflows or does not, HYMOD assumes that different parts of the catchment have different storage capacities drawn from a Pareto distribution.
This means that as the catchment wets up, more and more cells saturate progressively, generating runoff through the variable-source-area mechanism observed in real basins — a concept the Xinanjiang and VIC models share.

Runoff from the soil store is then split between a **fast flow** path (three linear reservoirs in cascade, approximating a quick subsurface response) and a **slow flow** path (a single linear groundwater reservoir).
A short unit-hydrograph delay accounts for in-channel travel time.
Despite using only six parameters, HYMOD typically performs on par with or better than other lumped conceptual models in benchmark studies, which is why it remains a staple in sensitivity-analysis and parameter-estimation research.

## Key Concepts

- **Pareto-distributed soil store**: A variable-source-area soil moisture accounting where catchment storage capacity follows a Pareto distribution.
Parameter $C_{\max}$ ($X_1$) sets the maximum local capacity, and parameter $B_{\exp}$ ($X_2$) controls the spatial variability: $B_{\exp} = 0$ gives a uniform bucket, while larger values produce strongly skewed distributions where a small fraction of the catchment saturates quickly.

- **Saturation excess runoff**: When incoming rainfall would cause the already-saturated fraction of the catchment to overflow, the excess becomes direct runoff.
This mechanism produces non-linear rainfall–runoff response even in dry conditions, because the saturated area grows as the catchment wets up.

- **Fast/slow flow split**: Non-saturation excess water is split between a fast path and a slow path by the parameter $\alpha$ ($X_3$).
The fraction $\alpha$ enters the fast path; the fraction $(1 - \alpha)$ feeds the slow groundwater store.

- **Three linear reservoirs in cascade**: The fast path routes water through three linear reservoirs in series, each with residence time $R_q$ ($X_6$).
The cascade of three linear stores approximates a gamma-distributed travel time and produces smoother, more damped flood peaks than a single linear reservoir.

- **Linear groundwater reservoir**: Slow flow passes through a single linear store with effective residence time $R_s \cdot R_q$, producing sustained baseflow.

- **Routing delay**: The combined fast-plus-slow outflow is delayed by $X_4$ days using linear interpolation between adjacent time steps, representing channel travel time to the catchment outlet.

## How It Works

The HYMOD model processes precipitation and evapotranspiration through the following steps:

**Step 1: Compute the current saturated capacity**.
Given the current soil water $S$, the model computes the inverse of the Pareto distribution function to determine the catchment capacity $C_{\text{prev}}$ that is currently filled.
This represents the fraction of the catchment whose storage is already saturated.

**Step 2: Saturation excess runoff**.
If incoming rainfall $P$ plus $C_{\text{prev}}$ exceeds $C_{\max}$, the fraction of the catchment already saturated cannot hold the rain and the excess $U_{t1}$ becomes immediate direct runoff.
This is the classic variable-source-area mechanism: a small wet catchment produces little saturation excess, a near-saturated catchment produces a lot.

**Step 3: Soil moisture update**.
The net rainfall $P_n = P - U_{t1}$ is distributed across the Pareto store, giving a new soil water level via the inverse Pareto integral.
The increase in $S$ represents water retained in the soil; any remainder $U_{t2}$ is non-saturation excess that also leaves the soil as runoff.

**Step 4: Evapotranspiration**.
Potential evapotranspiration $E$ is removed from the soil store at the full demand rate, clamped to keep $S$ non-negative.
HYMOD does not scale ET by soil water content, so dry periods directly deplete $S$.

**Step 5: Flow splitting**.
Non-saturation excess $U_{t2}$ is split between the fast and slow paths using the parameter $\alpha$.
The fast flow $U_q = \alpha \cdot U_{t2} + U_{t1}$ collects all saturation excess plus a fraction of the normal excess; the slow flow $U_s = (1 - \alpha) \cdot U_{t2}$ enters the groundwater store.

**Step 6: Slow routing**.
The groundwater store $T$ receives $U_s$ and drains linearly at rate $T / (R_s \cdot R_q)$, producing a slow baseflow component $Q_t$.

**Step 7: Fast routing**.
The fast flow $U_q$ enters the first linear reservoir $R_1$ of a three-reservoir cascade.
Each reservoir drains at rate $R_i / R_q$, feeding the next one in sequence.
The output of the third reservoir is the fast-response streamflow component $Q_3$.

**Step 8: Delay routing**.
The sum of fast and slow components $(Q_t + Q_3)$ is delayed by $X_4$ days using linear interpolation, producing the final simulated streamflow $Q_{\text{sim}}$.

## Parameters

The HYMOD model has six calibratable parameters.
Note that this implementation follows the HOOPLA parameterization, where the reservoir parameters $R_s$ and $R_q$ are **residence times** ($Q = R / R_q$), not the classical HYMOD emptying rates ($Q = R \cdot K_q$) found in Vrugt et al. (2003) and related literature.

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ ($C_{\max}$) | Maximum soil moisture capacity | 1–1500 | mm | Upper bound of the Pareto distribution of local storage capacities. Larger values increase total catchment water holding and reduce flashiness. |
| $X_2$ ($B_{\exp}$) | Spatial variability of soil moisture capacity | 0.1–2.0 | - | Shape parameter of the Pareto distribution. Small values give a near-uniform soil store; large values concentrate most of the capacity in a small fraction of the catchment. |
| $X_3$ ($\alpha$) | Distribution factor for fast/slow flows | 0.01–0.99 | - | Fraction of non-saturation excess routed to the fast cascade. Higher values produce flashier hydrographs; lower values emphasize baseflow. |
| $X_4$ (Delay) | Unit-hydrograph delay length | 0.1–5.0 | days | Channel travel time from the catchment to the outlet. Larger values shift the entire hydrograph later. |
| $X_5$ ($R_s$) | Slow routing residence scaler | 1–1000 | - | Multiplier combined with $R_q$ to give the effective residence time of the groundwater store. Effective slow residence time is $R_s \cdot R_q$ days. |
| $X_6$ ($R_q$) | Fast routing residence time | 1–10 | days | Residence time of each of the three linear reservoirs in the fast cascade. Larger values damp flood peaks; smaller values produce sharper peaks. |

**Understanding the parameters:**

- **$X_1$ and $X_2$ together** define the soil store.
$X_1$ is the absolute ceiling of local storage; $X_2$ controls how the storage is distributed spatially.
At $X_2 = 0.1$, the soil store behaves almost like a uniform bucket of depth $X_1 / 1.1$; at $X_2 = 2$, most of the catchment has low capacity and saturates easily, but a small fraction holds much more.
- **$X_3$** is a simple flow-partitioning knob.
Since HYMOD has no physical basis for choosing $\alpha$, this parameter is usually adjusted empirically during calibration to match the recession shape.
- **$X_4$** is a pure timing parameter: it shifts the hydrograph without changing its amplitude or shape.
- **$X_5$ and $X_6$** together control the slow component.
The effective slow residence time is $X_5 \cdot X_6$ days, so a large $X_5$ gives long baseflow recessions (weeks to years).
- **$X_6$ alone** controls the fast cascade.
With three reservoirs in series, the peak of the fast response is delayed and smoothed — a single spike of input produces a gamma-shaped output with mean delay $3 \cdot X_6$ days.

## Mathematical Formulation

### Initialization

Initial store levels:

$$S_0 = \min\left(0.2 \cdot X_1, \frac{X_1}{X_2 + 1}\right), \quad R_1^{(0)} = R_2^{(0)} = R_3^{(0)} = 1, \quad T_0 = 300$$

where $S$ is the soil water content, $R_1, R_2, R_3$ are the three fast reservoirs, and $T$ is the groundwater store.
The soil initialization is clamped to $X_1 / (X_2 + 1)$ to preserve the Pareto invariant $S \leq X_1 / (X_2 + 1)$, which is required for the inverse Pareto formula to stay real-valued.

### Pareto Soil Moisture Store

The Pareto distribution of local storage capacities is characterized by the cumulative fraction of the catchment with capacity less than $c$:

$$F(c) = 1 - \left(1 - \frac{c}{X_1}\right)^{X_2}$$

At any moment, the soil water $S$ corresponds to a "current capacity" $C_{\text{prev}}$ given by the inverse of the distribution:

$$C_{\text{prev}} = X_1 \cdot \left(1 - \left(1 - \frac{(X_2 + 1) \cdot S}{X_1}\right)^{1 / (X_2 + 1)}\right)$$

Incoming rainfall $P$ first produces saturation excess from the already-saturated fraction:

$$U_{t1} = \max(P - X_1 + C_{\text{prev}}, 0)$$

$$P_n = P - U_{t1}$$

The new soil water after absorbing $P_n$ is obtained by integrating the Pareto density:

$$\text{Dum} = \min\left(1, \frac{C_{\text{prev}} + P_n}{X_1}\right)$$

$$S \leftarrow \frac{X_1}{X_2 + 1} \cdot \left(1 - (1 - \text{Dum})^{X_2 + 1}\right)$$

The remaining excess (net rain minus the increase in storage) is the non-saturation runoff component:

$$U_{t2} = \max(P_n - (S - S_{\text{prev}}), 0)$$

### Evapotranspiration

Potential evapotranspiration is extracted at the full atmospheric demand rate:

$$S \leftarrow \max(S - E, 0)$$

### Flow Splitting

Non-saturation excess $U_{t2}$ is distributed between the fast and slow flow paths using the fraction $X_3 = \alpha$:

$$U_q = \alpha \cdot U_{t2} + U_{t1}$$

$$U_s = (1 - \alpha) \cdot U_{t2}$$

The fast flow $U_q$ collects all of the saturation excess $U_{t1}$ (which must drain quickly) plus a fraction of the normal excess.

### Slow Groundwater Reservoir

The groundwater store receives $U_s$ and drains linearly with effective residence time $X_5 \cdot X_6$:

$$T \leftarrow T + U_s$$

$$Q_t = \frac{T}{X_5 \cdot X_6}$$

$$T \leftarrow T - Q_t$$

### Fast Reservoir Cascade

The fast path routes water through three linear reservoirs in series, each with residence time $X_6$:

$$R_1 \leftarrow R_1 + U_q, \quad Q_1 = \frac{R_1}{X_6}, \quad R_1 \leftarrow R_1 - Q_1$$

$$R_2 \leftarrow R_2 + Q_1, \quad Q_2 = \frac{R_2}{X_6}, \quad R_2 \leftarrow R_2 - Q_2$$

$$R_3 \leftarrow R_3 + Q_2, \quad Q_3 = \frac{R_3}{X_6}, \quad R_3 \leftarrow R_3 - Q_3$$

The convolution of three identical linear reservoirs approximates a gamma distribution, producing an S-shaped unit response with peak delay of roughly $2 \cdot X_6$ days and total memory of about $5 \cdot X_6$ days.

### Delay Routing

The sum of fast and slow components $(Q_t + Q_3)$ is delayed by $X_4$ days using linear interpolation.
The model maintains a delay array of size $\lceil X_4 \rceil + 1$ with weights:

$$d_{\lceil X_4 \rceil - 1} = \frac{1}{X_4 - \lceil X_4 \rceil + 3}, \quad d_{\lceil X_4 \rceil} = 1 - d_{\lceil X_4 \rceil - 1}$$

The simulated streamflow is obtained by convolving the system output with this delay array:

$$Q_{\text{sim}}(t) = \text{delayed}(Q_t + Q_3, X_4)$$

## References

Boyle, D. P. (2000).
*Multicriteria Calibration of Hydrological Models*.
PhD dissertation, Department of Hydrology and Water Resources, University of Arizona, Tucson, USA.

Moore, R. J. (1985).
The probability-distributed principle and runoff production at point and basin scales.
*Hydrological Sciences Journal*, 30(2), 273–297.

Wagener, T., Boyle, D. P., Lees, M. J., Wheater, H. S., Gupta, H. V., & Sorooshian, S. (2001).
A framework for development and application of hydrological models.
*Hydrology and Earth System Sciences*, 5(1), 13–26.

Vrugt, J. A., Gupta, H. V., Bouten, W., & Sorooshian, S. (2003).
A Shuffled Complex Evolution Metropolis algorithm for optimization and uncertainty assessment of hydrologic model parameters.
*Water Resources Research*, 39(8), 1201.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
