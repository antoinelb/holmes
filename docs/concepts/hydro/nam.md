# NAM Model

## Overview

NAM (Nedbør-Afstrømnings-Model, "precipitation-runoff model" in Danish) is a ten-parameter daily lumped rainfall-runoff model originally developed by Nielsen and Hansen (1973) at the Technical University of Denmark.
It became one of the most widely used operational hydrological models in Scandinavia and is still distributed today as part of the DHI MIKE software suite, where it powers flood forecasting and water resources studies on hundreds of catchments around the world.

NAM represents the catchment as **seven reservoirs**: a surface storage $U$, a soil-moisture store $L$, two two-reservoir cascades for interflow and overland flow ($CK_1 \to CK_2$ and $CK_{1b} \to CK_{2b}$), and a groundwater store $GW$ that — unusually — is tracked as a *deficit* rather than as a stored volume.
Inputs are partitioned between three flow pathways (overland flow, interflow, baseflow) by piecewise rules driven by the soil filling ratio $L / X_7$, and the channel response is smoothed by a fractional-delay unit hydrograph.

The HOLMES implementation is a verbatim port of HOOPLA's HM12 step (Thiboult et al., 2020), which itself is the operational version studied in Perrin's thesis (fiche n°9): a richer ten-parameter formulation than the four-parameter NAM0 reduction also documented in the same thesis.
We chose this richer variant because it preserves NAM's structural distinction between overland flow and interflow, which is what makes it pedagogically interesting compared to HOLMES's simpler models.

Students typically choose NAM to study how a model with **a soil-moisture deficit groundwater store** and **explicit overland-flow vs. interflow separation** behaves under varying soil-moisture conditions, especially the way capillary rise from the deep aquifer "feeds back" into the soil store during dry periods.

## Key Concepts

- **Surface storage ($U$)**: A fast canopy-and-depression reservoir of capacity $X_9$ that intercepts rainfall, drains laterally as interflow, and evaporates at the full PET rate before any water reaches the soil. When $U$ overflows, the spill $PN$ enters the production phase.

- **Soil moisture store ($L$)**: The main moisture-accounting reservoir of capacity $X_7$. Its filling ratio $L / X_7$ controls every flow-partitioning decision in the model: the higher it is, the more water goes to overland flow and to deep percolation, the less stays in the soil.

- **Groundwater deficit ($GW$)**: NAM's defining feature. Unlike most rainfall-runoff models, $GW$ tracks how *empty* the deep aquifer is rather than how full. Recharge from the soil reduces $GW$, baseflow only switches on once $GW$ drops below the threshold $X_1$, and capillary rise from the saturated zone is driven by the *inverse* of $GW$.

- **Interflow cascade ($CK_1 \to CK_2$)**: A two-reservoir linear cascade with shared time constant $X_2$. Smooths the surface-extracted interflow $QIF$ before it reaches the channel, contributing the medium-speed component of the hydrograph.

- **Overland-flow cascade ($CK_{1b} \to CK_{2b}$)**: A second two-reservoir linear cascade, also with time constant $X_2$, that smooths the overland flow $QOF$. Two parallel cascades with the same time constant let NAM distinguish *where* water came from (surface saturation vs. interflow) without distinguishing *how fast* it travels.

- **Three-branch evapotranspiration**: After PET is debited from $U$, the model lands in one of three states: (a) $U$ still positive — no PET demand left over; (b) $U$ went negative — the unsatisfied demand $E_1$ is forwarded to the soil; (c) $U$ overflowed $X_9$ — the spill $PN$ feeds the production phase.

