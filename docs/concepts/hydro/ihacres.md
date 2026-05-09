# IHACRES Model

## Overview

IHACRES (Identification of unit Hydrographs And Component flows from Rainfall, Evaporation and Streamflow data) is a seven-parameter daily lumped rainfall–runoff model jointly developed at the Institute of Hydrology (Wallingford, UK) and the Australian National University in the early 1990s.
The original formulation appears in Jakeman et al. (1990) and the operational PC version is documented in Littlewood et al. (1997).

IHACRES occupies a distinctive niche among lumped models: it explicitly separates a **non-linear loss module** (which converts gross rainfall into "effective rainfall") from a **linear unit-hydrograph routing module** (which transforms effective rainfall into streamflow).
The loss module is built around a single dimensionless **catchment moisture index** $S$ that decays exponentially between rain events at a rate modulated by potential evapotranspiration.
The routing module places two parallel linear reservoirs in series with a pure delay — a fast store and a slow store sharing a multiplicative coupling — making it equivalent to a two-tap impulse response.

The HOLMES implementation follows Perrin's (2000) "version retenue" of the model, which uses PET in place of temperature in the drying-rate term.
Students often pick IHACRES as a teaching contrast to soil-bucket models (GR4J, GARDENIA, BUCKET): it shows that you can produce realistic streamflow without an explicit "reservoir capacity", relying instead on a moisture *index* that gates an otherwise linear system.

## Key Concepts

- **Catchment moisture index ($S$)**: A dimensionless state variable that tracks how wet the catchment is. Unlike a soil bucket, $S$ has no upper bound — it grows during wet periods and decays during dry periods at a rate set by PET.
- **Effective rainfall ($P_r$)**: The fraction of incoming rainfall that actually contributes to streamflow, computed as the product of the moisture index and the rainfall depth. When $S$ is small (dry), most rain is lost; when $S$ is large (wet), most rain becomes runoff.
- **PET-modulated drying constant ($\tau_w$)**: The time constant of the moisture index recession. It is *not* a fixed parameter — it shrinks when PET is high (faster drying) and expands when PET is low (slower drying), reproducing the seasonal asymmetry between summer and winter recessions.
- **Mass-balance forcing ($1/C$)**: A calibrated scaler ($X_1$) that converts gross rainfall into the moisture-index increment. It absorbs systematic differences between long-term gauge precipitation and observed runoff so that calibrated total flow matches observed total flow.
- **Parallel fast/slow routing**: Effective rainfall is split between two linear reservoirs by a fraction $X_2$. The fast reservoir empties with time constant $X_3$ (peak response); the slow reservoir empties with time constant $X_3 \cdot X_4$ (baseflow). The shared $X_3$ is a structural coupling — calibrating one affects both.
- **Pure delay ($X_5$)**: A fractional delay-line at the catchment outlet representing in-channel travel time, distributed between the two cells nearest to $\lceil X_5 \rceil$.

## How It Works

The IHACRES model processes precipitation and PET through the following steps:

**Step 1: Compute the drying-rate exponent**.
At time step $k$, the model first computes a drying exponent $E_l = \max(0, X_7 - E_k / X_6)$, where $X_7$ is the baseline drying constant and $X_6$ is the PET-modulation factor.
When PET is high, $E_k / X_6$ grows large, $E_l$ shrinks toward zero, and the moisture index decays slowly (or not at all in the saturated-drying limit).
When PET is low, $E_l$ stays close to $X_7$ and the recession is fast.

**Step 2: Update the catchment moisture index**.
The moisture index obeys an IIR filter equation: the previous value is multiplied by a decay coefficient $1 - 1/\exp(E_l) \in [0, 1)$ and incremented by $P_k / X_1$.
The mass-balance scaler $X_1$ converts the rainfall depth to a dimensionless increment that keeps long-term simulated and observed totals consistent.

**Step 3: Compute effective rainfall**.
Effective rainfall is the product of the average moisture index over the time step and the rainfall depth: $P_r = \frac{1}{2}(S_{k-1} + S_k) \cdot P_k$.
The midpoint trapezoidal rule reflects the fact that the catchment is wetting up *during* the time step, so the contributing wetness is the average of the start and end values.

