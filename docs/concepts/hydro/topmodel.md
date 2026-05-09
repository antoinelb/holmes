# TOPMODEL Model

## Overview

TOPMODEL (the *TOPography-based hydrological MODEL*) was introduced by Beven and Kirkby in 1979 as one of the first conceptual rainfall-runoff models to make explicit use of digital terrain information.
Its central premise is that the *spatial distribution of saturated areas* in a catchment can be predicted from a single statistical descriptor of the topography — the topographic index $\ln(a/\tan\beta)$, computed for every cell of a digital elevation model.
This was a radical departure from the lumped reservoir models of its era, and TOPMODEL became the conceptual ancestor of an entire family of "semi-distributed" models that try to bridge the gap between fully distributed physically-based simulators and parsimonious lumped models.

The original Beven & Kirkby formulation has roughly ten degrees of freedom (capacities, transmissivities, plus the topographic-index distribution itself).
Perrin (2000) showed that for daily lumped rainfall-runoff modelling without a digital elevation model in hand, the topographic-index distribution can be approximated by a *logistic function* of two parameters, collapsing the structure to **seven calibratable parameters**.
This is the version implemented in HOLMES, following Perrin's Annex 1 fiche n°33 and HOOPLA's HM18 reference implementation.

Structurally, the simplified TOPMODEL represents a catchment as three reservoirs: an interception store $S$, an unbounded groundwater deficit store $T$, and a quadratic surface routing reservoir $R$.
What makes it distinctive — and what makes it pedagogically valuable — is that the partitioning of effective rainfall between recharge and surface runoff is not done by a hard threshold or a saturation curve, but by a *sigmoid function* that depends on the current state of $T$.
The same sigmoid mechanism is used a second time to partition residual evapotranspiration between the soil and the groundwater store.
Students typically choose TOPMODEL when they want to study how a smooth probabilistic partition function behaves differently from the threshold-based partitions used in models like HBV or BUCKET.

## Key Concepts

- **Topographic index**: A spatial descriptor of the form $\ln(a/\tan\beta)$, where $a$ is the upslope contributing area per unit contour length and $\tan\beta$ is the local slope. High values mark concave wet zones near the channel; low values mark dry hilltops. In Perrin's reduction this distribution is replaced by a two-parameter logistic curve.

- **Interception store ($S$)**: A small surface reservoir of capacity $X_3$ that intercepts rainfall and consumes the first share of PET. Spill from $S$ becomes the effective rainfall $P_r$ that drives the rest of the model.

- **Groundwater deficit store ($T$)**: An *unbounded* reservoir that tracks the catchment-average groundwater state. Unlike the soil stores in GR4J or HBV, $T$ has no upper or lower cap — it can drift positive (saturation) or negative (deep deficit). This unboundedness is structural to TOPMODEL and is part of why initialization matters.

- **Sigmoid recharge partition**: The fraction of effective rainfall $P_r$ that recharges $T$ is given by the logistic function $1/(1 + \exp(X_6 - T/X_5))$ — a smooth probabilistic alternative to the hard saturation thresholds used in other models. As $T$ rises (catchment wetter), the sigmoid approaches 1 and almost everything recharges; as $T$ drops, the sigmoid drops to zero and almost everything becomes overland flow.

- **Sigmoid groundwater ET**: A second logistic function $1/(1 + \exp(X_7 - T/X_5))$ partitions the residual PET between the soil and the groundwater store. Following Perrin's Fiche 33 — preserved literally from HOOPLA — this term is *added* to $T$ rather than subtracted, an idiosyncrasy of the formulation that students often question.

- **Exponential baseflow**: The groundwater discharge $Q_t = X_2 \exp(T/X_2)$ is exponential in $T$: it grows fast when the catchment saturates and decays slowly during dry periods. The fact that $X_2$ appears as both the prefactor and the recession scale couples the baseflow magnitude to the recession length — an unusual choice with practical consequences for calibration.

- **Quadratic routing reservoir ($R$)**: A nonlinear surface routing store with discharge $Q_r = R^2/(R + X_1)$. Compared to the linear stores used in BUCKET or HBV, this quadratic form delivers sharper flood peaks at high storage and gentler tails at low storage.

- **Fractional-delay routing**: As in GR4J/GARDENIA/SACRAMENTO, the summed outflow $Q_t + Q_r$ passes through a two-tap shift register of length $\lceil X_4 \rceil + 1$, letting non-integer delays translate into a smooth time shift without per-step interpolation.

## How It Works

The TOPMODEL model processes precipitation and evapotranspiration through the following steps:

