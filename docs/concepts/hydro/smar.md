# SMAR Model

## Overview

SMAR (Soil Moisture Accounting and Routing) is an eight-parameter daily lumped rainfall-runoff model originally developed by O'Connell, Nash, and Farrell at University College Galway, Ireland (O'Connell et al., 1970).
It was designed as a general-purpose conceptual model for operational streamflow forecasting and has been widely applied in Irish, tropical, and semi-arid catchments.

The variant implemented in HOLMES is the **retained version** described in Annex 1 of Perrin (2000), corresponding to HOOPLA HM16.
It represents the catchment as a **16-layer discretised soil column** (each layer 25 mm thick, total depth $Z = 400$ mm) feeding two parallel routing reservoirs — one linear (groundwater) and one quadratic (surface) — with a fractional-delay unit hydrograph at the outlet.

What makes SMAR distinctive among the HOLMES models is its **explicit vertical soil discretisation**.
While most models represent soil moisture as a single bulk reservoir (GR4J, HYMOD, Bucket) or as a few discrete stores (SACRAMENTO, NAM), SMAR divides the soil into 16 physical layers and applies evapotranspiration to each layer with an **exponentially decaying intensity** ($C^i$, where $C < 1$ and $i$ is the layer index).
This means the top layers dry out first and more intensely, while deeper layers retain moisture longer — a realistic representation of how plant roots extract water preferentially from the surface.
The model is a good pedagogical choice when students need to understand how vertical soil structure affects runoff generation and recession behavior.

## Key Concepts

- **16-layer soil column**: The soil is discretised into 16 layers of 25 mm each (total $Z = 400$ mm).
Water infiltrates from the top layer downward; each layer fills to capacity before overflowing to the next.
Drainage from the bottom layer constitutes interflow.

- **Exponentially decaying evapotranspiration**: Each soil layer $i$ is subject to evapotranspiration at rate $C^i \cdot E_n$, where $C = X_3 < 1$ is a calibratable coefficient and $E_n$ is the remaining atmospheric demand.
The top layer receives the strongest ET, and each subsequent layer receives exponentially less — mimicking declining root-zone water uptake with depth.

- **Moisture-dependent direct runoff**: A fraction $H' = X_1 \cdot S / S_{\max}$ of net precipitation runs off directly without entering the soil, where $S$ is the moisture content of the top five layers.
As the soil wets up, direct runoff increases — a simple saturation-excess mechanism.

- **Exponential infiltration capacity**: The maximum infiltration rate decays exponentially with soil moisture: $F_r = Y_m \cdot \exp(-X_2 \cdot S / S_{\max})$, where $Y_m = 200$ mm/d is a fixed maximum.
Dry soils absorb rain readily; near-saturated soils severely limit infiltration.

- **Dual routing reservoirs**: Interflow from the soil column is split between a linear groundwater reservoir (fraction $1 - X_8$) and a quadratic surface reservoir (fraction $X_8$).
The linear reservoir produces smooth, sustained baseflow; the quadratic reservoir generates peakier, faster-decaying flow that dominates during storms.

- **Quadratic routing**: The surface routing reservoir drains via $Q_t = T^2 / (T + X_4)$, the same non-linear law used by GARDENIA.
This produces fast recession from high storage and slow recession from low storage.