**Step 4: Split between fast and slow paths**.
A fraction $X_2$ of the effective rainfall enters the fast linear reservoir $R$; the complementary fraction $1 - X_2$ enters the slow linear reservoir $T$.
This split is purely empirical — there is no soil-physics derivation for it.

**Step 5: Drain the routing reservoirs**.
The fast reservoir releases $Q_r = R / X_3$ each step; the slow reservoir releases $Q_t = T / (X_3 \cdot X_4)$.
The shared $X_3$ couples the two recessions so that calibration cannot make them fully independent.
The slow store inherits a longer memory ($X_4 \geq 1$ enforces slow $\geq$ fast).

**Step 6: Apply the pure delay**.
The combined outflow $Q_r + Q_t$ enters a fractional-delay line of length $\lceil X_5 \rceil + 1$.
Two non-zero weights distribute the new pulse across the last two cells, producing a smooth interpolation between integer delays.

**Step 7: Read the simulated streamflow**.
The streamflow at the catchment outlet is the leading cell of the delay array, clamped at zero to guarantee non-negative output.

## Parameters

The IHACRES model has seven calibratable parameters.
Note that the lower bound on $X_3$ is set to 1 day rather than the more permissive values found in the original literature.
This is a *numerical stability* constraint: the explicit-Euler routing scheme $Q = R / X_3$ followed by $R \leftarrow R - Q$ becomes unstable when $X_3 < 1$, since the per-step decay coefficient $|1 - 1/X_3|$ exceeds 1 and the reservoir oscillates with growing amplitude.
A 1-day floor is also physically reasonable for a model running on daily forcing.

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ ($1/C$) | Mass-balance forcing parameter | 1–1000 | – | Inverse of the calibrated forcing constant. Smaller values amplify rainfall into the moisture index, producing more total runoff. Used to correct long-term water-balance errors. |
| $X_2$ ($\alpha$) | Fast-flow fraction of effective rainfall | 0.01–0.99 | – | Fraction of effective rainfall routed to the fast store. Higher values produce flashier hydrographs; lower values emphasize baseflow. |
| $X_3$ | Fast routing reservoir time constant | 1–100 | days | Linear residence time of the fast store. Smaller values produce sharper peaks; values below 1 are excluded for numerical stability. |
| $X_4$ | Slow routing multiplier | 1–1000 | – | Multiplicative coupling: the slow store has time constant $X_3 \cdot X_4$. Constrained to $\geq 1$ to enforce "slow $\geq$ fast". |
| $X_5$ | Pure delay | 0.5–5.0 | days | Channel travel time from catchment to outlet. A fractional value distributes the pulse across two adjacent time cells. |
| $X_6$ ($f$) | PET modulation factor | 0.1–10 | – | Sensitivity of the drying time constant to PET. Larger values weaken the PET coupling; smaller values make recession highly seasonal. |
| $X_7$ ($T_w$) | Characteristic catchment drying constant | 0.1–10 | – | Baseline drying exponent at zero PET. Larger values mean the catchment retains moisture longer. The natural recession time scale (in days) is approximately $1 / (1 - 1/\exp(X_7))$. |

**Understanding the parameters:**

- **$X_1$ alone** scales the entire mass balance.
Calibration drives it to whatever value makes long-term simulated and observed runoff totals match — its value carries no physical meaning beyond "what the data demands".
A common diagnostic during manual calibration is to plot cumulative simulated vs. observed runoff: if the slope is wrong, $X_1$ is wrong.

- **$X_2$, $X_3$, and $X_4$ together** define the linear routing.
Because $X_3$ is shared between the fast ($X_3$) and slow ($X_3 \cdot X_4$) recessions, you cannot calibrate them fully independently — moving $X_3$ rescales both.
Practical workflow: fix $X_3$ from a recession analysis on the observed streamflow, then calibrate $X_2$ and $X_4$ from the peak/baseflow ratio.

- **$X_5$** is a pure timing parameter and only matters if the catchment is large enough to introduce a noticeable lag between peak rainfall and peak flow.
For small catchments at daily resolution, $X_5 \approx 1$ day is usually adequate.

- **$X_6$ and $X_7$ together** control the moisture index dynamics.
The drying time constant is approximately $\tau_w \approx \exp(X_7 - E/X_6)$ days when the argument is positive.
For temperate catchments with summer PET around 4 mm/day, $X_6$ in the range 1–5 and $X_7$ in the range 1–5 typically gives the seasonal recession asymmetry observed in the data.
Setting $X_7$ very small forces the moisture index to decay aggressively even in winter, which is rarely realistic.