**Step 1: Interception store and effective rainfall**.
Precipitation $P$ is added to the interception store $S$, then PET consumes the first share $E_s = \min(S, E)$.
The residual PET, $E' = E - E_s$, will drive groundwater evaporation downstream.
If $S$ exceeds its capacity $X_3$, the spill $P_r$ becomes the "effective rainfall" that enters the rest of the model.

**Step 2: Sigmoid recharge to the groundwater store ($P_r \to T$)**.
The effective rainfall $P_r$ is split into a recharge component $P_s$ (going to $T$) and a quickflow component $P_r - P_s$ (going to the surface routing store $R$).
The split is governed by the logistic function $P_s = P_r / (1 + \exp(X_6 - T/X_5))$ — when $T$ is high (wet catchment), most water recharges $T$; when $T$ is low (dry catchment), most water becomes quickflow.
The groundwater state $T$ is then updated by $T \leftarrow T + P_r - P_s$ — i.e., $T$ receives only the *non-recharged* fraction, because the recharged $P_s$ is treated as having flowed straight through to deeper drainage.

**Step 3: Sigmoid groundwater evapotranspiration**.
The residual PET $E'$ is partitioned by a second sigmoid: $E_t = E' / (1 + \exp(X_7 - T/X_5))$.
Following Perrin's Annex 1 fiche n°33 and HOOPLA HM18, this term is *added* to $T$ rather than subtracted: $T \leftarrow T + E_t$.
This sign convention is preserved literally from the source even though it conflicts with the obvious physical reading; it is part of the formulation and removing it would change the calibrated behavior.

**Step 4: Surface routing reservoir ($R$, quadratic discharge)**.
The quickflow $P_s$ (interpreted as the saturation-excess fraction not absorbed by $T$) is added to the surface routing reservoir $R$.
The reservoir then drains nonlinearly as $Q_r = R^2 / (R + X_1)$, a quadratic discharge function that produces sharper peaks at high storage and softer tails at low storage than a linear store would.

**Step 5: Exponential baseflow from $T$**.
The groundwater store $T$ discharges as $Q_t = X_2 \exp(T/X_2)$, then $T$ is updated by $T \leftarrow T - Q_t$.
Because $X_2$ appears as both the prefactor and the recession scale, doubling $X_2$ both doubles the baseflow magnitude and *halves* the recession decay rate of $T$ — the two are not independently calibratable, which is a known limitation of the seven-parameter reduction.

**Step 6: Fractional-delay routing of the total outflow**.
The two outflows $Q_t$ and $Q_r$ are summed and pushed through a shift-and-add register $\{HY_k\}$ of length $n = \lceil X_4 \rceil + 1$, with two non-zero weights at $DL_{n-2}$ and $DL_{n-1}$ that encode the non-integer delay $X_4$.
The first element of the register, clamped at zero, is returned as the simulated streamflow for the current time step.

## Parameters

The TOPMODEL has seven calibratable parameters.

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|:-----:|-------|------------------------|
| $X_1$ | Quadratic routing reservoir capacity | 1–1000 | mm | Storage scale of the surface routing reservoir $R$. Larger values smooth the hydrograph by spreading the surface response over more time steps. |
| $X_2$ | Exponential groundwater drainage parameter | 0.1–50 | mm | Sets both the baseflow magnitude at saturation ($Q_t = X_2$ when $T = 0$) and the recession decay length. The two roles are coupled. |
| $X_3$ | Interception reservoir capacity | 0.1–100 | mm | Capacity of the canopy/depression store $S$. Above $X_3$ the interception spill becomes effective rainfall. Often weakly identifiable. |
| $X_4$ | Routing delay | 0.5–10 | days | Fractional delay of the unit hydrograph register. Affects timing only, not shape. |
| $X_5$ | Topographic-index distribution scale | 1–200 | mm | Sets the steepness of both sigmoid partition functions through the term $T/X_5$. Smaller values make the sigmoids switch between the wet and dry regimes more abruptly. |
| $X_6$ | Topographic-index sigmoid offset | -10 – 10 | - | Shifts the recharge sigmoid horizontally. Negative values bias toward more recharge; positive values bias toward more quickflow. |
| $X_7$ | Groundwater PET sigmoid offset | -10 – 10 | - | Shifts the groundwater-ET sigmoid horizontally. Controls how much of the residual PET ends up modulating $T$. |

**Understanding the parameters:**

