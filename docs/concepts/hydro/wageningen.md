# WAGENINGEN Model

## Overview

WAGENINGEN is an eight-parameter daily lumped rainfall-runoff model developed by Warmerdam, Kole, and Chormanski (1997) at Wageningen Agricultural University in the Netherlands.
It was designed as a parsimonious conceptual model suited to humid-temperate catchments and operational forecasting.

The variant implemented in HOLMES is the HOOPLA HM19 port described in Annex 1 of Perrin (2000).
The model represents the catchment as **three reservoirs in a production–routing chain**: a soil reservoir $S$ that controls evapotranspiration and percolation, a slow sub-intermediate reservoir $T$ that can feed water back up to $S$ by capillary rise, and a fast surface reservoir $R$ — both routing stores drain through a common fractional-delay unit hydrograph.

The defining feature of WAGENINGEN is the **threshold-based split** at soil-moisture level $X_1$.
When $S \geq X_1$, the soil is wet enough to drain to the routing system and evapotranspires at the full atmospheric demand; when $S < X_1$, percolation stops, capillary rise transfers water upward from $T$, and evapotranspiration follows a cosine envelope that tapers smoothly toward zero as the soil dries.
This gives a pedagogically useful illustration of how a single wetness threshold can generate four coupled process regimes (drainage, capillary rise, full ET, suppressed ET) without introducing additional calibration parameters.

## Key Concepts

- **Soil-moisture threshold $X_1$**: The single wetness level that switches the model between a wet regime (percolation active, ET unrestricted) and a dry regime (percolation off, capillary rise from $T$ into $S$ active, ET damped).

- **Cosine-envelope evapotranspiration**: Below the threshold, actual ET is scaled by $\cos\!\bigl((\pi/2)\cdot(X_1 - S)/X_1\bigr)$.
This produces a smooth, concave taper from full atmospheric demand at $S = X_1$ down to zero at $S = 0$ — gentler than a linear reduction and numerically stable.

- **Capillary rise $I_t$**: When $S < X_1$, water moves *upward* from the slow reservoir $T$ into $S$ at a rate proportional to both the storage in $T$ and the soil-moisture deficit $(X_1 - S)$.
This is the only HOLMES model that represents capillary rise explicitly.

- **Flow dissociation via $\mathrm{DIV} = \min(1, T/X_5)$**: The ratio of storage in $T$ to the dissociation threshold $X_5$ decides the split of percolation $I_s$ between fast and slow routing — when $T$ is full the slow path saturates and everything goes fast; when $T$ is empty all percolation goes slow to refill it.

- **Fast reservoir $R$**: Linear routing store with time constant $X_6$, producing storm-event peaks.

- **Slow reservoir $T$**: Linear routing store with time constant $X_6 \cdot X_7$ (with $X_7 \geq 1$), producing sustained baseflow.
The same store supplies capillary rise into $S$.

- **Fractional-delay routing**: A pure channel delay $X_8$ (in days) shifts the combined hydrograph, interpolating between the two adjacent integer delays.

## How It Works

**Step 1: Soil-moisture update**.
Precipitation $P$ is added to the soil reservoir: $S \leftarrow S + P$.
The current value of $S$ relative to the threshold $X_1$ determines which of the two regimes applies for the rest of the step.

**Step 2: Percolation or capillary rise**.
If $S \geq X_1$, percolation drains the soil: $I_s = (S/X_2) \cdot (S - X_1)/X_3$, and no capillary rise occurs.
If $S < X_1$, percolation stops and capillary rise lifts water from $T$ back to $S$: $I_t = (T/X_4) \cdot (X_1 - S)$.
The soil reservoir is then updated: $S \leftarrow S + I_t - I_s$.

**Step 3: Evapotranspiration**.
Above the threshold, actual ET equals the demand: $E_s = E$.
Below the threshold, ET is damped by a cosine envelope: $E_s = E \cdot \cos\!\bigl((\pi/2)\cdot(X_1 - S)/X_1\bigr)$.
The soil storage is updated and clamped at zero: $S \leftarrow \max(0, S - E_s)$.

**Step 4: Flow dissociation**.
The percolated water $I_s$ is split between the two routing reservoirs by the dissociation ratio $\mathrm{DIV} = \min(1, T/X_5)$.
A fraction $\mathrm{DIV} \cdot I_s$ goes to the fast reservoir $R$ and the remainder $(1 - \mathrm{DIV}) \cdot I_s$ goes to the slow reservoir $T$.
When $T$ is near empty, the slow path absorbs most flux; when $T$ is well-filled, the fast path dominates.

**Step 5: Linear routing**.
Both routing reservoirs drain with linear-reservoir laws.
The fast reservoir empties with time constant $X_6$: $Q_r = R/X_6$.
The slow reservoir empties with time constant $X_6 \cdot X_7$: $Q_t = T/(X_6 \cdot X_7)$.
Since $X_7 \geq 1$, the slow reservoir is always at least as slow as the fast one.

**Step 6: Delay routing**.
The combined outflow $Q_r + Q_t$ is injected into the fractional-delay register of size $\lceil X_8 \rceil + 1$.
The register shifts by one step each day, and the first element, clamped at zero, is returned as simulated streamflow.

## Parameters