## Mathematical Formulation

### Initialization

The reservoir states are initialized to the HOOPLA HM8 defaults, independent of the parameter values:

$$S_0 = 0.5, \quad R_0 = 5, \quad T_0 = 50$$

The pure-delay vector of length $n = \lceil X_5 \rceil + 1$ is built once with all-zero history and two non-zero weights at the trailing cells:

$$d_{n-2} = \frac{1}{X_5 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}, \quad d_i = 0 \text{ for } i < n-2$$

### Drying Exponent

At each time step, the drying exponent is computed from the current PET:

$$E_{l,k} = \max\left(0, \; X_7 - \frac{E_k}{X_6}\right)$$

The $\max(\cdot, 0)$ clamp implements the "saturated-drying limit": no matter how high PET gets, the drying rate cannot become negative (i.e. the catchment cannot anti-dry).

### Catchment Moisture Index

The moisture index updates via a linear IIR filter with rainfall input:

$$S_k \leftarrow S_{k-1} + \frac{P_k}{X_1} - \frac{S_{k-1}}{\exp(E_{l,k})}$$

Equivalently, $S_k = \alpha_k \cdot S_{k-1} + P_k / X_1$ with $\alpha_k = 1 - 1/\exp(E_{l,k}) \in [0, 1]$.
The filter is strictly stable as long as $E_{l,k} > 0$; the bounds enforced on $X_3$, $X_6$, and $X_7$ keep the routing reservoirs numerically stable in the rare event that $E_{l,k}$ touches zero.

### Effective Rainfall

Effective rainfall is the trapezoidal-rule midpoint of the moisture index times the rainfall depth:

$$P_{r,k} = \frac{1}{2} \left(S_{k-1} + S_k\right) \cdot P_k$$

When $S$ is near zero (dry catchment), almost all rainfall is lost.
When $S$ is large (saturated catchment), almost all rainfall reaches the routing module.

### Fast Routing Reservoir

The fast store receives a fraction $X_2$ of the effective rainfall and drains linearly with time constant $X_3$:

$$R_k \leftarrow R_{k-1} + X_2 \cdot P_{r,k}$$

$$Q_{r,k} = \frac{R_k}{X_3}$$

$$R_k \leftarrow R_k - Q_{r,k}$$

### Slow Routing Reservoir

The slow store receives the complementary fraction $1 - X_2$ and drains with the longer time constant $X_3 \cdot X_4$:

$$T_k \leftarrow T_{k-1} + (1 - X_2) \cdot P_{r,k}$$

$$Q_{t,k} = \frac{T_k}{X_3 \cdot X_4}$$

$$T_k \leftarrow T_k - Q_{t,k}$$

### Delay Routing and Total Streamflow

The combined fast-plus-slow outflow $Q_{r,k} + Q_{t,k}$ is convolved with the static delay vector by shifting the in-channel buffer one cell forward and depositing the new pulse at the trailing cells:

$$h_i \leftarrow h_{i+1} + d_i \cdot (Q_{r,k} + Q_{t,k}) \quad \text{for } i = 0, \ldots, n-2$$

$$h_{n-1} \leftarrow d_{n-1} \cdot (Q_{r,k} + Q_{t,k})$$

The simulated streamflow at the catchment outlet is the leading cell, clamped at zero:

$$Q_{\text{sim},k} = \max(h_0, 0)$$

## References

Jakeman, A. J., Littlewood, I. G., & Whitehead, P. G. (1990).
Computation of the instantaneous unit hydrograph and identifiable component flows with application to two small upland catchments.
*Journal of Hydrology*, 117(1–4), 275–300.

Littlewood, I. G., Down, K., Parker, J. R., & Post, D. A. (1997).
*The PC version of IHACRES for catchment-scale rainfall-streamflow modelling. Version 1.0. User Guide*.
Institute of Hydrology, Wallingford, UK, 89 pp.

Jakeman, A. J., & Hornberger, G. M. (1993).
How much complexity is warranted in a rainfall-runoff model?
*Water Resources Research*, 29(8), 2637–2649.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis).
INPG, Grenoble. Annexe 1, fiche analytique n°17.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
