# MORDOR Model

## Overview

MORDOR (Modèle à Réservoirs de Drainage Ordinaire) is a conceptual rainfall-runoff model developed at Électricité de France (EDF) by Garçon (1999) for operational inflow forecasting at hydropower reservoirs.
The version implemented in HOLMES follows the six-parameter lumped variant catalogued as HM11 in the HOOPLA framework.

The model represents a catchment as four cascading reservoirs — surface (U), intermediate (L), deep soil (Z), and groundwater (N) — that progressively filter rainfall into slower and deeper flow components.
All three flow outputs (surface runoff, rapid underground flow, slow groundwater discharge) are routed through the same double-sided unit hydrograph UH2, producing a smooth composite hydrograph.

MORDOR occupies a middle ground in complexity: six parameters are enough to capture the dominant water balance processes while remaining easy to calibrate manually.
Its cascading four-reservoir structure makes it a good pedagogical counterpoint to simpler two-store models like GR4J, and its explicit separation of deep soil and groundwater storage makes it well-suited to catchments with significant baseflow contributions.

## Key Concepts

- **Surface reservoir (U)**: The uppermost store receiving the corrected rainfall.
It fills from rainfall that is not immediately shed as proportional runoff, and loses water through evapotranspiration and overflow.
Its capacity is set by $X_5$.

- **Intermediate reservoir (L)**: Receives infiltrated water from U overflow.
It drains linearly at a rate controlled by the emptying constant $X_2$, distributing its outflow downward to Z and N and laterally as rapid underground runoff.

- **Deep soil reservoir (Z)**: A fixed-capacity store (90 mm) representing deep unsaturated soil moisture.
It receives percolation from L drainage, loses water to evapotranspiration, and acts as a partitioning buffer: the fuller Z is, the more water is diverted to rapid underground flow and groundwater recharge instead of deep percolation.

- **Groundwater reservoir (N)**: The deepest store, producing slow baseflow through a nonlinear (cubic) drainage law controlled by $X_3$.

- **Rain correction coefficient ($X_1$)**: A multiplicative factor applied to the raw precipitation to correct for gauge undercatch or spatial representativeness.

- **Proportional rainfall partitioning**: Incoming corrected rainfall is split between direct runoff and infiltration into U in proportion to the current filling ratio $U/X_5$ — the wetter the surface store, the more rainfall becomes runoff.

- **UH2 unit hydrograph**: A double-sided (symmetric-tailed) unit hydrograph with exponent 2.5 and time base $2 X_4$.
All three flow components are independently convolved through identical UH2 instances before being summed.

## How It Works

**Step 1: Rain correction**.
Raw precipitation $P$ is multiplied by the correction coefficient $X_1$ to obtain the effective precipitation $P_L = P \cdot X_1$.
This accounts for systematic gauge undercatch or spatial non-representativeness of point measurements.

**Step 2: Rainfall partitioning and surface store update**.
The corrected precipitation is split proportionally to the current U filling ratio: a fraction $U/X_5$ becomes direct runoff, and the remainder enters the surface store.
If the store overflows (exceeds $X_5$), the excess is added to surface runoff.
The total surface flow component $V_S$ (direct runoff + overflow) will be routed later.

**Step 3: Evapotranspiration from U**.
The surface store loses water to actual evapotranspiration, limited by both the available water and the PET demand scaled by the filling ratio.
Any unmet PET demand is passed to the deep soil reservoir Z in step 5.

**Step 4: Infiltration from surface runoff to L**.
A portion of the surface runoff $V_S$ infiltrates into the intermediate reservoir L.
The infiltration rate depends on the remaining capacity in L: $A_L = \max(0,\, X_6 - L) \cdot \max(0,\, 1 - L/X_6)$.

**Step 5: Intermediate drainage and deep reservoir dynamics**.
L drains linearly at rate $V_L = L/X_2$.
This drainage is partitioned using the Z filling ratio $Z/Z_{max}$: a fraction goes to deep percolation into Z, 20% of the Z-proportional remainder goes to rapid underground runoff, and the remaining 80% recharges groundwater (N).
The deep reservoir Z is then updated: it receives percolation, loses residual evapotranspiration (from any unmet surface PET), and is capped at 90 mm.

**Step 6: Groundwater discharge**.
The groundwater reservoir N drains through a nonlinear cubic law: $V_N = \min(N,\, (N/X_3)^3)$.
This produces slow, recession-dominated baseflow that only becomes significant when N accumulates enough water.

**Step 7: UH2 routing and streamflow assembly**.
The three flow components — net surface runoff $(V_S - A_L)$, rapid underground runoff, and slow groundwater discharge — are each independently convolved through UH2 (time base $2 X_4$, exponent 2.5).
Total streamflow at each time step is the sum of the three routed components, floored at zero.

## Parameters

The MORDOR model has 6 calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ | Rain correction coefficient | 0.5–2.0 | - | Multiplicative scaling of observed precipitation. Values below 1.0 reduce rainfall (gauge overcatch or interception loss); values above 1.0 increase it (gauge undercatch). |
| $X_2$ | Emptying constant of reservoir L | 1–1000 | days | Time constant for linear drainage of the intermediate store. Larger values slow the release of infiltrated water, broadening the recession. |
| $X_3$ | Emptying constant of reservoir N | 0.01–100 | - | Controls the nonlinear (cubic) drainage of the groundwater store. Larger values reduce groundwater discharge, extending low-flow recession. |
| $X_4$ | Response time of UH2 | 0.5–10 | days | Half the time base of the double-sided unit hydrograph. Larger values spread the flow peak over a longer period. |
| $X_5$ | Capacity of reservoir U | 1–1000 | mm | Maximum surface store capacity. Controls how much rainfall can be absorbed before overflow occurs. |
| $X_6$ | Capacity of reservoir L | 1–1000 | mm | Maximum intermediate store capacity. Controls how much infiltrated water can be stored before saturating. |

