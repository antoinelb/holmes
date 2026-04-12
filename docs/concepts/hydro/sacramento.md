# SACRAMENTO Model

## Overview

SACRAMENTO is a nine-parameter daily lumped rainfall-runoff model derived from the Sacramento Soil Moisture Accounting model (SAC-SMA) developed by Burnash, Ferral and McGuire (1973) at the US National Weather Service.
It became the backbone of the NWS River Forecast System and has been operational across US forecast centers for more than four decades, which makes it one of the most rigorously field-tested conceptual models in operational hydrology.

The original SAC-SMA exposes fourteen parameters across five soil-moisture zones (upper-zone tension, upper-zone free, lower-zone tension, lower-zone primary free, lower-zone secondary free), but Perrin (2000) showed that a simplified nine-parameter variant retains most of the structural richness while being dramatically easier to calibrate.
The variant implemented in HOLMES is that **"version retenue"** described in Annex 1 of Perrin's thesis (fiche n°27): it merges the lower-zone primary and secondary free-water compartments into a single reservoir, fixes the impermeable-surface fraction to zero, hard-codes the interception capacity to 3 mm, and simplifies the infiltration function.
Structurally the result is a cascade of five reservoirs — $S$ (interception), $T$ (upper-zone tension), $R$ (upper-zone free), $L$ (lower-zone routing) and $M$ (direct routing) — linked by evaporation, percolation, hypodermic outflow, and a mass-balance correction that can move water *upward* from $R$ to $L$ when evapotranspiration over-drains the lower store.

Students typically choose SACRAMENTO to study how an operational-grade soil-moisture accounting scheme separates runoff into direct, interflow, and baseflow components using explicit reservoirs for each pathway — a richer decomposition than simpler models like GR4J or BUCKET expose.

## Key Concepts

- **Interception reservoir**: A small fixed-capacity store $S$ (3 mm) that intercepts rainfall and consumes the first share of PET before any water reaches the soil. It mimics canopy and depression storage.

- **Upper-zone tension water ($T$)**: The main soil-moisture store, playing the role of "uztwm" in Burnash notation. It receives throughfall, releases water to the free-water store $R$ via percolation, drains laterally as hypodermic flow, loses water to evapotranspiration, and overflows when saturated.

- **Upper-zone free water ($R$)**: A fast baseflow store that receives most of the percolation from $T$ and drains linearly with time constant $X_3$. In the original Burnash model this is the "uzfwm" store.

- **Lower-zone routing reservoir ($L$)**: A small-capacity store (capped at 30 mm) sitting between $T$ and $R$ that absorbs a fraction $X_7$ of the percolation and also evaporates residual PET. When its contents are over-drained by ET, a mass-balance correction transfers water back up from $R$.

- **Direct routing reservoir ($M$)**: A fast linear store that receives only the *saturation overflow* of $T$ and drains with time constant $X_1$, producing the direct-runoff component of the hydrograph.

- **Percolation with filling feedback**: The percolation from $T$ to $R$ is modulated by the filling ratio $R/X_2$ of the *receiving* reservoir: as $R$ fills up, percolation slows down and more water stays in $T$ (where it can either evaporate, drain laterally, or overflow). This feedback is the core of Burnash's soil-moisture accounting idea.

- **Upward mass-balance correction**: If the residual PET over-evaporates the lower-zone routing store $L$, the model pulls the deficit $I_r$ from $R$'s free space above $X_2 - 30$. This is the only process in the model where water moves against gravity.

- **Fractional-delay routing**: All three outflows $Q_r$, $Q_m$, and $Q_{t1}$ are summed and passed through a fractional-delay register of length $\lceil X_9 \rceil + 1$, identical to the GR4J/GARDENIA delay mechanism — this lets non-integer values of $X_9$ translate into a smooth time shift without resorting to per-step interpolation.

## How It Works

The SACRAMENTO model processes precipitation and evapotranspiration through the following steps:

