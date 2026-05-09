# SIMHYD Model

## Overview

SIMHYD (SIMple HYDrological model) is an eight-parameter conceptual rainfall-runoff model developed in Australia by Chiew, Peel, and Western (2002).
It belongs to the family of threshold-based models where infiltration capacity decays exponentially with soil saturation, a common simplification in Australian water-resources practice.

The HOLMES implementation follows the modified version from the HOOPLA toolbox (Thiboult et al., 2020, HM15), which adds two routing reservoirs and a fractional-delay parameter to the original formulation.
The model represents a catchment as an interception store, a soil moisture store, and two linear routing reservoirs (ground and main) connected by a time-delay register.

SIMHYD is a good choice when a simple model with explicit interflow and groundwater-recharge pathways is desired.
Its eight parameters are easy to interpret physically, making it well-suited for teaching and for benchmarking against more complex models.

## Key Concepts

- **Interception store**: a conceptual reservoir of capacity $X_1$ that captures precipitation before it reaches the soil, limited by both rainfall and available PET.
- **Soil moisture store**: a bucket of capacity $X_2$ that receives infiltrated water and loses water to evapotranspiration, interflow, groundwater recharge, and overflow.
- **Exponential infiltration**: the maximum infiltration rate decays as $X_8 \cdot e^{-2\,S/X_2}$ — a saturated soil admits very little additional water.
- **Interflow**: lateral subsurface flow proportional to soil saturation and inversely proportional to $X_6$.
- **Groundwater recharge**: deep percolation proportional to soil saturation and inversely proportional to $X_7$.
- **Ground reservoir**: a slow linear reservoir (emptying constant $X_3 \cdot X_5$) that receives soil excess and recharge.
- **Routing reservoir**: a fast linear reservoir (emptying constant $X_5$) that collects all flow components before delay routing.
- **Fractional delay**: a two-weight unit hydrograph of base $X_4$ days that shifts the routed flow in time.

## How It Works

**Step 1: Interception.**
Incoming precipitation $P$ is first intercepted up to a limit set by both the interception capacity $X_1$ and the available PET $E$.
The intercepted amount is $\text{CAP} = \min(P,\, X_1,\, E)$.
If precipitation exceeds this amount, the excess $\text{EXC} = P - \text{CAP}$ proceeds to infiltration; otherwise all precipitation is intercepted and no excess remains.

**Step 2: Infiltration.**
The excess rainfall is partitioned between surface runoff and infiltration based on the soil's ability to absorb water.
The infiltration capacity is $\text{RINF} = X_8 \cdot e^{-2\,S/X_2}$, which decays exponentially as the soil saturates.
If the excess exceeds this capacity, the surplus becomes surface runoff $Q_\text{srun}$ and only $\text{RINF}$ infiltrates.

**Step 3: Interflow and groundwater recharge.**
From the infiltrated water, a fraction proportional to soil saturation $S/X_2$ is diverted as interflow ($\text{SINT}$, governed by $X_6$) and groundwater recharge ($\text{REC}$, governed by $X_7$).
Both quantities increase as the soil approaches saturation, representing the idea that wetter soils lose water faster through lateral and vertical pathways.

**Step 4: Soil moisture accounting.**
The soil store $S$ receives the infiltrated water minus what was lost to interflow and recharge.
If $S$ exceeds capacity $X_2$, the excess $\text{EX}_2$ overflows to the ground reservoir.
Remaining PET (after interception) drives actual evapotranspiration from the soil, limited to $10 \cdot S / X_2$ mm, and the soil level is clamped to zero.

**Step 5: Routing.**
Soil excess and recharge feed the **ground reservoir** $R$ (slow pathway, emptying at rate $1/(X_3 \cdot X_5)$).
Surface runoff, interflow, and the ground reservoir outflow feed the **routing reservoir** $T$ (fast pathway, emptying at rate $1/X_5$).
This two-reservoir arrangement lets the model separate fast response from slow baseflow.

**Step 6: Delay and streamflow.**
The routing reservoir output $Q_t$ is convolved with a two-weight fractional-delay function of base $X_4$ days, producing the final simulated streamflow $Q$.
The delay shifts the hydrograph peak in time without changing its volume, representing travel time through the channel network.

## Parameters