The WAGENINGEN model has eight calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|:-----:|-------|------------------------|
| $X_1$ | Percolation/ET threshold | 1–500 | mm | Soil-moisture level above which percolation activates and ET runs unrestricted. Acts as the "field capacity" of the model — the higher it is, the larger the storage the catchment must build before generating runoff. |
| $X_2$ | Soil reservoir characteristic capacity | 10–2000 | mm | Appears in the denominator of the percolation rate. Larger values slow the drainage of the soil store and favor sustained moisture. |
| $X_3$ | Infiltration emptying constant | 0.1–1000 | mm | Second denominator in the percolation rate. Together with $X_2$ it controls how rapidly the soil drains above threshold. |
| $X_4$ | Capillary rise constant | 1–1000 | d | Time-constant analogue for the upward flux from $T$ to $S$. Smaller values produce faster capillary recovery from drought. |
| $X_5$ | Flow dissociation threshold | 0.1–500 | mm | Storage level in $T$ at which the slow path saturates and all percolation goes fast. Small values make the model flash-prone; large values favor groundwater storage. |
| $X_6$ | Fast-reservoir time constant | 0.5–50 | d | Residence time of $R$. Controls storm recession speed. |
| $X_7$ | Slow/fast time-constant ratio | 1–50 | - | Multiplicative factor: slow-reservoir time constant is $X_6 \cdot X_7$. Constrained $\geq 1$ so the slow path is genuinely slower than the fast path. |
| $X_8$ | Routing delay | 0.5–5 | d | Pure channel travel-time shift applied at the outlet. |

**Understanding the parameters:**

- **$X_1$ is the single most sensitive parameter.**
It sets the wet/dry regime boundary: too low and the model almost always percolates and evaporates at full rate (linear-reservoir behavior); too high and the soil never drains (all precipitation lost to ET).
Expect calibrated values between 50 and 200 mm on humid catchments.
- **$X_2$ and $X_3$ jointly scale the percolation rate** via $(S/X_2) \cdot (S - X_1)/X_3$.
Because they appear multiplicatively in a denominator, they are strongly equifinal — increasing one and decreasing the other gives the same drainage, so calibration typically fixes their ratio rather than each individually.
- **$X_5$ controls flashiness**.
If $T$ oscillates around $X_5$, small changes in $T$ can swing $\mathrm{DIV}$ from 0 to 1 and cause the model to suddenly dump percolation into the fast reservoir.
Values well above the typical $T$ storage produce a mostly-slow response; values far below give a mostly-fast response.
- **$X_6$ and $X_7$** are the routing knobs.
$X_6$ sets the fast recession timescale (typical catchment storm recessions are 2–10 days) and $X_7$ lengthens the slow path (baseflow recession over weeks to months implies $X_7 \approx 10$–$30$).
- **Capillary rise $X_4$** is only active in the dry regime.
On catchments with a persistently wet soil ($S \geq X_1$ most of the time), $X_4$ barely moves the objective function — expect weak identifiability.

## Mathematical Formulation

### Initialization

Fixed reservoir states at $t = 0$ (from HOOPLA `ini_HydroMod19.m`):

$$S_0 = 30 \text{ mm}, \quad R_0 = 0 \text{ mm}, \quad T_0 = 200 \text{ mm}$$

The fractional-delay register $\{H_k\}$ has $n = \lceil X_8 \rceil + 1$ elements, initialized to zero, with weights:

$$d_{n-2} = \frac{1}{X_8 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}$$

### Soil Moisture Update

$$S \leftarrow S + P$$

### Percolation and Capillary Rise

Mutually exclusive fluxes depending on the threshold $X_1$:

$$
I_s =
\begin{cases}
\dfrac{S}{X_2} \cdot \dfrac{S - X_1}{X_3} & \text{if } S \geq X_1 \\
0 & \text{if } S < X_1
\end{cases}
$$

$$
I_t =
\begin{cases}
0 & \text{if } S \geq X_1 \\
\dfrac{T}{X_4} \cdot (X_1 - S) & \text{if } S < X_1
\end{cases}
$$

$$S \leftarrow S + I_t - I_s$$

### Evapotranspiration

$$
E_s =
\begin{cases}
E & \text{if } S \geq X_1 \\
E \cdot \cos\!\left(\dfrac{\pi}{2} \cdot \dfrac{X_1 - S}{X_1}\right) & \text{if } S < X_1
\end{cases}
$$

$$S \leftarrow \max(0,\; S - E_s)$$

### Flow Dissociation

$$\mathrm{DIV} = \min\!\left(1,\; \frac{T}{X_5}\right)$$

$$T \leftarrow T + (1 - \mathrm{DIV}) \cdot I_s$$

$$R \leftarrow R + \mathrm{DIV} \cdot I_s$$

### Linear Routing

$$Q_r = \frac{R}{X_6}, \quad R \leftarrow R - Q_r$$

$$Q_t = \frac{T}{X_6 \cdot X_7}, \quad T \leftarrow T - Q_t$$

### Delay Routing

$$Q = Q_r + Q_t$$

$$H_k \leftarrow H_{k+1} + d_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow d_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0,\; H_0)$$

## References

Warmerdam, P. M. M., Kole, J., & Chormanski, J. (1997).
Modelling rainfall-runoff processes in the Hupselse Beek research basin.
*IHP-V Technical Documents in Hydrology*, 14, 155–160. UNESCO, Paris.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°34 (WAGE), pp. 461–464.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
