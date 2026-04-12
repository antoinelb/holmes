# MARTINE Model

## Overview

MARTINE is a seven-parameter daily lumped rainfall-runoff model developed at the Bureau de Recherches Géologiques et Minières (BRGM) in Orléans, France, by Mazenc, Sanchez, and Thiery (1984).
It was originally designed for **regionalization** studies: the authors wanted a model simple enough that its parameters could be related to catchment physiographic descriptors (area, slope, soil type), enabling streamflow prediction at ungauged sites across Brittany.

The variant implemented in HOLMES is the **MART** seven-parameter version described in Annex 1 of Perrin (2000).
It represents the catchment as four reservoirs: a **surface reservoir** that intercepts rainfall and produces overflow, a **quadratic direct routing reservoir** that generates fast runoff, an **intermediate reservoir** with both linear drainage and overflow pathways, and a **groundwater reservoir** that drains linearly to produce baseflow.
A fractional delay is applied at the outlet to account for channel travel time.

What makes MARTINE distinctive among the HOLMES models is its **dual-pathway intermediate reservoir**.
Unlike models where subsurface flow follows a single outflow law, the intermediate reservoir $T$ drains both linearly ($Q_{t1} = T/X_7$) *and* by overflow ($Q_{t2} = \max(0, T - X_2)$) — the linear pathway delivers sustained interflow while the overflow activates only when the store exceeds its capacity, producing a threshold-driven baseflow surge during wet periods.
This dual structure, combined with the quadratic direct routing, gives MARTINE a flexible hydrograph shape without requiring many parameters.

## Key Concepts

- **Overflow-based surface reservoir**: The uppermost reservoir $S$ has a fixed capacity $X_1$.
Rain that causes $S$ to exceed $X_1$ overflows as effective rainfall $P_r$; the rest stays in $S$ and is available for evaporation.

- **Distribution coefficient**: The parameter $X_5$ splits the effective rainfall $P_r$ between the fast (direct routing) and slow (intermediate) pathways: $X_5 \cdot P_r$ goes to the routing reservoir $R$, while $(1 - X_5) \cdot P_r$ goes to the intermediate reservoir $T$.

- **Quadratic direct routing**: The routing reservoir $R$ drains via $Q_r = R^2 / (R + X_3)$, the same nonlinear law used in GARDENIA.
For high $R$ the response approaches linear discharge; for low $R$ it becomes quadratic, producing a smooth transition from flood peaks to recession.

- **Dual-pathway intermediate reservoir**: The intermediate store $T$ has two outflow pathways operating in sequence — a linear emptying $Q_{t1} = T / X_7$ followed by an overflow $Q_{t2} = \max(0, T - X_2)$ when the store exceeds its capacity.
Both outputs feed the groundwater store.

- **Residual evapotranspiration**: After the surface store has satisfied as much PET as it can ($E_s = \min(S, E)$), the unsatisfied remainder $E_t = E - E_s$ is applied to the intermediate reservoir.
This means the intermediate store can dry out during sustained warm spells even without surface overflow.

- **Linear groundwater recession**: The groundwater reservoir $L$ drains linearly at rate $Q_l = L / X_4$, producing sustained baseflow.
All intermediate outflows ($Q_{t1}$ and $Q_{t2}$) recharge this store.

- **Fractional delay routing**: Because the delay parameter $X_6$ is a real number (typically 0.5–5 days), MARTINE uses a two-element fractional delay register that interpolates between adjacent integer delays — e.g. $X_6 = 2.3$ puts 77% of flow at day 2 and 23% at day 3.

## How It Works

The MARTINE model processes precipitation and evapotranspiration through the following steps each day:

**Step 1: Surface reservoir inflow and overflow**.
Rain is added to the surface store: $S \leftarrow S + P$.
Any amount above the capacity $X_1$ overflows as effective rainfall $P_r = \max(0, S - X_1)$, and the store is reduced: $S \leftarrow S - P_r$.

