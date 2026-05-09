# MOHYSE Model

## Overview

MOHYSE (MOdèle HYdrologique Simplifié à l'Extrême) is a daily lumped rainfall-runoff model developed by Fortin and Turcotte at Université Laval, Canada (2007).
The name translates to "Hydrological Model Simplified to the Extreme," reflecting its design philosophy: capture the essential processes of catchment hydrology with the fewest possible structural components.

The model represents a catchment using just two reservoirs (soil and groundwater) connected by linear drainage pathways, with a gamma-shaped unit hydrograph to distribute flow in time.
With seven parameters and a fully linear structure (no power-law outflows, no nonlinear soil dynamics), MOHYSE is one of the simplest models in the HOLMES collection.
This makes it an excellent pedagogical starting point for understanding how production, routing, and convolution interact in a conceptual model.

Despite its simplicity, MOHYSE provides a good benchmark for comparing more complex model structures.
When a more complex model fails to outperform MOHYSE, it suggests that the additional structural complexity is not justified by the data.

## Key Concepts

- **Interception**: Direct evaporation of a fraction of rainfall before it reaches the soil surface. MOHYSE intercepts exactly $\min(P, E)$ — rainfall up to the atmospheric demand — removing it before any other process.

- **Capacity-limited infiltration**: Water enters the soil store at a rate that decreases linearly as the store fills toward its maximum capacity $X_2$. When the soil is saturated, all net rainfall becomes surface runoff.

- **Transpiration**: Evapotranspiration drawn from the soil store, controlled by the coefficient $X_1$. The actual transpiration rate is limited by both the available soil moisture and the residual atmospheric demand after interception.

- **Vadose zone drainage**: Gravity-driven flow from the unsaturated soil through two parallel pathways: one draining directly to the river ($X_4$) and another percolating to the groundwater reservoir ($X_3$).

- **Groundwater baseflow**: Slow discharge from the groundwater reservoir to the river, controlled by the emptying coefficient $X_5$. Represents the sustained flow component that persists between rainfall events.

- **Gamma unit hydrograph**: A bell-shaped transfer function defined by a shape parameter ($X_6$) and a scale parameter ($X_7$) that spreads the total flow over multiple time steps. Unlike simpler triangular or rectangular unit hydrographs, the gamma distribution allows flexible control over both the peak timing and the tail length.

## How It Works

**Step 1: Interception**.
Rainfall first passes through an interception layer where an amount equal to $\min(P, E)$ evaporates directly.
This represents canopy interception and surface evaporation.
The remaining rainfall $(P - E_d)$ is available for infiltration and runoff, while the remaining atmospheric demand $(E - E_d)$ can drive transpiration from the soil.

**Step 2: Infiltration and surface runoff**.
Net rainfall infiltrates into the soil store at a rate proportional to the remaining storage capacity: $I = (P - E_d) \cdot (1 - S / X_2)$.
When the soil is nearly empty, almost all water infiltrates; when it approaches capacity $X_2$, most becomes surface runoff $Q_1 = P - E_d - I$.

**Step 3: Transpiration**.
The atmosphere draws water from the soil at a rate proportional to the soil moisture content, modulated by coefficient $X_1$.
Transpiration is limited to the lesser of $X_1 \cdot S$ and the residual PET after interception, ensuring the soil cannot supply more water than it holds or the atmosphere demands.

**Step 4: Subsurface drainage**.
Two linear drainage pathways empty the soil store in parallel.
A fraction $X_4 \cdot S$ drains directly to the river (representing shallow interflow), while $X_3 \cdot S$ percolates to the groundwater reservoir (representing deeper recharge).
Both coefficients are small (0.001 to 1.0), reflecting the relatively slow emptying of the vadose zone.

**Step 5: Groundwater baseflow**.
The groundwater reservoir releases water to the river at a rate $X_5 \cdot R$, producing the slow baseflow component.
The reservoir receives water from soil drainage and loses it only through this linear outflow.

**Step 6: Unit hydrograph routing**.
The total flow from all three pathways ($Q_1 + Q_2 + Q_3$) is routed through a gamma-shaped unit hydrograph defined by the shape ($X_6$) and scale ($X_7$) parameters.
Because all three outflows pass through the same convolution, this is equivalent (by linearity) to routing each component separately and summing the results.
The unit hydrograph memory extends 80 time steps, which is long enough to capture the full tail of the gamma distribution for any parameter combination within the calibration bounds.

## Parameters

The MOHYSE model has 7 calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ | Transpiration coefficient | 0.01–1.0 | - | Fraction of soil moisture available for transpiration per time step. Higher values allow faster soil drying. |
| $X_2$ | Maximum infiltration capacity | 1–2000 | mm | Maximum soil water storage. Controls how much water the soil can hold before saturating. |
| $X_3$ | Aquifer vadose zone emptying coefficient | 0.001–1.0 | - | Fraction of soil moisture draining to the groundwater reservoir per time step. |
| $X_4$ | River vadose zone emptying coefficient | 0.001–1.0 | - | Fraction of soil moisture draining directly to the river per time step. |
| $X_5$ | Aquifer to river emptying coefficient | 0.001–1.0 | - | Fraction of groundwater storage discharging as baseflow per time step. |
| $X_6$ | Unit hydrograph shape parameter | 1.0–5.0 | - | Shape (alpha) of the gamma distribution. Higher values shift the peak later and produce a more symmetric shape. |
| $X_7$ | Unit hydrograph scale parameter | 0.5–5.0 | - | Scale (beta) of the gamma distribution. Higher values spread the response over more time steps. |

**Understanding the parameters:**

- **$X_1$** and **$X_2$** together govern the production phase. A large $X_2$ (deep soil) delays saturation, while a large $X_1$ (fast transpiration) accelerates drying between events. Start calibration by adjusting $X_2$ to match the overall water balance, then refine $X_1$ to match recession in dry periods.
- **$X_3$**, **$X_4$**, and **$X_5$** control flow partitioning. Increasing $X_4$ relative to $X_3$ sends more water directly to the river (flashier response); increasing $X_3$ while keeping $X_5$ small produces a slower, more groundwater-dominated hydrograph. The ratio $X_4 / X_3$ is often more informative than either value alone.
- **$X_6$** and **$X_7$** shape the unit hydrograph. With $X_6 \approx 1$, the UH is exponentially decaying (peak at day 1); with $X_6 = 3\text{–}5$, the peak shifts to day 2–4 and the response becomes more bell-shaped. $X_7$ stretches or compresses the tail.
- Because all five drainage coefficients ($X_1$ through $X_5$) are fractional and linear, MOHYSE can exhibit equifinality when $X_3$ and $X_4$ trade off against each other. Fixing one of them or constraining their ratio can improve identifiability.

## Mathematical Formulation

### Initialization

Initial reservoir states follow HOOPLA HM10 defaults:

$$S_0 = 40 \text{ mm}, \quad R_0 = 30 \text{ mm}$$

where $S$ is the soil moisture store and $R$ is the groundwater store.

### Interception

Direct evaporation removes the lesser of precipitation and PET:

$$E_d = \min(P, E)$$

### Transpiration

Water drawn from the soil is limited by the soil content and the residual atmospheric demand:

$$T_r = \min(X_1 \cdot S, \; E - E_d)$$

### Infiltration

Net rainfall enters the soil at a rate that decreases linearly with saturation:

$$
I = \begin{cases}
(P - E_d) \cdot \left(1 - \dfrac{S}{X_2}\right) & \text{if } S < X_2 \\[6pt]
0 & \text{if } S \geq X_2
\end{cases}
$$

### Surface Runoff

Water that cannot infiltrate becomes surface runoff:

$$Q_1 = P - E_d - I$$

### Vadose Zone Drainage

Two parallel drainage pathways empty the soil store:

$$Q_2 = X_4 \cdot S \quad \text{(direct to river)}$$

$$Q_t = X_3 \cdot S \quad \text{(to groundwater)}$$

### Groundwater Baseflow

$$Q_3 = X_5 \cdot R$$

### State Updates

$$S \leftarrow \max(S + I - T_r - Q_t - Q_2, \; 0)$$

$$R \leftarrow \max(R + Q_t - Q_3, \; 0)$$

### Gamma Unit Hydrograph

The unit hydrograph ordinates are computed from a gamma distribution with shape $\alpha = X_6$ and scale $\beta = X_7$:

$$h(t) = \frac{t^{\alpha - 1} \cdot e^{-t/\beta}}{\displaystyle\sum_{j=1}^{k} j^{\alpha - 1} \cdot e^{-j/\beta}}, \quad t = 1, 2, \ldots, k$$

where $k = 80$ is the fixed memory length and the denominator normalizes the ordinates so they sum to 1.

### Total Streamflow

The total flow is the sum of all three pathways, routed through the unit hydrograph via shift-and-add convolution:

$$Q_{\text{total}}(t) = Q_1(t) + Q_2(t) + Q_3(t)$$

$$Q(t) = \sum_{j=1}^{k} h(j) \cdot Q_{\text{total}}(t - j + 1)$$

The output streamflow $Q(t) = \max(Q(t), 0)$ is enforced non-negative.

## References

- Fortin, V., & Turcotte, R. (2007). *Le modèle hydrologique MOHYSE*. Note de cours pour SCA7420, Département des sciences de la terre et de l'atmosphère, Université du Québec à Montréal.
- Arsenault, R., Brissette, F., Martel, J.-L., Troin, M., Lévesque, G., Davidson-Chaput, J., Gonzalez, M. C., Ameli, A., & Poulin, A. (2020). A comprehensive, multisource database for hydrometeorological modeling of 14,425 North American watersheds. *Scientific Data*, 7(1), 243. [DOI](https://doi.org/10.1038/s41597-020-00583-2)
