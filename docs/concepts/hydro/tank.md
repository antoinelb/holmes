# TANK Model

## Overview

TANK is a conceptual rainfall-runoff model developed by Sugawara (1979) at the National Research Center for Disaster Prevention in Japan and has since become one of the most widely used operational models in East Asia.
The version implemented in HOLMES follows Perrin's seven-parameter "version retenue" (Perrin, 2000, fiche n°31), catalogued as HM17 in the HOOPLA framework.

The model represents a catchment as a vertical cascade of four linear reservoirs — surface ($S$), upper soil ($R$), lower soil ($T$), and groundwater ($L$) — each draining into the next through a fixed bottom outlet.
The surface reservoir carries two additional side outlets that only activate once its storage exceeds calibrated thresholds, allowing the model to represent a sharp flow response once the soil becomes sufficiently wet.
Outflows from all four reservoirs are aggregated and routed through a fractional unit-delay filter before reaching the outlet.

TANK is conceptually simple but surprisingly expressive: the geometric scaling of drain time constants ($x_3$, $x_3 x_4$, $x_3 x_4 x_7$, $x_3 x_4 x_7^2$) creates a natural separation of fast, intermediate, slow, and very-slow flow components without any explicit flow-partitioning equation.
This makes TANK a good pedagogical counterpoint to models like GR4J (which splits flow explicitly) or HYMOD (which distributes runoff through a Pareto law): in TANK, flow separation emerges from storage dynamics alone.

## Key Concepts

- **Surface reservoir ($S$)**: The uppermost store receiving all precipitation.
Unlike the three reservoirs below it, $S$ has two side outlets that only activate when storage exceeds $x_1 + x_2$ (upper threshold) and $x_2$ (lower threshold), producing quickflow during wet episodes.

- **Upper soil reservoir ($R$)**: Receives the bottom drainage of $S$.
Has one side outlet at threshold $x_2$ and one bottom outlet; drains on an intermediate timescale controlled by the product $x_3 x_4$.

- **Lower soil reservoir ($T$)**: Receives the bottom drainage of $R$.
Has one side outlet at threshold $x_2$ and one bottom outlet; drains on a slow timescale controlled by $x_3 x_4 x_7$.

- **Groundwater reservoir ($L$)**: The deepest store, with no side outlet.
It drains purely through a single linear bottom outlet on the very slow timescale $x_3 x_4 x_7^2$, producing the longest baseflow recession.

- **Dual-threshold side outlets**: The surface reservoir is unique in having two side outlets. The upper outlet (threshold $x_1 + x_2$) produces intense peaks during storms; the lower outlet (threshold $x_2$) produces moderate quickflow during wet spells.

- **Geometric time-constant scaling**: All four bottom drains share the base constant $x_3$, successively multiplied by $x_4$, $x_7$, and $x_7$ again. This produces a physically motivated hierarchy of recession timescales without requiring separate calibration of each.

- **Cascading evapotranspiration**: PET demand (corrected by $x_6$) is satisfied top-down — first from $S$, then any unmet demand flows to $R$, then $T$, then $L$. Deeper reservoirs only lose water to ET after all shallower ones are dry.

- **Fractional unit-delay routing**: The sum of the five outflows (two side outlets on $S$, three bottom outlets on $R$, $T$, $L$) is passed through a fractional-delay filter of length $\lceil x_5 \rceil + 1$. Non-integer values of $x_5$ split the mass between two adjacent time steps.

## How It Works

**Step 1: PET correction**.
The incoming PET $E$ is multiplied by the correction coefficient $x_6$ to obtain the effective PET demand $E_1 = E \cdot x_6$.
Values of $x_6 < 1$ reduce the demand (common when PET is from Oudin or Penman formulas that slightly overestimate evaporation); values near 1 leave it unchanged.

**Step 2: Surface reservoir update and threshold outflows**.
All precipitation enters $S$.
If $S$ exceeds the upper threshold $x_1 + x_2$, the excess drains as $Q_{s1}$ at rate $1/x_3$.
If the remaining $S$ still exceeds the lower threshold $x_2$, a second side outflow $Q_{s2}$ drains at the same rate.
Finally, a bottom drainage $I_s = S / x_3$ feeds the next reservoir.