- **$X_2$ is dual-roled and the most sensitive parameter**: it sets both the baseflow rate at saturation and the exponential recession length. Doubling $X_2$ doubles the baseflow magnitude *and* doubles the recession length scale, so an under-calibrated catchment can easily lead to runaway baseflow magnitudes if the bounds are too generous. Stay in the 1–30 mm range for most catchments unless you have a strong reason otherwise.
- **$X_5$ controls the sigmoid sharpness**, while $X_6$ and $X_7$ control the sigmoid offsets. These three parameters together fully determine the partitioning behavior of TOPMODEL. A common calibration trap is to fix $X_5$ at a moderate value (say 50 mm) and explore $X_6$ and $X_7$ first — the model is much less identifiable when all three are free.
- **$X_1$ shapes the flood response** without affecting the long-term water balance. Small $X_1$ produces flashy peaks; large $X_1$ smooths the hydrograph. It is the easiest parameter to tune by visual inspection.
- **$X_3$ is often weakly identifiable** — interception capacities below ~5 mm produce nearly indistinguishable hydrographs in most temperate catchments. Perrin's discussion in Fiche 33 explicitly notes that $X_3$ "may be fixed" without much loss.
- **$X_4$ is a pure translation parameter**: it shifts the hydrograph in time without changing its shape. Calibrate it last, after the others have settled into a reasonable shape.

**Why the groundwater store is unbounded**: TOPMODEL's $T$ represents a *deficit* relative to a notional saturation reference, not a stock of water. There is no physical reason for it to be capped — a catchment can be arbitrarily wet (positive $T$) or arbitrarily dry (negative $T$). The exponential discharge function $Q_t = X_2 \exp(T/X_2)$ makes the model self-regulating: when $T$ grows, baseflow grows exponentially and pulls $T$ back down. This is structurally different from the bounded soil stores in HBV/SACRAMENTO/GR4J.

## Mathematical Formulation

### Initialization

Initial reservoir states (from HOOPLA's `ini_HydroMod18.m`, matching Perrin's fiche):

$$S_0 = 10 \ \text{mm}, \quad T_0 = -50 \ \text{mm}, \quad R_0 = 0.2 \cdot X_1$$

The deeply negative initial $T$ is intentional: it suppresses the exponential baseflow $Q_t = X_2 \exp(T/X_2)$ during spin-up, letting recharge fill $T$ toward its steady-state equilibrium without producing a startup discharge spike.

The fractional-delay routing array $\{DL_k\}$ of length $n = \lceil X_4 \rceil + 1$ is built so that only the last two elements are non-zero:

$$DL_{n-2} = \frac{1}{X_4 - n + 3}, \quad DL_{n-1} = 1 - DL_{n-2}$$

This is the same two-tap stencil used by GR4J, GARDENIA, and SACRAMENTO.

### Surface Phase (interception store)

$$S \leftarrow S + P$$

$$E_s = \min(S, E), \quad S \leftarrow S - E_s, \quad E' = E - E_s$$

$$P_r = \max(0, \ S - X_3), \quad S \leftarrow S - P_r$$

### Sigmoid Recharge to the Groundwater Store

The effective rainfall $P_r$ is partitioned by a logistic function depending on $T$:

$$P_s = \frac{P_r}{1 + \exp\left(X_6 - \dfrac{T}{X_5}\right)}$$

$$T \leftarrow T + (P_r - P_s)$$

### Sigmoid Groundwater Evapotranspiration

$$E_t = \frac{E'}{1 + \exp\left(X_7 - \dfrac{T}{X_5}\right)}$$

$$T \leftarrow T + E_t$$

(The sign matches Perrin's Annex 1 fiche n°33 and HOOPLA HM18 literally — see the implementation note in the source.)

### Surface Routing Reservoir

The quickflow $P_s$ enters the quadratic routing reservoir $R$:

$$R \leftarrow R + P_s$$

$$Q_r = \frac{R^2}{R + X_1}, \quad R \leftarrow R - Q_r$$

### Exponential Baseflow from $T$

$$Q_t = X_2 \exp\left(\frac{T}{X_2}\right), \quad T \leftarrow T - Q_t$$

### Total Streamflow and Fractional Delay

The two outflows are summed and pushed through the shift-and-add delay register $\{HY_k\}$ of length $n = \lceil X_4 \rceil + 1$:

$$Q = Q_t + Q_r$$

$$HY_k \leftarrow HY_{k+1} + DL_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$HY_{n-1} \leftarrow DL_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0, \ HY_0)$$

The first element of the register is returned as the simulated streamflow; the register then advances by one position, ready for the next step.

## References

Beven, K. J., & Kirkby, M. J. (1979).
A physically based, variable contributing area model of basin hydrology.
*Hydrological Sciences Bulletin*, 24(1), 43–69.
[https://doi.org/10.1080/02626667909491834](https://doi.org/10.1080/02626667909491834)

Beven, K. (1997).
TOPMODEL: a critique.
*Hydrological Processes*, 11(9), 1069–1085.

Franchini, M., Wendling, J., Obled, C., & Todini, E. (1996).
Physical interpretation and sensitivity analysis of the TOPMODEL.
*Journal of Hydrology*, 175, 293–338.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°33 (TOPMODEL), pp. 453–458.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
