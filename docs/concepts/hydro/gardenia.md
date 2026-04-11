# GARDENIA Model

## Overview

GARDENIA is a six-parameter daily lumped rainfall-runoff model developed at the Bureau de Recherches Géologiques et Minières (BRGM) in Orléans, France, by Thiery (1982).
It was originally designed not as a streamflow model but as a **rainfall → piezometric-level** model for hydrogeological applications: the original version calibrated parameters on observed groundwater levels rather than discharge, and GARDENIA is still widely used today in French operational hydrogeology for aquifer monitoring and drought forecasting.

The variant implemented in HOLMES is the **GARD** six-parameter version described in Annex 1 of Perrin (2000).
It uses three reservoirs in series: a **surface reservoir** that captures the shallow interception/runoff layer, a **soil reservoir** that produces streamflow through a nonlinear quadratic outflow and simultaneously percolates water downwards, and a **groundwater reservoir** that drains linearly and represents the deep-flow / baseflow component.
A short pure delay is applied at the outlet to account for channel travel time.

What distinguishes GARDENIA from the other six-parameter HOLMES models is the **quadratic soil emptying** $Q_r = R^2 / (R + X_2 X_3)$.
This is a non-linear reservoir law that produces smoother recession curves than pure linear reservoirs when $R$ is large, and reverts to linear behavior when $R$ is small — a nice property for catchments that swing between saturated and dry conditions.
The model also exposes a **PET correction coefficient** $X_5$, which lets calibration compensate for systematic biases in the input PET series (e.g. when the Oudin PET is known to over- or underestimate ET for a particular catchment).

## Key Concepts

- **Overflow-based surface reservoir**: The uppermost reservoir $S$ has a fixed capacity $X_1$.
Any rain that causes $S$ to exceed $X_1$ is routed downward as $P_r$; the rest stays in $S$ and is available for evaporation.
This simple threshold captures interception and shallow soil storage, and is reset daily if $S$ happens to fall back below capacity due to evaporation.

- **PET correction coefficient**: Actual evapotranspiration is computed as $E_s = X_5 \cdot E$, where $E$ is the input PET and $X_5$ is a calibratable multiplier.
This is a coarse but effective way to absorb systematic PET biases during calibration: if Oudin underestimates ET for a semi-arid catchment, $X_5$ calibrates to a value above 1; if it overestimates, $X_5$ calibrates below 1.
Unlike most other HOLMES models, GARDENIA does **not** scale $E_s$ by soil moisture content — the surface store is simply capped at zero when it runs dry.

- **Quadratic soil outflow**: The soil reservoir $R$ drains via $Q_r = R^2 / (R + X_2 X_3)$, which is a smooth non-linear law.
For $R \gg X_2 X_3$ the response is linear-like with slope 1 (full discharge per unit storage); for $R \ll X_2 X_3$ it becomes quadratic with slope $R/(X_2 X_3)$.
This matches empirical behavior where large floods drain nearly proportionally while recession from low flows is much slower.

- **Linear percolation to groundwater**: In addition to the quadratic outflow, the soil reservoir percolates linearly at rate $I_r = R/X_2$, representing deep drainage into the groundwater store $T$.
Both outputs from $R$ are deducted in sequence, so percolation is computed on the post-$Q_r$ soil storage.

- **Linear groundwater baseflow**: The groundwater reservoir $T$ drains linearly at rate $Q_t = T/X_4$, producing sustained baseflow.
A long residence time ($X_4$ large) gives a slow recession that extends into dry seasons; a short one gives a flashier response.

- **Fractional delay routing**: Because the delay parameter $X_6$ is a real number (typically between 0.5 and 5 days), GARDENIA uses a **two-element fractional delay** rather than a unit hydrograph.
A size-$(\lceil X_6 \rceil + 1)$ register distributes the total flow between two adjacent time steps with weights that interpolate linearly between integer delays — e.g. $X_6 = 2.3$ puts 70% of the flow at day 2 and 30% at day 3 after generation.

## How It Works

The GARDENIA model processes precipitation and evapotranspiration through the following steps each day:

**Step 1: Surface reservoir inflow and overflow**.
Rain is added to the surface store: $S \leftarrow S + P$.
Any amount above the capacity $X_1$ overflows as $P_r = \max(0, S - X_1)$ and the store is reduced to its capacity: $S \leftarrow S - P_r$.
$P_r$ is the runoff that enters the soil reservoir.

