# HBV Model

## Overview

HBV is a nine-parameter daily lumped rainfall-runoff model developed at the Swedish Meteorological and Hydrological Institute (SMHI) by Bergström and Forsman (1973) and refined throughout the 1980s and 1990s.
It became one of the most widely used operational hydrological models in Nordic and temperate regions thanks to its simplicity, its transparent reservoir-based structure, and its ability to handle both snow-dominated and rain-dominated catchments.

The variant implemented in HOLMES is **HBV0** as documented in Annex 1 of Perrin (2000) — a nine-parameter simplification of the full operational HBV in which the snow routine has been stripped out and only the land-phase water-balance components remain.
Effective precipitation (rain plus optional snowmelt from CemaNeige, if active) enters a single soil moisture store that produces runoff through a non-linear function of saturation.
The runoff then flows through a two-outflow intermediate reservoir (mimicking near-surface and subsurface pathways) and a linear baseflow reservoir, before being routed through a triangular unit hydrograph to account for channel travel time.
A key numerical feature is that the soil-moisture accounting is split into **five sub-steps per time step** to reduce integration error when the soil is near saturation and the non-linear production function is stiff.

## Key Concepts

- **Non-linear soil production function**: The fraction of incoming rainfall that contributes to runoff at each sub-step is $(S/X_1)^{X_7}$, where $S$ is the current soil moisture and $X_1$ is the soil capacity.
When $S \ll X_1$ almost no runoff is generated and rainfall simply recharges the soil; when $S$ approaches $X_1$ nearly all rainfall runs off.
The exponent $X_7$ (the $\beta$ parameter in classical HBV literature) controls how quickly the transition happens — higher values produce a sharper, more threshold-like response.

- **Sub-step splitting for numerical stability**: Because the production function is highly non-linear, integrating a full daily precipitation pulse in one step can overshoot the soil capacity and misrepresent saturation.
HBV0 therefore divides each day into five equal sub-steps, applies one-fifth of the rain and ET in each, and accumulates the resulting runoff.
This implicit higher-order integration is cheap and significantly improves water balance during heavy rain days.

- **PET threshold**: Evapotranspiration is scaled by the ratio $S/X_2$, where $X_2$ is a threshold parameter (the $LP$ parameter in classical HBV).
When the soil is above the threshold the scaling factor is near 1 and evaporation proceeds at near-potential rate; below the threshold ET decreases linearly with soil moisture, mimicking plant stress under water limitation.

- **Two-outflow intermediate reservoir**: Instead of a single linear reservoir, HBV0 uses an intermediate store $R$ with two distinct outflow pathways.
The **upper outflow** $Q_{r1}$ only fires when $R$ exceeds a threshold $X_8$, representing near-surface flood response (interflow).
The **lower outflow** $Q_{r2}$ is always active and represents slower subsurface drainage.
The relative magnitude of the two is controlled by $X_3$ and $X_9$.

- **Capped percolation**: Water moves from the intermediate reservoir to the groundwater store at a rate capped at $X_5$ mm per day.
This represents the limited infiltration capacity of the deeper soil profile and decouples fast interflow from slow baseflow recharge.

- **Linear baseflow and triangular routing**: The groundwater store $T$ drains linearly with residence time $X_4$, producing sustained baseflow.
The total output ($Q_{r1} + Q_{r2} + Q_t$) is then routed through a **triangular unit hydrograph** of base $X_6$ days, representing channel travel time as a smooth delay rather than a pure time shift.

## How It Works

The HBV0 model processes precipitation and evapotranspiration through the following steps:

**Step 1: Sub-step splitting**.
Each daily time step is divided into five equal sub-steps by splitting the rain $P$ and the PET $E$ into fifths ($P_5 = P/5$, $E_5 = E/5$).
Steps 2 through 4 are applied at each sub-step and runoff generation accumulates into a sub-step total $Pr$.

**Step 2: Non-linear production**.
At each sub-step, the fraction $(S/X_1)^{X_7}$ of $P_5$ is diverted to runoff $Pr_i$ and the rest refills the soil: $S \leftarrow S + (P_5 - Pr_i)$.
Because the multiplier is raised to the power $X_7$, the soil store sharply saturates as $S$ approaches $X_1$, reproducing the observed threshold behavior of wet catchments.

**Step 3: Evapotranspiration**.
Evaporation at the sub-step level is $E_{si} = E_5 \cdot S/X_2$, capped at the current $S$ so the soil cannot go negative.
When $S$ is above $X_2$ evaporation runs at more than the potential rate (this is a modeling artefact of the simplified scheme), but the cap $\min(S, \cdot)$ prevents any physical impossibility.
The soil is updated as $S \leftarrow S - E_{si}$.

**Step 4: End of sub-step loop**.
After five sub-steps the total runoff $Pr$ from the soil is passed to the routing phase.
This concludes the production phase of the model.