**Understanding the parameters:**

- **$X_1$** usually calibrates close to 1.0 (within 0.8–1.2). Values far from 1.0 may indicate issues with the precipitation input data rather than genuine catchment properties.
- **$X_2$** and $X_3$ together control the recession curve shape. $X_2$ governs the intermediate timescale (days to weeks), while $X_3$ governs the slowest component (weeks to months). Start calibration by adjusting $X_2$ to match the falling limb of the hydrograph, then tune $X_3$ to match low-flow periods.
- **$X_4$** controls the smoothness and timing of the hydrograph peak. Small catchments with flashy response typically need $X_4 \approx 1$; larger catchments with slow routing need higher values.
- **$X_5$** determines how quickly a catchment "saturates" and begins producing proportional runoff. Low $X_5$ makes the model flashy; high $X_5$ means more rainfall is absorbed before runoff generation becomes significant.

## Mathematical Formulation

### Initialization

Reservoir states at $t = 0$:

$$U_0 = \frac{X_5}{2}, \quad L_0 = \frac{X_6}{2}, \quad Z_0 = 50, \quad N_0 = 0.5$$

The constant $Z_{max} = 90$ mm is the fixed capacity of the deep soil reservoir (not calibratable).

### Rain Correction

$$P_L = P \cdot X_1$$

### Rainfall Partitioning

Direct runoff is proportional to U filling:

$$DTR_1 = P_L \cdot \frac{U}{X_5}$$

The remainder enters U:

$$DTU_1 = P_L - DTR_1$$

Surface runoff includes both direct runoff and any overflow:

$$V_S = DTR_1 + \max(0,\, U + DTU_1 - X_5)$$

$$U \leftarrow \min(U + DTU_1,\, X_5)$$

### Surface Evapotranspiration

$$E_U = \min\!\left(U,\, X_5,\, \max\!\left(0,\, E \cdot \frac{U}{X_5}\right)\right)$$

$$U \leftarrow U - E_U$$

### Infiltration to L

$$A_L = \min\!\left(\max(0,\, X_6 - L),\, V_S \cdot \max\!\left(0,\, 1 - \frac{L}{X_6}\right)\right)$$

$$L \leftarrow L + A_L$$

### Intermediate Drainage (L)

$$V_L = \frac{L}{X_2}$$

$$L \leftarrow L - V_L$$

### Deep Soil Reservoir (Z) and Flow Partitioning

The Z filling ratio determines how L drainage is distributed:

$$z_r = \frac{Z}{Z_{max}}$$

$$DTZ = V_L \cdot (1 - z_r) \quad \text{(percolation to Z)}$$

$$RUR = 0.2 \cdot V_L \cdot z_r \quad \text{(rapid underground runoff)}$$

$$A_N = 0.8 \cdot V_L \cdot z_r \quad \text{(groundwater recharge)}$$

Z is updated with percolation, residual evapotranspiration, and capping:

$$Z \leftarrow Z + DTZ$$

$$E_Z = \min\!\left(Z,\, (E - E_U)^+ \cdot \frac{Z}{Z_{max}}\right)$$

$$Z \leftarrow \max\!\left(0,\, \min(Z - E_Z,\, Z_{max})\right)$$

where $(x)^+ = \max(0, x)$.

### Groundwater Discharge (N)

$$N \leftarrow N + A_N$$

$$V_N = \min\!\left(N,\, \left(\frac{N}{X_3}\right)^3\right)$$

$$N \leftarrow \max(0,\, N - V_N)$$

### Unit Hydrograph UH2

The UH2 is a double-sided unit hydrograph with time base $2 X_4$ and exponent 2.5.
Its S-curve is:

$$SH_2(t) = \begin{cases}
0 & \text{if } t \leq 0 \\
\frac{1}{2}\left(\frac{t}{X_4}\right)^{2.5} & \text{if } 0 < t \leq X_4 \\
1 - \frac{1}{2}\left(2 - \frac{t}{X_4}\right)^{2.5} & \text{if } X_4 < t \leq 2X_4 \\
1 & \text{if } t > 2X_4
\end{cases}$$

The UH2 weights are the finite differences of the S-curve:

$$UH_2(j) = SH_2(j) - SH_2(j-1), \quad j = 1, \ldots, \lceil 2 X_4 \rceil$$

### Total Streamflow

Each of the three flow components is independently convolved through a UH2 state vector, and the total streamflow is their sum:

$$Q(t) = \bigl[\text{UH2} * (V_S - A_L)^+\bigr](t) + \bigl[\text{UH2} * RUR\bigr](t) + \bigl[\text{UH2} * V_N\bigr](t)$$

with $Q(t) \geq 0$ enforced at each time step.

## References

- Garçon, R. (1999). Modèle global pluie-débit pour la prévision et la génération des crues. *La Houille Blanche*, 85(7-8), 88–95. [DOI](https://doi.org/10.1051/lhb/1999088)
- Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis). INPG, Grenoble. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
- Thiéry, D. (2014). Logiciel GARDÉNIA, version 8.2 — Guide d'utilisation. *Rapport final BRGM/RP-62797-FR*. (For comparison with the related EDF/BRGM modelling tradition.)