- **PET correction coefficient**: The input PET is scaled by a calibratable factor $X_7$ before use, allowing the model to compensate for systematic biases in the PET estimate (similar to GARDENIA's $X_5$).

- **Fractional delay routing**: A short pure delay $X_6$ (typically 0.5 to 5 days) shifts the hydrograph to account for channel travel time, using a two-element fractional interpolation between adjacent integer delays.

## How It Works

The SMAR model processes precipitation and evapotranspiration through the following steps each day:

**Step 1: PET correction and net inputs**.
The input PET is scaled by the correction coefficient: $E_{\text{corr}} = X_7 \cdot E$.
Net precipitation and net evapotranspiration are computed as complementary residuals: $P_n = \max(0, P - E_{\text{corr}})$ and $E_n = \max(0, E_{\text{corr}} - P)$.
Only one of these is non-zero on any given day — on wet days $P_n > 0$ and $E_n = 0$; on dry days $E_n > 0$ and $P_n = 0$.

**Step 2: Direct runoff**.
A moisture-dependent fraction of net precipitation runs off directly: $P_{r1} = H' \cdot P_n$, where $H' = X_1 \cdot S / S_{\max}$.
Here $S$ is the moisture sum of the top five layers (capacity $S_{\max} = 125$ mm).
When the soil is wet ($S \approx S_{\max}$), $H'$ approaches $X_1$ and substantial rain bypasses the soil column entirely; when the soil is dry, almost all rain infiltrates.

**Step 3: Infiltration and surface excess**.
The infiltration capacity $F_r = 200 \cdot \exp(-X_2 \cdot S / S_{\max})$ limits how much of the remaining rainfall ($P_n - P_{r1}$) can enter the soil.
Actual infiltration is $P_s = \min(F_r, P_n - P_{r1})$, and any surplus above the infiltration capacity becomes surface excess $P_{r2}$.

**Step 4: 16-layer soil moisture accounting**.
Infiltrated water $P_s$ cascades down the 16 layers sequentially: each layer absorbs water up to its 25 mm capacity, and any overflow passes to the next layer.
At each layer, evapotranspiration removes water at an exponentially decreasing rate $C^{i+1} \cdot E_n$ (where $i$ is the zero-based layer index), reducing the remaining atmospheric demand $E_n$ accordingly.
Water that overflows from the bottom layer (layer 16) constitutes **interflow**.

**Step 5: Linear groundwater routing**.
A fraction $1 - X_8$ of the interflow enters the linear groundwater reservoir: $L \leftarrow L + (1 - X_8) \cdot I$.
The reservoir drains linearly: $Q_l = L / X_5$, producing smooth baseflow.

**Step 6: Quadratic surface routing**.
The remaining fraction $X_8$ of interflow, plus any surface excess $P_{r2}$ from Step 3, enters the quadratic routing reservoir: $T \leftarrow T + X_8 \cdot I + P_{r2}$.
The reservoir drains via the quadratic law: $Q_t = T^2 / (T + X_4)$, producing peaked, fast-decaying flow.

**Step 7: Total streamflow and delay**.
The total flow $Q = Q_l + Q_t + P_{r1}$ (baseflow + surface routing + direct runoff) is injected into the fractional-delay register of size $\lceil X_6 \rceil + 1$.
The register shifts by one step each day, and the first element — clamped at zero — is returned as the simulated streamflow.

## Parameters

The SMAR model has eight calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|:-----:|-------|------------------------|
| $X_1$ | Direct flow coefficient ($H$) | 0.01–1.0 | - | Maximum fraction of net precipitation that runs off directly when the top soil is fully saturated. Higher values increase the flashiness of peak flows. |
| $X_2$ | Infiltration parameter ($Y_c$) | 0.01–10.0 | - | Controls how fast infiltration capacity decays with increasing soil moisture. Higher values mean the soil "seals" more quickly as it wets up. |
| $X_3$ | PET reduction coefficient ($C$) | 0.01–0.99 | - | Base of the exponential ET decay with depth: layer $i$ receives $C^{i+1}$ of the remaining atmospheric demand. Lower values concentrate ET in the surface layers; values near 1 spread ET uniformly through the soil column. |
| $X_4$ | Quadratic routing reservoir capacity | 1–500 | mm | Characteristic storage of the quadratic surface routing reservoir. Larger values slow the surface recession and spread flood peaks; smaller values produce sharper peaks. |
| $X_5$ | Linear routing reservoir emptying constant | 1–200 | days | Residence time of the linear groundwater store ($Q_l = L / X_5$). Large values produce long, sustained baseflow recessions; small values give a flashier groundwater response. |
| $X_6$ | Delay | 0.5–5.0 | days | Pure channel routing delay applied at the outlet. Shifts the hydrograph in time without changing its shape. |
| $X_7$ | PET correction coefficient | 0.1–2.0 | - | Multiplicative factor applied to the input PET series. Values above 1 increase evapotranspiration (useful when Oudin PET underestimates for a given climate); below 1 reduces it. |
| $X_8$ | Flow partitioning coefficient ($G$) | 0.01–0.99 | - | Fraction of interflow routed to the quadratic surface reservoir. The complement $(1 - X_8)$ goes to the linear groundwater store. Controls the balance between fast peaked flow and slow sustained baseflow. |

**Understanding the parameters:**

- **$X_1$** is the saturation-excess runoff coefficient.
At $X_1 = 1.0$, a fully saturated soil sends all net precipitation directly to the stream; at $X_1 = 0.01$, almost none.
Expect calibrated values between 0.1 and 0.6 for most humid catchments.
- **$X_2$ and $X_3$ together** control how the soil processes water.
$X_2$ governs the infiltration capacity (how quickly rain can enter the soil column), while $X_3$ governs the ET extraction profile (how quickly the soil dries from the top down).
Low $X_3$ (0.1–0.3) creates a sharply surface-drying soil; high $X_3$ (0.7–0.9) distributes ET evenly.
- **$X_4$ and $X_5$** are the routing parameters.
$X_4$ controls the fast (quadratic) response, while $X_5$ controls the slow (linear) baseflow.
When $X_5 \gg X_4$, the hydrograph shows distinct fast peaks on a slow base — typical of catchments with deep aquifers.
- **$X_8$** is a flow partitioning knob similar to MARTINE's $X_5$ or GR4J's fixed 90/10 split.
Values near 1 send most interflow through the fast quadratic path; values near 0 send it to groundwater.
For catchments with strong baseflow, expect $X_8 < 0.5$.

## Mathematical Formulation

### Initialization

Fixed reservoir states at $t = 0$:

$$W_i = 2 \text{ mm for } i = 1, \ldots, 16$$

$$S_0 = 100 \text{ mm}, \quad L_0 = 50 \text{ mm}, \quad T_0 = 20 \text{ mm}$$

where $W_i$ are the individual soil layer storages, $S$ is the top-five-layer moisture sum (recalculated each step), $L$ is the linear routing reservoir, and $T$ is the quadratic routing reservoir.

The fractional-delay register $\{H_k\}$ has $n = \lceil X_6 \rceil + 1$ elements, initialized to zero, with weights:

$$d_{n-2} = \frac{1}{X_6 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}$$

### PET Correction and Net Inputs

$$E_{\text{corr}} = X_7 \cdot E$$

$$P_n = \max(0, P - E_{\text{corr}})$$

$$E_n = \max(0, E_{\text{corr}} - P)$$

### Direct Runoff

The soil moisture sum of the top five layers is:

$$S = \sum_{i=1}^{5} W_i, \quad S_{\max} = 125 \text{ mm}$$

The moisture-dependent direct runoff fraction:

$$H' = X_1 \cdot \frac{S}{S_{\max}}$$

$$P_{r1} = H' \cdot P_n$$

### Infiltration

The infiltration capacity decreases exponentially with soil saturation:

$$F_r = Y_m \cdot \exp\!\left(-X_2 \cdot \frac{S}{S_{\max}}\right), \quad Y_m = 200 \text{ mm/d}$$

Actual infiltration and surface excess:

$$P_s = \min\!\bigl(F_r,\; \max(0, P_n - P_{r1})\bigr)$$

$$P_{r2} = \max\!\bigl(0,\; P_n - P_{r1} - P_s\bigr)$$

### 16-Layer Soil Moisture Accounting

For each layer $i = 1, 2, \ldots, 16$:

$$W_i \leftarrow W_i + P_s$$

$$P_s \leftarrow \max(0, W_i - 25)$$

$$W_i \leftarrow W_i - P_s$$

$$E_i = \min\!\bigl(W_i,\; X_3^{\,i} \cdot E_n\bigr)$$

$$W_i \leftarrow W_i - E_i$$

$$E_n \leftarrow E_n - E_i$$

The remaining $P_s$ after the bottom layer is the **interflow**:

$$I = P_s \big|_{i=16}$$

The top-five-layer moisture sum $S$ is then recomputed for the next time step:

$$S \leftarrow \sum_{i=1}^{5} W_i$$

### Linear Groundwater Routing

The linear reservoir receives a fraction $(1 - X_8)$ of the interflow:

$$L \leftarrow L + (1 - X_8) \cdot I$$

$$Q_l = \frac{L}{X_5}$$

$$L \leftarrow L - Q_l$$

### Quadratic Surface Routing

The quadratic reservoir receives the remaining interflow plus surface excess:

$$T \leftarrow T + X_8 \cdot I + P_{r2}$$

$$Q_t = \frac{T^2}{T + X_4}$$

$$T \leftarrow T - Q_t$$

### Delay Routing

The total flow before routing:

$$Q = Q_l + Q_t + P_{r1}$$

The register $\{H_k\}$ is updated with the shift-and-add rule:

$$H_k \leftarrow H_{k+1} + d_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow d_{n-1} \cdot Q$$

The simulated streamflow is:

$$Q_{\text{sim}} = \max(0,\; H_0)$$

## References

O'Connell, P. E., Nash, J. E., & Farrell, J. P. (1970).
River flow forecasting through conceptual models, Part II: The Brosna catchment at Ferbane.
*Journal of Hydrology*, 10(4), 317–329.

Kachroo, R. K. (1992).
River flow forecasting. Part 5. Applications of a conceptual model.
*Journal of Hydrology*, 133(1-2), 141–178.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°30 (SMAR), pp. 438–441.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