**Step 3: ET satisfaction from $S$ and cascade to $R$**.
ET is taken from $S$ up to its available water; any unmet demand $E_2 = E_1 - E_S$ is passed to $R$.
Water infiltrating from $S$'s bottom ($I_s$) enters $R$.
$R$ has one side outlet at threshold $x_2$ draining at rate $1/(x_3 x_4)$, one bottom outlet at the same rate, and an ET term satisfying residual demand.

**Step 4: Cascade through $T$**.
Bottom drainage from $R$ ($I_r$) enters $T$.
$T$ has the same structure as $R$ (one side outlet at threshold $x_2$, one bottom outlet) but with a slower time constant $1/(x_3 x_4 x_7)$.
ET residuals cascade to $E_3 = E_2 - E_R$.

**Step 5: Groundwater dynamics in $L$**.
Bottom drainage from $T$ ($I_t$) enters $L$.
Unlike the three reservoirs above, $L$ has no side outlet — only a single linear bottom drain at rate $1/(x_3 x_4 x_7^2)$.
Residual ET is then taken from $L$.

**Step 6: Fractional-delay routing**.
The five outflows ($Q_{s1}$, $Q_{s2}$, $Q_r$, $Q_t$, $Q_l$) are summed and passed through a unit-delay filter of length $\lceil x_5 \rceil + 1$.
When $x_5$ is non-integer, the filter splits the flow mass between two adjacent time steps, allowing sub-daily delay resolution.
The first element of the delay buffer is the simulated streamflow, clamped at zero.

## Parameters

The TANK model has 7 calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $x_1$ | Upper outflow threshold of $S$ | 1–1000 | mm | Storage level above which the upper side outlet of the surface reservoir activates. Controls when flashy storm-peak quickflow begins. |
| $x_2$ | Lower outflow threshold | 1–1000 | mm | Storage level above which the lower side outlet of $S$ (and the side outlets of $R$, $T$) activate. Controls the onset of moderate quickflow. |
| $x_3$ | Fast emptying constant | 1–100 | days | Base time constant for all bottom drains. Larger values slow every reservoir proportionally. |
| $x_4$ | Intermediate emptying multiplier | 1–100 | – | Multiplier applied to $x_3$ to obtain the $R$ and $T$ drain time constants. Larger values lengthen intermediate recession. |
| $x_5$ | Delay | 0.5–5 | days | Length of the fractional-delay filter; controls the lag between rainfall and streamflow peak. |
| $x_6$ | PET correction coefficient | 0.1–2 | – | Multiplicative correction applied to the forcing PET. Compensates for systematic bias in the PET formula. |
| $x_7$ | Slow emptying multiplier | 1–100 | – | Multiplier applied to $x_3 x_4$ to obtain the $T$ drain time constant, and squared for the $L$ drain. Large values produce long baseflow recessions. |

**Understanding the parameters:**

- **$x_1$ and $x_2$** together control how "flashy" the catchment response looks. Low $x_2$ means the catchment produces quickflow easily (typical of wet temperate catchments); high $x_1$ means only large storms trigger the upper outlet (typical of dry or deep-soil catchments). Because the upper threshold sums both ($x_1 + x_2$), calibrating $x_2$ first and then $x_1$ is usually more stable.
- **$x_3$, $x_4$, $x_7$** jointly determine the full recession behaviour from days to months. Start with $x_3 \approx 10$ (typical daily-model fast recession), adjust $x_4$ to match mid-recession timescales, and tune $x_7$ last to fit baseflow.
- **$x_5$** is almost always small (0.5–2 days) for daily models; calibrating it much higher usually indicates an upstream routing issue or data shift rather than a genuine catchment property.
- **$x_6$** should calibrate close to 1.0 if the PET input is reasonable. Systematic values far from 1.0 (below 0.5 or above 1.5) often signal a mis-matched PET formula or incorrect temperature input.
- The quadratic scaling of $L$'s drain through $x_7^2$ means that small changes in $x_7$ have disproportionately large effects on low-flow behaviour. Calibrate $x_7$ last and monitor low-flow indices carefully.

