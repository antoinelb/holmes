# PDM Model

## Overview

PDM (Probability-Distributed Model) is an eight-parameter daily lumped rainfall-runoff model originally developed by Moore and Clarke (1981) at the Institute of Hydrology, Wallingford, UK.
It is one of the most widely used conceptual models in British operational hydrology, and its core idea — Pareto-distributed soil moisture capacity — was later adopted by HYMOD, Xinanjiang, and VIC.

The HOLMES implementation follows the modified eight-parameter version from HOOPLA (HM13), which extends Perrin's six-parameter PDM0 with a rainfall correction factor ($X_7$) and a threshold-gated drainage mechanism controlled by $X_3$ and $X_8$.
Structurally, the model represents a catchment as four interacting reservoirs: a Pareto soil store, a cubic groundwater store, and two linear fast-routing reservoirs in series, connected by a fractional-delay unit hydrograph.

PDM is a natural choice when the analyst wants an explicit representation of spatially variable soil moisture capacity without committing to a fully distributed model.
Its cubic groundwater store also provides a nonlinear baseflow recession that many simpler linear models cannot reproduce.

## Key Concepts

- **Pareto-distributed soil store**: The catchment is modelled as an ensemble of soil columns whose maximum capacities follow a Pareto distribution.
Parameter $C_{\max}$ ($X_1$) sets the largest capacity, and parameter $b$ ($X_2$) controls spatial variability: low $b$ gives a near-uniform store, high $b$ means a small fraction of the catchment saturates quickly.

- **Saturation excess**: When rainfall lands on parts of the catchment that are already full, it cannot infiltrate and immediately becomes surface runoff ($U_{t1}$).

- **Infiltration excess**: Even for parts of the catchment that are not fully saturated, the net rainfall may exceed the increase in soil storage, producing additional runoff ($U_{t2}$).

- **Threshold drainage**: Subsurface drainage from the soil store only occurs when $S$ exceeds a fraction $\alpha$ ($X_3$) of the maximum soil storage, at a rate controlled by the drainage time constant $X_8$.

- **Cubic groundwater reservoir**: A nonlinear store where the outflow depends on the cube of the stored volume relative to a characteristic storage $X_5$, producing a concave recession curve that better matches observed baseflow behaviour.

- **Two-stage linear cascade**: Surface runoff passes through two linear reservoirs in series (both with residence time $X_6$), producing a smoothed and delayed fast-flow response.

- **Fractional-delay routing**: The combined fast-plus-slow outflow is delayed by $X_4$ days using linear interpolation, representing in-channel travel time to the catchment outlet.

- **Rainfall correction factor**: The raw precipitation is multiplied by $X_7$ before entering the model, allowing correction for gauge undercatch or spatial representativeness.

## How It Works

The PDM model processes precipitation and potential evapotranspiration through the following steps:

**Step 1: Rainfall correction**.
Raw precipitation is multiplied by $X_7$ to obtain effective precipitation $P_1 = P \cdot X_7$.
This corrects for systematic gauge bias and spatial under-sampling.

**Step 2: Saturation excess**.
The model computes the equivalent uniform depth currently filled using the inverse Pareto distribution, then determines which fraction of the catchment is already saturated.
Any rainfall exceeding the remaining capacity on the saturated fraction becomes saturation excess $U_{t1}$, which exits the soil store immediately.

**Step 3: Soil moisture update**.
The net rainfall $P_n = P_1 - U_{t1}$ is distributed across the Pareto store using the forward Pareto integral, updating the soil water $S$.
Any net rain that did not fit into the store (because the soil absorbed less than $P_n$) becomes infiltration excess $U_{t2}$.

**Step 4: Evapotranspiration**.
PET is scaled by a nonlinear function of the current soil filling: $\text{factor} = 1 - (1 - \text{fill})^2$, where $\text{fill} = S / X_1 \cdot (X_2 + 1)$.
This means evapotranspiration is highest when the soil is wet and reduces quadratically as it dries.