**Step 5: Upper outflow (threshold-linear)**.
The intermediate reservoir $R$ first receives $Pr$.
If $R$ exceeds the threshold $X_8$, an upper outflow $Q_{r1} = (R - X_8)/X_3$ fires; otherwise $Q_{r1} = 0$.
This threshold mechanism represents near-surface interflow that only activates when the soil is wet enough — a common feature in operational HBV implementations.
$R$ is then decremented: $R \leftarrow R - Q_{r1}$.

**Step 6: Lower outflow (linear)**.
Whatever remains in $R$ drains linearly at rate $Q_{r2} = R / (X_3 \cdot X_9)$.
Unlike the upper outflow, this component is always active and represents slower subsurface drainage.
$R$ is updated: $R \leftarrow R - Q_{r2}$.

**Step 7: Percolation**.
A fraction of the remaining $R$ percolates down to the groundwater store, capped at the maximum rate $X_5$: $I_r = \min(R, X_5)$.
$R$ is decremented by $I_r$ and the groundwater store $T$ is incremented by the same amount.
This cap introduces a decoupling between fast interflow and slow baseflow — when $R$ is high, most of the water leaves through $Q_{r1}$ and $Q_{r2}$, and only a limited fixed amount refills the groundwater.

**Step 8: Baseflow**.
The groundwater store drains linearly: $Q_t = T / X_4$, then $T \leftarrow T - Q_t$.
Long residence times (large $X_4$) produce sustained baseflow that extends recession curves over weeks.

**Step 9: Triangular routing**.
The total output $Q = Q_{r1} + Q_{r2} + Q_t$ is convolved with a triangular unit hydrograph of time base $X_6$ days, smoothing the hydrograph and representing channel travel time to the outlet.
The first element of the delay register is returned as the simulated streamflow, clamped at zero.

## Parameters

The HBV0 model has nine calibratable parameters.

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|:-----:|-------|------------------------|
| $X_1$ ($F_c$) | Soil reservoir capacity | 100–1000 | mm | Maximum storage of the soil moisture store. Larger values delay runoff generation and extend dry-period memory. |
| $X_2$ ($LP$) | PET threshold | 1–1000 | mm | Soil-moisture level above which evaporation runs at near-potential rate. Below $X_2$, ET is reduced linearly with $S/X_2$. |
| $X_3$ | Upper emptying constant of intermediate reservoir | 1–20 | days | Residence-time scaler for both the upper threshold outflow $Q_{r1}$ and the lower linear outflow $Q_{r2}$. Larger values slow the intermediate reservoir. |
| $X_4$ | Ground reservoir emptying constant | 1–100 | days | Residence time of the linear groundwater store. Larger values produce longer baseflow recessions. |
| $X_5$ | Percolation coefficient | 1–20 | mm/d | Maximum rate of water transfer from the intermediate reservoir to the groundwater store. Caps the baseflow recharge regardless of how wet $R$ is. |
| $X_6$ | Triangular unit hydrograph time base | 2–40 | days | Total duration of the triangular UH. The peak of the UH is at $X_6 / 2$ and the response returns to zero at $X_6$. |
| $X_7$ ($\beta$) | Soil nonlinearity exponent | 0–50 | - | Exponent on $(S/X_1)$ in the production function. $X_7 = 0$ gives a purely linear response (all rain runs off); large values give a sharp threshold behavior where rain only runs off when $S$ is near $X_1$. |
| $X_8$ ($UZL$) | Flow threshold of intermediate reservoir | 0–100 | mm | Level of $R$ above which the upper outflow $Q_{r1}$ activates. When $R < X_8$ only $Q_{r2}$ drains the reservoir. |
| $X_9$ | Lower emptying constant multiplier | 1–20 | - | Multiplier combined with $X_3$ to give the effective residence time of the lower outflow $Q_{r2}$. The product $X_3 \cdot X_9$ is constrained to be $\geq 1$ by the bounds to guarantee numerical stability. |

**Understanding the parameters:**

- **$X_1$ and $X_7$ together** define the production phase.
$X_1$ is the soil capacity; $X_7$ is the Bergström $\beta$ exponent that controls how sharply runoff generation accelerates as the soil fills up.
A high $X_7$ (e.g. 5–10) gives a threshold-like response that is characteristic of real catchments, while $X_7 = 0$ makes all rainfall directly generate runoff.
- **$X_2$** sets the soil-moisture level above which ET runs freely.
In classical HBV literature this is the $LP$ parameter, typically set around $0.5$ to $0.8 \cdot X_1$.
- **$X_3$, $X_8$, and $X_9$ together** define the intermediate reservoir dynamics.
$X_8$ is the threshold above which the upper (fast) outflow activates, $X_3$ controls how fast both outflows drain, and $X_9$ tunes the relative speed of the lower (slow) outflow.
- **$X_4$** is the linear groundwater emptying constant — the longer this is, the longer baseflow lasts into dry spells.
- **$X_5$** is the percolation cap.
It acts as a ceiling on how much water per day can reach the baseflow store, regardless of how full the intermediate reservoir is.
- **$X_6$** is a smoothing parameter: a longer UH time base delays *and* smooths the hydrograph peak, whereas a short UH delivers the response nearly instantaneously.