## Mathematical Formulation

### Initialization

All four reservoirs start at 10 mm (HOOPLA HM17 convention):

$$S_0 = R_0 = T_0 = L_0 = 10 \text{ mm}$$

### PET Correction and Surface Reservoir

$$S \leftarrow S + P, \qquad E_1 = E \cdot x_6$$

Upper-threshold side outflow:

$$Q_{s1} = \max\!\left(0,\; \frac{S - (x_1 + x_2)}{x_3}\right), \qquad S \leftarrow S - Q_{s1}$$

Lower-threshold side outflow:

$$Q_{s2} = \max\!\left(0,\; \frac{S - x_2}{x_3}\right), \qquad S \leftarrow S - Q_{s2}$$

Bottom drainage to $R$:

$$I_s = \frac{S}{x_3}, \qquad S \leftarrow S - I_s$$

ET from $S$ and residual demand:

$$E_S = \min(E_1,\, S), \qquad S \leftarrow S - E_S, \qquad E_2 = E_1 - E_S$$

### Upper Soil Reservoir ($R$)

$$R \leftarrow R + I_s$$

$$Q_r = \max\!\left(0,\; \frac{R - x_2}{x_3 x_4}\right), \qquad R \leftarrow R - Q_r$$

$$I_r = \frac{R}{x_3 x_4}, \qquad R \leftarrow R - I_r$$

$$E_R = \min(E_2,\, R), \qquad R \leftarrow R - E_R, \qquad E_3 = E_2 - E_R$$

### Lower Soil Reservoir ($T$)

$$T \leftarrow T + I_r$$

$$Q_t = \max\!\left(0,\; \frac{T - x_2}{x_3 x_4 x_7}\right), \qquad T \leftarrow T - Q_t$$

$$I_t = \frac{T}{x_3 x_4 x_7}, \qquad T \leftarrow T - I_t$$

$$E_T = \min(E_3,\, T), \qquad T \leftarrow T - E_T, \qquad E_4 = E_3 - E_T$$

### Groundwater Reservoir ($L$)

The groundwater store has no side outlet — only a single linear bottom drain with the slowest time constant:

$$L \leftarrow L + I_t$$

$$Q_l = \frac{L}{x_3 x_4 x_7^2}, \qquad L \leftarrow L - Q_l$$

$$E_L = \min(E_4,\, L), \qquad L \leftarrow L - E_L$$

### Fractional-Delay Routing

Let $n = \lceil x_5 \rceil + 1$ and define the delay weights $d \in \mathbb{R}^n$ by:

$$d_{n-2} = \frac{1}{x_5 - n + 3}, \qquad d_{n-1} = 1 - d_{n-2}, \qquad d_i = 0 \text{ for } i < n-2$$

These two weights sum to 1 and split the outflow mass between two adjacent delay-buffer slots.
The total outflow to route is the sum of all five reservoir outlets:

$$Q_{\text{tot}} = Q_{s1} + Q_{s2} + Q_r + Q_t + Q_l$$

The delay buffer $HY$ is updated each time step by a left-shift plus a weighted injection:

$$HY_i \leftarrow HY_{i+1} + d_i \cdot Q_{\text{tot}}, \quad i = 0, \ldots, n-2$$

$$HY_{n-1} \leftarrow d_{n-1} \cdot Q_{\text{tot}}$$

### Total Streamflow

$$Q(t) = \max(0,\, HY_0(t))$$

## References

- Sugawara, M. (1979). Automatic calibration of the tank model. *Hydrological Sciences Bulletin*, 24(3), 375–388. [DOI](https://doi.org/10.1080/02626667909491876)
- Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis). INPG, Grenoble. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
- Sugawara, M. (1995). Tank model. In V. P. Singh (Ed.), *Computer Models of Watershed Hydrology* (pp. 165–214). Water Resources Publications, Colorado.