The SIMHYD model has 8 calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ | Interception store capacity | 0.5 – 10.0 | mm | Maximum rainfall that can be held by vegetation canopy before reaching the soil |
| $X_2$ | Soil moisture store capacity | 1.0 – 500.0 | mm | Total amount of water the soil can hold before overflowing |
| $X_3$ | Ground reservoir emptying constant | 1.0 – 1000.0 | - | Multiplier that slows the ground reservoir relative to the routing reservoir |
| $X_4$ | Delay | 0.5 – 5.0 | d | Fractional time shift applied to routed streamflow |
| $X_5$ | Routing reservoir emptying constant | 1.0 – 500.0 | d | Controls how quickly the main routing reservoir drains |
| $X_6$ | Interflow constant | 1.0 – 1000.0 | - | Larger values reduce interflow; inversely proportional to the standard SIMHYD SUB parameter |
| $X_7$ | Groundwater recharge constant | 1.0 – 1000.0 | - | Larger values reduce deep percolation; inversely proportional to the standard SIMHYD CRAK parameter |
| $X_8$ | Maximum infiltration capacity | 1.0 – 500.0 | mm | Infiltration rate when the soil is completely dry; decays exponentially with saturation |

**Understanding the parameters:**

- $X_1$ is small (typically 1–5 mm) because canopy interception is a minor component of the water balance. It mainly affects peak timing and ET partitioning.
- $X_2$ controls the overall wetness of the catchment — larger values mean more buffering before soil excess triggers overflow to the ground reservoir.
- $X_3$ and $X_5$ together control the slow/fast flow separation: the routing reservoir empties at rate $1/X_5$ while the ground reservoir empties at rate $1/(X_3 \cdot X_5)$. Increasing $X_3$ makes baseflow more persistent.
- $X_6$ and $X_7$ compete for infiltrated water — when both are small, the soil loses water quickly through lateral and vertical pathways; when both are large, water stays in the soil longer and is eventually lost to ET or overflow.
- $X_8$ sets the infiltration ceiling. On dry soils the full $X_8$ mm is available, but as $S \to X_2$ the effective infiltration drops to about $14\%$ of $X_8$ (because $e^{-2} \approx 0.135$).

## Mathematical Formulation

### Initialization

$$S_0 = \frac{X_2}{2}, \quad R_0 = 80, \quad T_0 = 1$$

### Interception

$$\text{CAP} = \min(P,\, X_1,\, E)$$

$$\text{EXC} = \max(0,\; P - \text{CAP}), \quad E_1 = \begin{cases} \text{CAP} & \text{if } P > \text{CAP} \\ P & \text{otherwise} \end{cases}$$

### Infiltration

$$\text{RINF} = X_8 \cdot \exp\!\left(-2\,\frac{S}{X_2}\right)$$

$$Q_\text{srun} = \max(0,\; \text{EXC} - \text{RINF}), \quad \text{FILT} = \min(\text{EXC},\; \text{RINF})$$

### Interflow and Groundwater Recharge

$$\text{SINT} = \frac{S}{X_2} \cdot \frac{\text{FILT}}{X_6}$$

$$\text{REC} = \max\!\left(0,\; \frac{S}{X_2} \cdot \frac{\text{FILT} - \text{SINT}}{X_7}\right)$$

### Soil Moisture Accounting

$$S \leftarrow S + \text{FILT} - \text{SINT} - \text{REC}$$

$$\text{EX}_2 = \max(0,\; S - X_2), \quad S \leftarrow \min(S,\; X_2)$$

$$\text{ET} = \min\!\left(E - E_1,\; 10 \cdot \frac{S}{X_2}\right), \quad S \leftarrow \max(0,\; S - \text{ET})$$

### Ground Reservoir (Slow)

$$R \leftarrow R + \text{EX}_2 + \text{REC}$$

$$Q_r = \frac{R}{X_3 \cdot X_5}, \quad R \leftarrow R - Q_r$$

### Routing Reservoir (Fast)

$$T \leftarrow T + \text{SINT} + Q_\text{srun} + Q_r$$

$$Q_t = \frac{T}{X_5}, \quad T \leftarrow T - Q_t$$

### Total Streamflow

$$Q = \text{delay}(Q_t,\; X_4)$$

where $\text{delay}(\cdot, X_4)$ is a two-weight fractional-delay convolution of base $\lceil X_4 \rceil + 1$ time steps.

## References

- Chiew, F.H.S., Peel, M.C., & Western, A.W. (2002). Application and testing of the simple rainfall-runoff model SIMHYD. In V.P. Singh, D.K. Frevert (Eds.), *Mathematical Models of Small Watershed Hydrology and Applications* (pp. 335–367). Water Resources Publications.
- Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020). The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory. *Hydrology and Earth System Sciences Discussions*.
- Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis). INPG, Grenoble.