**Bound tightening for numerical stability:**
The HOOPLA reference implementation allows $X_2 = 0$ and $X_9 = 0$ as valid parameter values, but this HOLMES implementation enforces $X_2 \geq 1$ and $X_9 \geq 1$.
The first bound avoids a division by zero in the evaporation formula $E_5 \cdot S / X_2$.
The second guarantees that $X_3 \cdot X_9 \geq 1$, which in turn guarantees $Q_{r2} \leq R$, so the intermediate reservoir $R$ can never go negative by construction — the tight loop needs no runtime clamping.

## Mathematical Formulation

### Initialization

Initial store levels:

$$S_0 = X_1, \quad R_0 = 1, \quad T_0 = 10$$

where $S$ is the soil moisture, $R$ is the intermediate reservoir, and $T$ is the groundwater store.
The soil is initialized at its capacity (not empty) so the model reaches a realistic water balance faster during the warm-up period.

The triangular unit hydrograph weights are built from $X_6$ as:

$$h_k = \begin{cases} k - 0.5 & \text{for } 1 \leq k \leq \lfloor X_6 / 2 \rfloor \quad \text{(rising limb)} \\ X_6 + 0.5 - k & \text{for } \lfloor X_6 / 2 \rfloor + 1 \leq k \leq \lceil X_6 \rceil \quad \text{(recession limb)} \end{cases}$$

The weights are then normalized so they sum to one: $h_k \leftarrow h_k / \sum_j h_j$.

### Production Phase (five sub-steps)

At each sub-step $i = 1, 2, 3, 4, 5$, with $P_5 = P/5$ and $E_5 = E/5$:

$$Pr_i = P_5 \cdot \left(\min\left(1, \frac{S}{X_1}\right)\right)^{X_7}$$

$$Pr \leftarrow Pr + Pr_i$$

$$S \leftarrow S + (P_5 - Pr_i)$$

$$E_{si} = \min\left(S, \ E_5 \cdot \frac{S}{X_2}\right)$$

$$S \leftarrow S - E_{si}$$

After five sub-steps, $Pr$ is the total runoff leaving the soil to enter the routing phase.

### Upper Outflow (Threshold-Linear)

The intermediate reservoir $R$ first receives the runoff generated by the soil:

$$R \leftarrow R + Pr$$

The upper outflow $Q_{r1}$ only fires when $R$ is above the threshold $X_8$:

$$Q_{r1} = \max\left(0, \ \frac{R - X_8}{X_3}\right)$$

$$R \leftarrow R - Q_{r1}$$

### Lower Outflow (Linear)

Whatever remains drains at a constant linear rate:

$$Q_{r2} = \frac{R}{X_3 \cdot X_9}$$

$$R \leftarrow R - Q_{r2}$$

The bound constraint $X_3 \cdot X_9 \geq 1$ guarantees $Q_{r2} \leq R$ so that $R$ stays non-negative without runtime clamping.

### Percolation

Percolation from $R$ to $T$ is capped at $X_5$:

$$I_r = \min(R, \ X_5)$$

$$R \leftarrow R - I_r$$

### Groundwater Reservoir

The groundwater store receives $I_r$ and drains linearly:

$$T \leftarrow T + I_r$$

$$Q_t = \frac{T}{X_4}$$

$$T \leftarrow T - Q_t$$

### Total Outflow and Triangular Routing

The instantaneous total output before routing is the sum of the three components:

$$Q = Q_{r1} + Q_{r2} + Q_t$$

The simulated streamflow is obtained by convolving $Q$ with the triangular unit hydrograph $\{h_k\}$ via a shift-and-add register $\{H_k\}$ of the same length as $\{h_k\}$:

$$H_k \leftarrow H_{k+1} + h_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow h_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0, \ H_0)$$

The first element of the register is returned as the current time step's streamflow, and the register is shifted by one position ready for the next time step.

## References

Bergström, S., & Forsman, A. (1973).
Development of a conceptual deterministic rainfall-runoff model.
*Nordic Hydrology*, 4(3), 147–170.

Bergström, S. (1995).
The HBV model.
In V. P. Singh (Ed.), *Computer Models of Watershed Hydrology*, Chapter 13.
Water Resources Publications, 443–476.

Lindström, G., Johansson, B., Persson, M., Gardelin, M., & Bergström, S. (1997).
Development and test of the distributed HBV-96 hydrological model.
*Journal of Hydrology*, 201, 272–288.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°15 (HBV), pp. 366–371.

Seibert, J. (1997).
Estimation of parameter uncertainty in the HBV model.
*Nordic Hydrology*, 28(4/5), 247–262.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