**Step 2: Surface evaporation and residual ET**.
PET is deducted from the surface store up to what it holds: $E_s = \min(S, E)$, $S \leftarrow S - E_s$.
The unsatisfied remainder $E_t = E - E_s$ is carried forward and applied to the intermediate reservoir in Step 4.

**Step 3: Direct routing reservoir**.
The routing store receives the fast fraction of effective rainfall: $R \leftarrow R + X_5 \cdot P_r$.
It then empties via the quadratic law $Q_r = R^2 / (R + X_3)$, which generates strong fast runoff when $R$ is large and very little when $R$ is small.
The store is updated: $R \leftarrow R - Q_r$.

**Step 4: Intermediate reservoir**.
The residual ET from Step 2 is subtracted first: $T \leftarrow \max(0, T - E_t)$.
Then the slow fraction of effective rainfall is added: $T \leftarrow T + (1 - X_5) \cdot P_r$.
Linear drainage produces $Q_{t1} = T / X_7$, and any excess above capacity produces overflow $Q_{t2} = \max(0, T - X_2)$.
Both are deducted from $T$ and sent to the groundwater store.

**Step 5: Groundwater reservoir**.
The groundwater store receives both intermediate outflows: $L \leftarrow L + Q_{t1} + Q_{t2}$.
It drains linearly: $Q_l = L / X_4$, $L \leftarrow L - Q_l$.
$X_4$ controls the baseflow recession speed.

**Step 6: Delay register**.
The total instantaneous output $Q_l + Q_r$ is injected into a fractional delay register of size $\lceil X_6 \rceil + 1$.
The register shifts by one position each time step and its first element is returned as simulated streamflow, clamped at zero.

## Parameters

The MARTINE model has seven calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|:-----:|-------|------------------------|
| $X_1$ (CRSM) | Surface reservoir capacity | 1–2000 | mm | Maximum storage of the surface store (interception + topsoil). Larger values absorb more rain before producing overflow. |
| $X_2$ (HMAM) | Intermediate reservoir capacity | 1–2000 | mm | Capacity threshold for the intermediate reservoir. Overflow $Q_{t2}$ is produced only when $T > X_2$, creating a second baseflow pathway that activates during wet conditions. |
| $X_3$ (RUIM) | Quadratic routing reservoir parameter | 0.01–1000 | mm | Characteristic storage in the denominator of the quadratic law $Q_r = R^2/(R+X_3)$. Smaller $X_3$ yields faster, flashier direct runoff; larger $X_3$ dampens the response. |
| $X_4$ (TB) | Groundwater emptying constant | 1–500 | days | Residence time of the linear groundwater store. Controls the speed and persistence of baseflow recession. |
| $X_5$ (CRUM) | Distribution coefficient | 0.01–0.99 | - | Fraction of effective rainfall routed to the fast (quadratic) pathway. $1 - X_5$ goes to the intermediate (slow) pathway. |
| $X_6$ | Delay | 0.5–5 | days | Pure delay applied at the outlet via a fractional interpolation. Shifts the hydrograph without changing its shape. |
| $X_7$ (TP) | Intermediate reservoir emptying constant | 1–500 | days | Residence time for the linear drainage of the intermediate reservoir ($Q_{t1} = T/X_7$). Slower drainage (larger $X_7$) means more water stays in $T$ and eventually overflows to the groundwater store. |

**Understanding the parameters:**