**Step 1: Interception store (surface phase)**.
The rainfall $P$ is added to the interception store $S$.
Evaporation $E_s = \min(E, S)$ consumes the first share of the day's PET from $S$; the rest of the PET, $E' = E - E_s$, becomes the "residual" that will cascade through the rest of the model.
If $S$ overflows its fixed cap $XF_1 = 3$ mm, the overflow $I_s$ enters the upper-zone tension store $T$.

**Step 2: Percolation to the free-water store ($T \to R$)**.
The tension store $T$ first receives $I_s$. The percolation rate is then computed as $I_t = X_5 \cdot (1 - R/X_2) \cdot T/X_4$, clamped to $[0, T]$ so it can never exceed the available water.
The factor $(1 - R/X_2)$ implements Burnash's "filling-feedback" — as $R$ saturates, $I_t$ drops to zero, and the tension store has to dispose of its water through the other pathways.

**Step 3: Hypodermic flow and evaporation from $T$**.
The residual water in $T$ produces a hypodermic outflow $Q_{t1} = T/X_6$ (the "interflow" pathway) and is then subjected to the residual PET, scaled by $T/X_4$ to represent water-limited evaporation.
The remaining PET after this step, $E''$, is what eventually reaches the lower-zone store $L$.

**Step 4: Saturation overflow of $T$**.
If $T$ still exceeds its capacity $X_4$ after all the above, the excess $Q_{t0} = \max(0, T - X_4)$ overflows into the direct routing store $M$. This is the saturation-excess component of the direct runoff.

**Step 5: Routing to $L$ and $R$**.
The percolation $I_t$ is split by the partitioning coefficient $X_7$: a fraction $X_7 \cdot I_t$ feeds the lower-zone routing reservoir $L$, while the complementary fraction $(1 - X_7) \cdot I_t$ goes directly to $R$.
If $L$ overflows its cap $XF_2 = 30$ mm, the overflow $I_l$ is diverted straight to $R$.

**Step 6: Residual evaporation from $L$ and upward correction**.
The residual PET $E''$ evaporates from $L$ at rate $E_l = E'' \cdot L / (XF_1 + XF_2)$, proportional to $L$'s filling ratio of the combined interception + routing capacity.
If this drives $L$ below zero, the model pulls a compensation $I_r$ from $R$'s "free space" above $X_2 - XF_2$ — this is the mass-balance correction that keeps reservoir contents non-negative while preserving the water balance.

**Step 7: Baseflow and deep-percolation damping**.
The free-water store $R$ drains linearly as $Q_r = R / X_3$, then the baseflow is further damped by the deep-percolation coefficient $X_8 \geq 1$: $Q_r \leftarrow Q_r / X_8$.
This two-stage damping allows the calibration to decouple the raw baseflow time constant ($X_3$) from the share of baseflow that actually reaches the outlet — the rest is treated as deep-percolation loss from the watershed.

**Step 8: Direct routing and total streamflow**.
The direct routing store $M$ receives $Q_{t0}$ from Step 4 and drains linearly with time constant $X_1$, producing $Q_m = M / X_1$.
The three components $Q_r + Q_m + Q_{t1}$ are summed and pushed through a fractional-delay register of length $\lceil X_9 \rceil + 1$, and the first element of the register is returned as the simulated streamflow, clamped at zero.

## Parameters