**Step 5: Threshold drainage**.
If the soil water $S$ exceeds the threshold $\alpha \cdot S_{\max}$ (where $S_{\max} = X_1 / (X_2 + 1)$), the excess drains to the groundwater store at rate $(S - \text{threshold}) / X_8$.
When $S$ is below the threshold, no drainage occurs — the soil retains all its water.

**Step 6: Fast routing**.
Surface runoff $U_q = U_{t1} + U_{t2}$ enters a cascade of two linear reservoirs (M and N), each draining at rate $1/X_6$ per time step.
The two reservoirs in series smooth the fast response, producing a damped hydrograph peak.

**Step 7: Slow routing**.
The drainage from Step 5 enters the cubic groundwater store $T$, which releases water as $Q_t = T \cdot (1 - (1 + (T/X_5)^2)^{-1/2})$.
This nonlinear formula produces large outflows when the store is full but vanishingly small outflows during dry periods.

**Step 8: Delay routing**.
The sum of fast and slow components $(Q_t + Q_3)$ is convolved with a fractional-delay unit hydrograph of length $\lceil X_4 \rceil + 1$, producing the final simulated streamflow.

## Parameters

The PDM model has eight calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ ($C_{\max}$) | Maximum soil moisture capacity | 10–2000 | mm | Upper bound of the Pareto distribution of local storage capacities. Larger values increase total water holding and reduce flashiness. |
| $X_2$ ($b$) | Spatial variability of soil moisture capacity | 0.01–2.0 | - | Shape parameter of the Pareto distribution. Low values give a uniform bucket; high values concentrate capacity in a small fraction of the catchment. |
| $X_3$ ($\alpha$) | Drainage threshold fraction | 0.01–0.99 | - | Fraction of maximum soil storage that must be filled before drainage to groundwater begins. High values suppress drainage except during wet periods. |
| $X_4$ (Delay) | Routing delay | 0.5–5.0 | days | Channel travel time to the catchment outlet. Shifts the entire hydrograph without changing its shape. |
| $X_5$ ($S_c$) | Cubic ground reservoir characteristic storage | 1–2000 | mm | Scale parameter of the nonlinear groundwater store. Larger values slow baseflow recession and increase the volume held in the subsurface. |
| $X_6$ ($\tau_q$) | Linear routing emptying constant | 1–30 | days | Residence time of each of the two fast linear reservoirs. Controls the width and damping of the fast-flow peak. |
| $X_7$ ($P_{\text{corr}}$) | Rainfall correction factor | 0.5–1.5 | - | Multiplicative scaling of raw precipitation. Values below 1.0 reduce effective rainfall; values above 1.0 increase it. |
| $X_8$ ($\tau_d$) | Drainage time constant | 1–100 | days | Controls how quickly soil water above the threshold drains to the groundwater store. Small values give rapid drainage; large values make drainage sluggish. |

**Understanding the parameters:**

- **$X_1$ and $X_2$ together** define the soil store, exactly as in HYMOD. $X_1$ sets the ceiling; $X_2$ determines whether all cells saturate at similar depths ($X_2 \approx 0$) or whether a few cells saturate very early while others hold much more ($X_2 \approx 2$).
- **$X_3$ and $X_8$ together** control the threshold drainage mechanism. $X_3$ determines when drainage begins (how wet the soil must be), and $X_8$ determines how fast it proceeds once the threshold is crossed. A high $X_3$ with a large $X_8$ gives very little baseflow recharge; a low $X_3$ with a small $X_8$ feeds the groundwater store aggressively.
- **$X_5$** governs the nonlinearity of baseflow recession. When the groundwater store $T$ is small relative to $X_5$, outflow is nearly cubic ($\propto T^3$); when $T \gg X_5$, outflow approaches $T$ (linear). In practice, $X_5$ should be calibrated to match the shape of observed baseflow recessions.
- **$X_6$** affects peak timing and attenuation of the fast flow. With two reservoirs in series, the cascade acts as a gamma filter with mean delay $2 \cdot X_6$.
- **$X_7$** is useful when the rain gauge network under-represents the catchment, or when there is a known elevation bias.