- **Capillary rise**: A small upward flux $caflu$ that moves water from the saturated zone back into the soil store. It is proportional to $\sqrt{1 - L/X_7}$ (the soil's *unsaturated* fraction) and to $(X_{10} / GW)^2$ (the *inverse-square* of the groundwater deficit), so it grows rapidly when both stores are dry. This is the only upward water transfer in NAM.

- **Fractional-delay unit hydrograph**: All four channel-bound fluxes ($BF + BF_1 + B_1 + B_2$) are summed and pushed through a shift-register of length $\lceil X_4 \rceil + 1$, identical in construction to the GR4J / SACRAMENTO delay mechanism, so a non-integer routing time $X_4$ translates to a smooth lag without per-step interpolation.

## How It Works

The NAM model processes rainfall and PET through the following steps in each daily time step:

**Step 1: Surface storage and interflow extraction**.
The rainfall $P$ is added to the surface store $U$.
The interflow $QIF = \min(U, \, (L/X_7) \cdot U / X_3)$ is then extracted; the soil filling ratio $L/X_7$ acts as a *gate* — when the soil is dry, very little interflow forms even if $U$ is full.
$QIF$ feeds the first interflow cascade reservoir $CK_1$, then propagates through $CK_2$ to produce the channel-bound interflow $B_2 = CK_2 / X_2$.

**Step 2: Three-branch evapotranspiration from $U$**.
PET $E$ is debited from $U$.
If $U$ stays in $[0, X_9]$, there is no residual demand.
If $U$ went negative, the unsatisfied demand $E_1 = -U$ is carried forward to the soil store.
If $U$ overflowed $X_9$, the surplus $PN = U - X_9$ enters the production phase below.

**Step 3: Overland-flow partitioning of the spill $PN$**.
When $PN > 0$, the spill is split into three components:
overland flow $QOF = PN \cdot (L / X_7) / X_8$,
groundwater recharge $G = (PN - QOF) \cdot (L/X_7 - X_5) / (1 - X_5)$ — only when the soil is wetter than the percolation threshold $X_5$,
and soil-store recharge $DL_0 = PN - QOF - G$.
A bookkeeping subtlety: when $DL_0$ would push the soil store above its capacity $X_7$, the surplus is forced into $G$ but $DL_0$ itself is *not* decremented; the explicit clip $L \leftarrow \min(L, X_7)$ later restores mass conservation.

**Step 4: Overland-flow cascade**.
The overland flow $QOF$ feeds $CK_{1b}$, which propagates through $CK_{2b}$, producing the channel-bound overland flow $B_1 = CK_{2b} / X_2$.

**Step 5: Soil-moisture update**.
The soil store receives $DL_0$ from Step 3 and is then evaporated by the carried-over surface deficit $E_1$, scaled by the filling ratio: $L \leftarrow \max(0, \, L - E_1 \cdot L / X_7)$.
This water-limited form prevents a very dry soil from being driven negative by an unsatisfied PET demand.

**Step 6: Groundwater deficit update and baseflow**.
$GW$ first absorbs the recharge $G$ (which *reduces* the deficit because $GW$ is sign-flipped).
If the new deficit drops below the threshold $X_1$, baseflow $BF = (X_1 - GW) / X_6$ switches on and closes the gap toward $X_1$ over the time constant $X_6$.
If baseflow would drive $GW$ to or below zero — which would later cause the capillary-rise term to divide by zero — an emergency reset $BF_1$ flushes the surplus and clamps $GW$ to a small positive floor.

**Step 7: Capillary rise**.
A small upward flux $caflu = \sqrt{1 - L/X_7} \cdot (X_{10} / GW)^2$ moves water from the saturated zone back into the soil store, capped at the soil's free capacity $X_7 - L$.
$caflu$ is added to $L$ and *also* to $GW$ (deficit grows again as water leaves the aquifer).
This is the only upward water transfer in the model.

**Step 8: Channel routing**.
The four channel-bound fluxes are summed as $Q = BF + BF_1 + B_1 + B_2$ and pushed through the fractional-delay shift register $\{HY_k\}$ of length $n = \lceil X_4 \rceil + 1$.
The first element of the register is returned (clamped at zero) as the simulated streamflow for the current time step.

## Parameters

The NAM model has ten calibratable parameters.

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|:-----:|-------|------------------------|
| $X_1$ | Groundwater baseflow threshold | 1–1000 | mm | The soil-moisture deficit at which baseflow switches on. When $GW$ drops below this value, the aquifer starts releasing water. |
| $X_2$ | Routing reservoir time constant | 1–100 | days | Shared time constant of the four cascade reservoirs ($CK_1$, $CK_2$, $CK_{1b}$, $CK_{2b}$). Controls how much smoothing is applied to both interflow and overland flow. |
| $X_3$ | Interflow time constant | 1–100 | days | Damps the interflow extraction $QIF = (L/X_7) \cdot U / X_3$. Larger values starve the interflow pathway and shift more water to overland flow or percolation. |
| $X_4$ | Routing delay | 0.5–10 | days | Fractional delay applied to total channel inflow through the unit hydrograph. Pure timing parameter — does not affect hydrograph shape. |
| $X_5$ | Soil percolation threshold | 0.01–0.99 | - | Soil filling ratio above which groundwater recharge $G$ activates. Below this, all spill water stays in the surface and overland-flow cascades. |
| $X_6$ | Baseflow time constant | 1–500 | days | Recession time constant of the groundwater store. Larger values give long, slow baseflow recessions. |
| $X_7$ | Soil reservoir capacity | 1–1000 | mm | Storage capacity of the soil-moisture store $L$. Most other parameters scale via the filling ratio $L / X_7$, so this parameter is the *master scale* of the production phase. |
| $X_8$ | Overland flow time constant | 1–100 | days | Damps the overland-flow extraction $QOF = (L/X_7) \cdot PN / X_8$. Larger values shift water from overland flow to either groundwater recharge or soil storage. |
| $X_9$ | Surface reservoir capacity | 1–1000 | mm | Storage capacity of the surface store $U$. Acts as an interception threshold: rainfall less than $X_9$ never reaches the production phase. |
| $X_{10}$ | Capillary rise scale | 0.01–10 | mm | Numerator of the capillary-rise driver $(X_{10}/GW)^2$. Larger values produce stronger upward flux during dry spells. |

**Understanding the parameters:**

- **$X_7$ is the master scale of the model**. Almost every flow-partitioning rule depends on the filling ratio $L / X_7$, so the calibrated value of $X_7$ implicitly sets the moisture-related sensitivities. Typical Perrin-calibrated values fall in the 100–500 mm range; below 50 mm the model is hyper-reactive, above 800 mm it becomes sluggish.

- **$X_1$ and $X_6$ together shape baseflow**. $X_1$ sets *when* baseflow turns on (the deficit threshold), while $X_6$ sets *how fast* it recedes. A small $X_1$ with a large $X_6$ produces a delayed but very long baseflow tail; a large $X_1$ with a small $X_6$ gives a quick, sharp baseflow response. Use the observed recession constant of the catchment as a starting point for $X_6$.

- **$X_3$ vs. $X_8$ controls the interflow-vs.-overland-flow balance**. Both pathways are gated by the same filling ratio, so the relative magnitudes of $X_3$ and $X_8$ decide which one dominates. A small $X_3$ and a large $X_8$ make the model interflow-dominated; the reverse makes it overland-flow-dominated.

- **$X_5$ is the percolation switch**. Below this soil filling ratio, *no* groundwater recharge takes place — all production-phase water cascades through the surface pathways. Catchments with shallow aquifers often calibrate to a low $X_5$ (always recharging), while karstic or impermeable catchments calibrate to a high $X_5$.

- **$X_4$ should be calibrated last**, after the other parameters have produced a hydrograph of the right *shape*. It only affects the timing of the response, not its magnitude or recession structure.

- **$X_{10}$ is usually small**. The capillary-rise term enters as $(X_{10}/GW)^2$, so even modest values produce a meaningful upward flux when the aquifer is dry. Calibrated values are typically below 2 mm; values above 5 mm tend to over-feed the soil during dry spells and degrade summer baseflow performance.

## Mathematical Formulation

### Initialization

Initial reservoir states (from HOOPLA's `ini_HydroMod12.m`):

$$U_0 = X_9, \quad L_0 = \frac{X_7}{2}, \quad GW_0 = 50 \ \text{mm}$$

$$CK_{1,0} = CK_{2,0} = CK_{1b,0} = CK_{2b,0} = 0$$

The fractional-delay routing array $\{DL_k\}$ has length $n = \lceil X_4 \rceil + 1$ and only its last two entries are non-zero:

$$DL_{n-2} = \frac{1}{X_4 - n + 3}, \quad DL_{n-1} = 1 - DL_{n-2}$$

This represents a non-integer delay of $X_4$ days as a two-element stencil at the tail of an otherwise-empty array. The unit hydrograph register $\{HY_k\}$ starts at zero in every cell.

### Surface Reservoir and Interflow

Add rainfall, then extract interflow gated by the soil filling ratio:

$$U \leftarrow U + P$$

$$QIF = \min\left(U, \ \frac{L}{X_7} \cdot \frac{U}{X_3}\right), \quad U \leftarrow U - QIF$$

Interflow propagates through the two-reservoir cascade $CK_1 \to CK_2$:

$$CK_1 \leftarrow CK_1 + QIF, \quad B_{21} = \frac{CK_1}{X_2}, \quad CK_1 \leftarrow CK_1 - B_{21}$$

$$CK_2 \leftarrow CK_2 + B_{21}, \quad B_2 = \frac{CK_2}{X_2}, \quad CK_2 \leftarrow CK_2 - B_2$$

### Three-Branch Evapotranspiration from $U$

Debit PET, then branch on the resulting state of $U$:

$$U \leftarrow U - E$$

$$
(E_1, PN) =
\begin{cases}
(0, 0) & \text{if } 0 \le U \le X_9 \\
(-U, \, 0); \ U \leftarrow 0 & \text{if } U < 0 \\
(0, \, U - X_9); \ U \leftarrow X_9 & \text{if } U > X_9
\end{cases}
$$

Only one of $E_1$ or $PN$ can be non-zero in any given time step.

### Overland-Flow Partitioning of the Spill

When the surface store overflows ($PN > 0$), partition the spill into overland flow, groundwater recharge, and soil-store recharge:

$$QOF = PN \cdot \frac{L}{X_7} \cdot \frac{1}{X_8}$$

$$G =
\begin{cases}
(PN - QOF) \cdot \dfrac{L/X_7 - X_5}{1 - X_5} & \text{if } L/X_7 > X_5 \\
0 & \text{otherwise}
\end{cases}$$

$$DL_0 = PN - QOF - G$$

If $DL_0 > X_7$, the surplus is added to $G$ (without decrementing $DL_0$ — the over-fill is corrected later by an explicit clip on $L$):

$$\text{if } DL_0 > X_7: \quad G \leftarrow G + (DL_0 - (X_7 - L))$$

### Overland-Flow Cascade

The overland flow propagates through the second two-reservoir cascade $CK_{1b} \to CK_{2b}$:

$$CK_{1b} \leftarrow CK_{1b} + QOF, \quad B_{12} = \frac{CK_{1b}}{X_2}, \quad CK_{1b} \leftarrow CK_{1b} - B_{12}$$

$$CK_{2b} \leftarrow CK_{2b} + B_{12}, \quad B_1 = \frac{CK_{2b}}{X_2}, \quad CK_{2b} \leftarrow CK_{2b} - B_1$$

### Soil Moisture Store

Recharge, then evaporate the residual surface deficit, scaled by the filling ratio and clamped to zero:

$$L \leftarrow L + DL_0$$

$$L \leftarrow \max\!\left(0, \ L - E_1 \cdot \frac{L}{X_7}\right)$$

### Groundwater Deficit and Baseflow

Recall that $GW$ is a *deficit*: subtracting recharge $G$ makes the aquifer wetter.

$$GW \leftarrow GW - G$$

Baseflow switches on when the deficit drops below the threshold $X_1$:

$$BF =
\begin{cases}
\dfrac{X_1 - GW}{X_6} & \text{if } GW \le X_1 \\
0 & \text{otherwise}
\end{cases}, \quad GW \leftarrow GW + BF$$

If baseflow would drive $GW \le 0$, an emergency reset releases the surplus and clamps the deficit to a small positive floor:

$$BF_1 =
\begin{cases}
-GW + 0.1; \ GW \leftarrow 0.1 & \text{if } GW \le 0 \\
0 & \text{otherwise}
\end{cases}$$

### Soil Cap and Capillary Rise

Restore mass conservation by clipping the soil store at its capacity:

$$L \leftarrow \min(L, X_7)$$

Capillary rise from the aquifer into the soil, capped at the soil's free capacity:

$$caflu = \min\!\left(\sqrt{1 - L/X_7} \cdot \left(\frac{X_{10}}{GW}\right)^2, \ X_7 - L\right)$$

$$L \leftarrow L + caflu, \quad GW \leftarrow GW + caflu$$

### Total Streamflow and Fractional Delay

The four channel-bound fluxes are summed:

$$Q = BF + BF_1 + B_1 + B_2$$

The unit-hydrograph register $\{HY_k\}$ of length $n = \lceil X_4 \rceil + 1$ advances by one step and adds the new contribution:

$$HY_k \leftarrow HY_{k+1} + DL_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n-2$$

$$HY_{n-1} \leftarrow DL_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0, \ HY_0)$$

The first element of the register is returned as the simulated streamflow for the current time step; the rest of the register is shifted on the next call.

## References

Nielsen, S. A., & Hansen, E. (1973).
Numerical simulation of the rainfall-runoff process on a daily basis.
*Nordic Hydrology*, 4(3), 171–190.
[https://doi.org/10.2166/nh.1973.0013](https://doi.org/10.2166/nh.1973.0013)

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°9 (NAM).

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