**Step 2: Surface evaporation**.
PET is corrected by the coefficient $X_5$ and deducted from the surface store: $E_s = X_5 \cdot E$, $S \leftarrow \max(0, S - E_s)$.
The clamp at zero handles the case where the corrected PET exceeds what is currently in the surface store (a normal occurrence during dry spells).
GARDENIA does not transfer unused PET to the soil store, so evaporation is purely surface-level.

**Step 3: Soil reservoir inflow and quadratic outflow**.
The soil store receives the overflow from the surface: $R \leftarrow R + P_r$.
Streamflow generation $Q_r$ follows the quadratic law $Q_r = R^2 / (R + X_2 X_3)$ and the store is decremented: $R \leftarrow R - Q_r$.
This nonlinear form means that a full soil reservoir generates strong flow (the quadratic numerator dominates), while a near-empty store generates almost none.

**Step 4: Linear percolation**.
A linear fraction $I_r = R / X_2$ of the remaining soil water percolates to the groundwater store.
The soil is updated: $R \leftarrow R - I_r$.
Note that since $Q_r$ was subtracted first, percolation operates on the depleted soil rather than the original.

**Step 5: Groundwater reservoir**.
The groundwater store receives the percolation: $T \leftarrow T + I_r$, then drains linearly: $Q_t = T / X_4$, $T \leftarrow T - Q_t$.
$X_4$ is the linear residence time, typically long compared to $X_2$ and $X_3$ to generate sustained baseflow.

**Step 6: Delay register**.
The total instantaneous output $Q_r + Q_t$ is added to a delay register of size $\lceil X_6 \rceil + 1$.
Only the last two register positions receive non-zero weights — the one at index $\lceil X_6 \rceil - 1$ receives $1/(X_6 - \lceil X_6 \rceil + 3)$ and the one at index $\lceil X_6 \rceil$ receives the complement.
The register is then shifted by one position and its first element is returned as the simulated streamflow, clamped at zero.

## Parameters

The GARDENIA model has six calibratable parameters.

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|:-----:|-------|------------------------|
| $X_1$ (RUMAX) | Surface reservoir capacity | 1–1000 | mm | Maximum storage of the shallow surface store (interception + topsoil). Larger values absorb more rain before overflowing to the soil. |
| $X_2$ (THG) | Linear percolation constant | 1–1000 | days | Residence time controlling the rate at which soil water percolates into the groundwater store ($I_r = R / X_2$). Also appears in the denominator of the quadratic soil outflow. |
| $X_3$ (RUIPER) | Lateral emptying parameter of soil reservoir | 0.01–1000 | - | Together with $X_2$ sets the characteristic storage threshold above which soil outflow $Q_r$ transitions from quadratic to linear behavior. Calibrates the overall volume of fast runoff response. |
| $X_4$ (K1) | Linear emptying constant of groundwater reservoir | 1–500 | days | Residence time of the linear groundwater store. Larger values produce longer, smoother baseflow recessions; smaller values make baseflow more responsive. |
| $X_5$ (PETC) | PET correction coefficient | 0.1–2.0 | - | Multiplicative factor applied to the input PET series. Used during calibration to absorb systematic biases in the PET estimator (e.g. Oudin over- or underestimating ET for a given climate). |
| $X_6$ (delay) | Routing delay | 0.5–5 | days | Pure delay applied at the outlet, implemented as a two-element fractional interpolation. Shifts the hydrograph without changing its shape or amplitude. |

**Understanding the parameters:**

- **$X_1$** is the rain interception / topsoil threshold.
Think of it as how much rain the catchment can "absorb at the surface" before any runoff is generated.
It has no explicit physical match in typical operational HBV or GR4J models, but plays a similar role to $C_{\max}$ in HYMOD or $X_4$ in GR4J.
- **$X_2$ and $X_3$ together** define the quadratic soil outflow.
The effective characteristic soil storage is $X_2 \cdot X_3$; flows get volume-limited as $R$ approaches this value.
At the same time, $X_2$ alone controls the deeper percolation rate — so increasing $X_2$ slows both the soil outflow *and* the recharge to the groundwater reservoir.
- **$X_4$** is the linear groundwater residence time.
Long $X_4$ (weeks to months) gives a deep, slow aquifer with long memory; short $X_4$ (days) gives a flashy watershed with little sub-surface storage.
- **$X_5$** is the PET bias correction.
When calibrated together with everything else, it typically settles between 0.5 and 1.5, with higher values in humid catchments where Oudin underestimates plant water use and lower values in semi-arid catchments where it over-predicts.
- **$X_6$** is a pure timing knob: it does not change flood volume or recession shape, only the time at which the hydrograph appears at the outlet.