## Mathematical Formulation

### Initialization

$$S_0 = \min\left(0.2 \cdot X_1, \frac{X_1}{X_2 + 1}\right), \quad T_0 = 20, \quad M_0 = 30, \quad N_0 = 30$$

where $S$ is the soil water, $T$ the groundwater store, and $M, N$ the two fast-routing reservoirs.
The soil initialization is clamped to $X_1 / (X_2 + 1)$ to preserve the Pareto invariant required for the inverse formula to remain real-valued.

### Pareto Soil Moisture Store

The inverse Pareto formula gives the equivalent capacity currently filled:

$$C_{\text{prev}} = X_1 \cdot \left(1 - \max\left(1 - \frac{(X_2 + 1) \cdot S}{X_1},\, 0\right)^{1/(X_2 + 1)}\right)$$

Saturation excess from rainfall $P_1 = P \cdot X_7$:

$$U_{t1} = \max(P_1 - X_1 + C_{\text{prev}},\, 0)$$

$$P_n = P_1 - U_{t1}$$

Forward Pareto update:

$$\text{Dum} = \min\left(1, \frac{C_{\text{prev}} + P_n}{X_1}\right)$$

$$S \leftarrow \frac{X_1}{X_2 + 1} \cdot \left(1 - (1 - \text{Dum})^{X_2 + 1}\right)$$

Infiltration excess:

$$U_{t2} = \max(P_n - (S - S_{\text{prev}}),\, 0)$$

### Evapotranspiration

Evapotranspiration is scaled by the current soil filling fraction using a quadratic reduction:

$$\text{fill} = \frac{S}{X_1} \cdot (X_2 + 1)$$

$$\text{factor} = 1 - (1 - \text{fill})^2$$

$$S \leftarrow \max(S - E \cdot \text{factor},\, 0)$$

### Threshold Drainage

Drainage occurs only when the soil exceeds a fraction $X_3$ of the maximum storage:

$$\text{threshold} = \frac{X_1}{X_2 + 1} \cdot X_3$$

$$D = \begin{cases} \frac{S - \text{threshold}}{X_8} & \text{if } S > \text{threshold} \\ 0 & \text{otherwise} \end{cases}$$

$$S \leftarrow S - D$$

### Fast Routing: Two-Stage Linear Cascade

Surface runoff $U_q = U_{t1} + U_{t2}$ enters two linear reservoirs in series:

$$M \leftarrow M + U_q, \quad Q_1 = \frac{M}{X_6}, \quad M \leftarrow M - Q_1$$

$$N \leftarrow N + Q_1, \quad Q_2 = \frac{N}{X_6}, \quad N \leftarrow N - Q_2$$

### Slow Routing: Cubic Ground Reservoir

The groundwater store $T$ receives drainage $D$ and releases water nonlinearly:

$$T \leftarrow T + D$$

$$Q_t = T \cdot \left(1 - \left(1 + \left(\frac{T}{X_5}\right)^2\right)^{-1/2}\right)$$

$$T \leftarrow T - Q_t$$

This formula produces near-cubic behaviour for $T \ll X_5$ and near-linear behaviour for $T \gg X_5$.

### Delay Routing

The combined outflow $(Q_t + Q_2)$ is convolved with a fractional unit hydrograph of length $k = \lceil X_4 \rceil + 1$:

$$d_{k-2} = \frac{1}{X_4 - k + 3}, \quad d_{k-1} = 1 - d_{k-2}$$

$$Q_{\text{sim}}(t) = \max\left(\text{delayed}(Q_t + Q_2, X_4),\, 0\right)$$

## References

Moore, R. J., & Clarke, R. T. (1981).
A distribution function approach to rainfall runoff modeling.
*Water Resources Research*, 17(5), 1367–1382.

Moore, R. J. (1985).
The probability-distributed principle and runoff production at point and basin scales.
*Hydrological Sciences Journal*, 30(2), 273–297.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis).
INPG, Grenoble.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