- **$X_1$** is the rain interception / topsoil threshold — how much rain the catchment absorbs at the surface before any runoff is generated.
Typically calibrates between 50 and 500 mm depending on soil depth and land cover.
- **$X_2$ and $X_7$ together** control the intermediate reservoir behavior.
$X_7$ is the linear drainage time constant (how fast water trickles down to groundwater), while $X_2$ is the overflow threshold (when the store spills into the groundwater as a pulse).
A small $X_7$ with a large $X_2$ gives steady percolation; a large $X_7$ with a small $X_2$ gives bursty overflow.
- **$X_3$** controls the direct routing recession shape.
Small values (< 10 mm) make floods drain quickly with sharp peaks; large values (> 100 mm) flatten and delay the direct runoff component.
- **$X_5$** is the key flow partitioning knob.
Values near 1 send most water through the fast (quadratic) pathway, producing flashier hydrographs; values near 0 favor the slow pathway through the intermediate and groundwater stores.
- **$X_4$** controls how long baseflow persists after wet periods.
Long $X_4$ (weeks to months) produces a deep, slow aquifer with seasonal memory; short $X_4$ (days) makes the catchment more responsive.

## Mathematical Formulation

### Initialization

Initial store levels:

$$S_0 = X_1, \quad T_0 = \frac{X_2}{2}, \quad L_0 = 5, \quad R_0 = 0.1 \, X_3$$

where $S$ is the surface reservoir (initialized at capacity), $T$ is the intermediate reservoir, $L$ is the groundwater reservoir, and $R$ is the direct routing reservoir.
These initial values produce a short warm-up transient that typically dissipates within a few weeks of simulation.

The delay register is a fractional two-weight array of size $n = \lceil X_6 \rceil + 1$, with only the last two entries non-zero:

$$d_{n-2} = \frac{1}{X_6 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}$$

### Surface Reservoir

Rain enters the surface store; the excess over capacity $X_1$ becomes effective rainfall:

$$S \leftarrow S + P$$

$$P_r = \max(0,\; S - X_1)$$

$$S \leftarrow S - P_r$$

Evapotranspiration is deducted from the surface store, capped at zero:

$$E_s = \min(S,\; E)$$

$$S \leftarrow S - E_s$$

The unsatisfied remainder is carried to the intermediate reservoir:

$$E_t = E - E_s$$

### Direct Routing Reservoir

The fast fraction of effective rainfall feeds the routing store, which drains quadratically:

$$R \leftarrow R + X_5 \cdot P_r$$

$$Q_r = \frac{R^2}{R + X_3}$$

$$R \leftarrow R - Q_r$$

The quadratic form produces strong runoff when $R$ is large ($Q_r \approx R$) and very weak runoff when $R$ is small ($Q_r \approx R^2 / X_3$).

### Intermediate Reservoir

Residual ET is applied first, then the slow fraction of effective rainfall is added:

$$T \leftarrow \max(0,\; T - E_t)$$

$$T \leftarrow T + (1 - X_5) \cdot P_r$$

Two outflow pathways operate in sequence — linear drainage followed by capacity overflow:

$$Q_{t1} = \frac{T}{X_7}, \quad T \leftarrow T - Q_{t1}$$

$$Q_{t2} = \max(0,\; T - X_2), \quad T \leftarrow T - Q_{t2}$$

### Groundwater Reservoir

The groundwater store receives both intermediate outflows and drains linearly:

$$L \leftarrow L + Q_{t1} + Q_{t2}$$

$$Q_l = \frac{L}{X_4}$$

$$L \leftarrow L - Q_l$$

### Delay Routing

The total instantaneous output before routing is:

$$Q = Q_l + Q_r$$

The register $\{H_k\}$ is updated with the shift-and-add rule, with new flow $Q$ injected only into the last two positions via the fractional delay weights $\{d_k\}$:

$$H_k \leftarrow H_{k+1} + d_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow d_{n-1} \cdot Q$$

The simulated streamflow is the first register element, clamped at zero:

$$Q_{\text{sim}} = \max(0,\; H_0)$$

## References

Mazenc, B., Sanchez, M., & Thiery, D. (1984).
Analyse de l'influence de la physiographie d'un bassin versant sur les paramètres d'un modèle hydrologique global et sur les débits caractéristiques à l'exutoire.
*Journal of Hydrology*, 69, 97–118.
[DOI](https://doi.org/10.1016/0022-1694(84)90159-6)

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°19 (MARTINE), pp. 387–390.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