## Mathematical Formulation

### Initialization

Initial store levels:

$$S_0 = X_1, \quad R_0 = 10, \quad T_0 = 80$$

where $S$ is the surface reservoir (initialized at its capacity), $R$ is the soil reservoir, and $T$ is the groundwater reservoir.
These initial values are fixed and produce a short warm-up transient that typically dissipates within a few weeks of simulation.

The delay register is a fractional two-weight array of size $n = \lceil X_6 \rceil + 1$ with only the last two entries non-zero:

$$d_{n-2} = \frac{1}{X_6 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}$$

For example, with $X_6 = 1.5$, $n = 3$ and the weights are $d_1 = 1/1.5 \approx 0.667$ and $d_2 \approx 0.333$ — so two-thirds of the flow is delivered at a 1-day delay and one-third at a 2-day delay, exactly the fractional interpolation you would expect for a 1.5-day delay.
For $X_6 = 2.3$, $n = 4$ and the weights are $d_2 = 1/1.3 \approx 0.769$ and $d_3 \approx 0.231$, putting most of the flow near the 2-day mark.

### Surface Reservoir

Rain enters the surface store; the excess over capacity $X_1$ becomes runoff:

$$S \leftarrow S + P$$

$$P_r = \max(0, S - X_1)$$

$$S \leftarrow S - P_r$$

The corrected PET is deducted from the surface store, clamped at zero:

$$E_s = X_5 \cdot E$$

$$S \leftarrow \max(0, S - E_s)$$

### Soil Reservoir

The soil store receives the overflow and drains via a quadratic outflow law:

$$R \leftarrow R + P_r$$

$$Q_r = \frac{R^2}{R + X_2 X_3}$$

$$R \leftarrow R - Q_r$$

The quadratic form is the key non-linearity of GARDENIA.
Intuitively: when $R \gg X_2 X_3$, the denominator is dominated by $R$ and the formula reduces to $Q_r \approx R$ (all the water flows out); when $R \ll X_2 X_3$, the denominator is dominated by $X_2 X_3$ and $Q_r \approx R^2 / (X_2 X_3)$ (flow scales with the square of storage, a much slower recession).

Linear percolation to the groundwater store:

$$I_r = \frac{R}{X_2}$$

$$R \leftarrow R - I_r$$

### Groundwater Reservoir

The groundwater store receives percolation and drains linearly:

$$T \leftarrow T + I_r$$

$$Q_t = \frac{T}{X_4}$$

$$T \leftarrow T - Q_t$$

### Delay Routing

The total instantaneous output before routing is:

$$Q = Q_t + Q_r$$

The register $\{H_k\}$ is updated with the shift-and-add rule, with new flow $Q$ injected only into the last two positions via the fractional delay weights $\{d_k\}$:

$$H_k \leftarrow H_{k+1} + d_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow d_{n-1} \cdot Q$$

The simulated streamflow is the first register element, clamped at zero:

$$Q_{\text{sim}} = \max(0, H_0)$$

## References

Thiery, D. (1982).
Utilisation d'un modèle global pour identifier sur un niveau piézométrique des influences multiples dues à diverses activités humaines.
*IAHS Publication*, 136, 71–77.

Thiery, D. (1988).
Forecast of changes in piezometric levels by a lumped hydrological model.
*Journal of Hydrology*, 97, 129–148.

Filippi, C., Milville, F., & Thiery, D. (1990).
Evaluation de la recharge des aquifères en climat Soudano-Sahélien par modélisation hydrologique globale: application à dix sites au Burkina Faso.
*Hydrological Sciences Journal*, 35(1), 29–48.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°9 (GARDENIA), pp. 333–336.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