The SACRAMENTO model has nine calibratable parameters.

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|:-----:|-------|------------------------|
| $X_1$ | Direct routing reservoir capacity (uzk-equivalent) | 1–20 | days | Residence time of the fast direct-runoff store $M$. Small values give flashy flood peaks; large values smear the peak over several days. |
| $X_2$ | Upper-zone free-water capacity ($uzfwm$) | 30–1000 | mm | Storage capacity of the fast baseflow store $R$. Also controls the filling-feedback that throttles percolation from $T$ once $R$ is near saturation. |
| $X_3$ | Lower-zone emptying constant | 10–500 | days | Linear time constant of the free-water store $R$. Larger values produce longer recession curves. |
| $X_4$ | Upper-zone tension-water capacity ($uztwm$) | 10–500 | mm | Storage capacity of the soil moisture store $T$. Above $X_4$ the tension store overflows into the direct routing store $M$. |
| $X_5$ | Maximum percolation rate | 0.01–20 | mm/day | Scale factor for percolation from $T$ to $R$. Larger values move more water into the fast baseflow pathway per time step. |
| $X_6$ | Hypodermic flow emptying constant | 1–100 | days | Time constant of the interflow pathway $Q_{t1} = T / X_6$. Small values give fast subsurface response; large values suppress interflow. |
| $X_7$ | Upper-zone partitioning coefficient ($pfree$) | 0.01–0.99 | - | Fraction of percolation $I_t$ routed to the lower-zone store $L$ (the remainder goes to $R$). Controls the split between slow lower-zone dynamics and fast free-water baseflow. |
| $X_8$ | Deep percolation coefficient | 1–50 | - | Damping factor applied to $Q_r$ to represent groundwater loss below the watershed. Larger values reduce baseflow reaching the outlet without changing its shape. |
| $X_9$ | Delay | 0.5–10 | days | Fractional delay applied to the summed outflow through a shift register. Handles non-integer travel times without interpolation. |

**Understanding the parameters:**

- **$X_4$ and $X_2$ together** set the soil-water budget of the catchment: $X_4$ is the tension-water capacity (how much rain it takes to saturate the soil) and $X_2$ is the free-water capacity (how much water the fast baseflow store can hold). Typical values in Perrin's calibrated set put $X_4$ in the 100–300 mm range and $X_2$ around 200–500 mm.
- **$X_5$ and $X_7$** control the percolation pathway. $X_5$ sets the maximum rate at which $T$ can feed $R$, while $X_7$ decides what share is diverted through the lower-zone store $L$ first. A high $X_7$ makes the model more sensitive to residual evaporation (via the mass-balance correction), which can be useful on catchments with strong vegetation control.
- **$X_3$, $X_6$, and $X_1$** are the three time constants that shape the hydrograph recession.  $X_6$ controls the interflow tail (hours to days), $X_1$ controls the direct-runoff decay (days), and $X_3$ controls the baseflow decay (weeks to months). The three together let the model fit hydrographs with very different fast/slow balances.
- **$X_8$** is the only parameter that breaks the mass balance intentionally. Setting $X_8 = 1$ means all baseflow reaches the outlet; $X_8 = 50$ means 98 % of it is lost to deep percolation. This parameter is pedagogically interesting because it lets students see the impact of deep groundwater losses on long-term water balance.
- **$X_9$** is a pure translation parameter: it does not affect the shape of the hydrograph, only its timing. It should be calibrated last, once the other parameters have produced a hydrograph of the right shape.

**Why the interception and lower-zone capacities are fixed**: Perrin's "version retenue" hard-codes $XF_1 = 3$ mm (interception) and $XF_2 = 30$ mm (lower-zone routing). These were originally calibrated parameters in the full Burnash model but were found to be weakly identifiable, so Perrin fixed them to reasonable physical defaults to reduce the search space and eliminate the equifinality associated with small-capacity reservoirs.

## Mathematical Formulation

### Initialization

Initial store levels (from HOOPLA's `ini_HydroMod14.m`, matching the moderately wet catchment state in Perrin's fiche):

$$S_0 = 3, \quad T_0 = 10, \quad R_0 = 100, \quad L_0 = 0, \quad M_0 = 0$$

Fixed capacities:

$$XF_1 = 3 \ \text{mm} \ \text{(interception)}, \quad XF_2 = 30 \ \text{mm} \ \text{(lower-zone routing)}$$

The fractional-delay routing array $\{DL_k\}$ of length $n = \lceil X_9 \rceil + 1$ is built such that only the last two elements are non-zero:

$$DL_{n-2} = \frac{1}{X_9 - n + 3}, \quad DL_{n-1} = 1 - DL_{n-2}$$

This construction represents a non-integer delay of $X_9$ time steps as a two-element stencil at the tail of an otherwise-empty array.

### Surface Phase (interception store)

$$S \leftarrow S + P$$

$$E_s = \min(E, S), \quad S \leftarrow S - E_s, \quad E' = E - E_s$$

$$I_s = \max(0, S - XF_1), \quad S \leftarrow S - I_s$$

### Upper-Zone Tension Store ($T$)

The spill $I_s$ enters $T$:

$$T \leftarrow T + I_s$$

Percolation to the upper-zone free-water store $R$, with filling-feedback damping:

$$I_t = \mathrm{clamp}\left(X_5 \cdot \left(1 - \frac{R}{X_2}\right) \cdot \frac{T}{X_4}, \ 0, \ T\right)$$

$$T \leftarrow T - I_t$$

Hypodermic (interflow) outflow:

$$Q_{t1} = \frac{T}{X_6}, \quad T \leftarrow T - Q_{t1}$$

Evaporation (water-limited via the filling ratio):

$$E_t = \min\left(E' \cdot \min\left(1, \frac{T}{X_4}\right), \ T\right), \quad T \leftarrow T - E_t, \quad E'' = E' - E_t$$

Saturation overflow to the direct routing store $M$:

$$Q_{t0} = \max(0, \ T - X_4), \quad T \leftarrow T - Q_{t0}$$

### Lower-Zone Routing Store ($L$) and Upward Correction

Percolation $I_t$ is split between $L$ (fraction $X_7$) and $R$ (fraction $1 - X_7$):

$$L \leftarrow L + X_7 \cdot I_t$$

$$I_l = \max(0, \ L - XF_2), \quad L \leftarrow L - I_l$$

$$R \leftarrow R + (1 - X_7) \cdot I_t + I_l$$

Residual PET evaporates $L$ proportionally to its filling ratio of the combined interception + routing capacity:

$$E_l = E'' \cdot \frac{L}{XF_1 + XF_2}, \quad L \leftarrow L - E_l$$

If $L$ now sits below zero, the deficit is pulled upward from $R$'s free space:

$$\text{if } L < 0: \quad I_r = \min\left(-L, \ \max\left(0, \ R - (X_2 - XF_2)\right)\right)$$

$$L \leftarrow \max(0, \ L + I_r), \quad R \leftarrow R - I_r$$

### Upper-Zone Free-Water Store ($R$, baseflow)

$$Q_r = \frac{R}{X_3}, \quad R \leftarrow R - Q_r$$

The baseflow reaching the outlet is damped by deep percolation:

$$Q_r \leftarrow \frac{Q_r}{X_8}$$

### Direct Routing Store ($M$)

$$M \leftarrow M + Q_{t0}, \quad Q_m = \frac{M}{X_1}, \quad M \leftarrow M - Q_m$$

### Total Streamflow and Fractional Delay

The three outflows are summed and pushed through the shift-and-add delay register $\{HY_k\}$ of the same length as $\{DL_k\}$:

$$Q = Q_r + Q_m + Q_{t1}$$

$$HY_k \leftarrow HY_{k+1} + DL_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$HY_{n-1} \leftarrow DL_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0, \ HY_0)$$

The first element of the register is returned as the simulated streamflow for the current time step; the register then advances by one position, ready for the next step.

## References

Burnash, R. J. C., Ferral, R. L., & McGuire, R. A. (1973).
*A generalized streamflow simulation system – Conceptual modelling for digital computers*.
US Department of Commerce, National Weather Service, and State of California, Department of Water Resources.

Burnash, R. J. C. (1995).
The NWS River Forecast System — catchment modelling.
In V. P. Singh (Ed.), *Computer Models of Watershed Hydrology*, Chapter 10, pp. 311–366.
Water Resources Publications.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°27 (Sacramento), pp. 425–429.

Sorooshian, S., Duan, Q., & Gupta, V. K. (1993).
Calibration of rainfall-runoff models: Application of global optimization to the Sacramento soil moisture accounting model.
*Water Resources Research*, 29(4), 1185–1194.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
