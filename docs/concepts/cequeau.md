# CEQUEAU Model

## Overview

CEQUEAU is a conceptual rainfall-runoff model originally developed at INRS-Eau (Institut National de la Recherche Scientifique) in Québec, Canada, by Girard, Morin, and Charbonneau (1972). The name comes from the former name of the institute. In its original form, CEQUEAU is a spatially distributed model designed for use with physiographic databases, but it can also operate in lumped mode.

The version implemented in HOLMES follows the simplified "CEQU" variant described in Perrin (2000), which reduces the original 11-parameter formulation to 9 parameters. This simplified version removes the impervious surface partitioning mechanism, fixes the evapotranspiration threshold, and adds a pure time delay parameter. Despite these simplifications, the core two-reservoir structure of the original model is preserved.

CEQUEAU represents the catchment using two interconnected reservoirs: a surface (soil) store that handles precipitation, evapotranspiration, and infiltration, and a groundwater store that receives percolated water and produces slower flow components. Both reservoirs generate multiple outflow pathways — some threshold-based, some continuous — giving the model considerable flexibility in reproducing different hydrograph shapes.

## Key Concepts

- **Surface store**: The upper reservoir receiving precipitation directly. It produces three distinct outflow pathways (overflow, threshold-based drainage, and continuous drainage) and loses water to both evapotranspiration and infiltration to the groundwater store.

- **Groundwater store**: The lower reservoir fed by infiltration from the surface store. It produces two outflow pathways (threshold-based hypodermic flow and continuous baseflow) and is also subject to evapotranspiration from remaining PET demand.

- **Threshold-based drainage**: Several outflows in CEQUEAU activate only when the store level exceeds a threshold. This allows the model to represent nonlinear behavior where certain flow pathways only contribute during wet conditions.

- **Continuous drainage**: Other outflows are proportional to the current store level regardless of any threshold, providing a baseline contribution at all times.

- **Routing delay**: A pure time translation applied to the total streamflow before output, representing the travel time of water through the channel network to the catchment outlet.

## How It Works

CEQUEAU operates on a daily time step, processing precipitation and potential evapotranspiration through the following sequence:

**Step 1: Precipitation input**. All precipitation enters the surface store directly. Unlike the original CEQUEAU model, the simplified version does not partition precipitation between impervious surface runoff and soil input (the TRI coefficient is set to zero).

**Step 2: Surface evapotranspiration**. The surface store loses water to evapotranspiration. Actual evapotranspiration is limited by both the PET demand and the available water, with a linear scaling factor that depends on the ratio of the store level to half its capacity ($X_5/2$). When the store is more than half full, actual ET equals potential ET; below that, it decreases linearly.

**Step 3: Infiltration (percolation)**. Water above the infiltration threshold $X_1$ percolates to the groundwater store at a rate controlled by the infiltration constant $X_3$. This is the only pathway connecting the two reservoirs.

**Step 4: Surface drainage**. The surface store produces three outflows in sequence: threshold-based lateral drainage (above $X_2$, controlled by $X_4$), continuous lateral drainage (controlled by $X_4 \cdot X_8$), and overflow if the store exceeds its capacity $X_5$. Each outflow is subtracted from the store before the next is computed, so their order matters.

**Step 5: Groundwater dynamics**. The groundwater store receives the infiltrated water and produces two outflows: threshold-based hypodermic flow (above $X_7$, controlled by $X_4 \cdot X_9$) and continuous baseflow (controlled by $X_4 \cdot X_8 \cdot X_9^2$). Any remaining PET demand after surface evapotranspiration is applied to the groundwater store, again with linear scaling relative to $X_7$.

**Step 6: Total streamflow and delay**. The five outflow components are summed to produce total streamflow, which is then delayed by $X_6$ time steps using linear interpolation for non-integer delays.

## Parameters

CEQUEAU (CEQU variant) has nine calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ | Infiltration threshold | 0–3000 | mm | Surface store level above which water infiltrates to the groundwater store. Higher values reduce percolation. |
| $X_2$ | Soil drainage threshold | 1–3000 | mm | Surface store level above which threshold-based lateral drainage occurs. Controls when quick lateral flow activates. |
| $X_3$ | Infiltration constant | 1–100 | - | Controls the rate of infiltration. Larger values slow infiltration to the groundwater store. |
| $X_4$ | Upper drainage constant | 1–50 | - | Primary drainage time constant for the surface store. Also appears as a factor in groundwater drainage constants. |
| $X_5$ | Surface store capacity | 1–8000 | mm | Maximum capacity of the surface (soil) reservoir. Also determines the evapotranspiration scaling threshold at $X_5/2$. |
| $X_6$ | Routing delay | 0.1–20 | days | Pure time translation applied to total streamflow. Reflects channel travel time to the outlet. |
| $X_7$ | Groundwater drainage threshold | 0.01–500 | mm | Groundwater store level above which hypodermic flow occurs. Also scales groundwater evapotranspiration. |
| $X_8$ | Lower drainage constant | 1–1000 | - | Multiplier for continuous (slow) drainage from the surface store. Also contributes to groundwater baseflow constant. |
| $X_9$ | Groundwater drainage constant | 1–3000 | - | Controls both hypodermic flow rate (as $X_4 \cdot X_9$) and baseflow rate (as $X_4 \cdot X_8 \cdot X_9^2$). |

**Understanding the parameters:**

- **$X_1$ and $X_2$** are thresholds that control when different drainage pathways activate. If $X_1$ is very large, almost no water reaches the groundwater store; if $X_2$ is very large, the threshold-based surface drainage rarely activates.
- **$X_3$ and $X_4$** are the primary drainage constants. $X_4$ appears in multiple outflow equations, making it a central parameter that influences the overall speed of the catchment response.
- **$X_5$** plays a dual role: it sets the overflow threshold for the surface store and determines when evapotranspiration becomes water-limited (at $X_5/2$).
- **$X_6$** is purely a timing parameter — it shifts the entire hydrograph without changing its shape.
- **$X_8$ and $X_9$** interact with $X_4$ to form composite drainage constants for the slower flow pathways. This parameterization means that adjusting $X_4$ affects all drainage rates simultaneously.

## Mathematical Formulation

### Initialization

The surface store is initialized at a fixed level, while the groundwater store is set to 20% of its capacity parameter:

$$S_0 = 500, \quad T_0 = 0.2 \cdot X_5$$

where $S$ is the surface store level and $T$ is the groundwater store level.

### Surface Store: Precipitation and Evapotranspiration

Precipitation is added directly to the surface store:

$$S \leftarrow S + P$$

Actual evapotranspiration from the surface store is limited by both the PET demand and available water, with linear scaling when the store is below half capacity:

$$E_s = \min\!\left(S,\ E \cdot \min\!\left(1,\ \frac{2S}{X_5}\right)\right)$$

The store is updated and the remaining PET demand is computed:

$$S \leftarrow S - E_s, \quad E' = E - E_s$$

### Surface Store: Infiltration

Water above the infiltration threshold percolates to the groundwater store:

$$I_s = \frac{\max(0,\ S - X_1)}{X_3}$$

$$S \leftarrow S - I_s$$

### Surface Store: Drainage

Three outflows are computed sequentially, each depleting the store before the next:

**Threshold-based lateral drainage** (activated when $S > X_2$):

$$Q_{s2} = \frac{\max(0,\ S - X_2)}{X_4}$$

$$S \leftarrow S - Q_{s2}$$

**Continuous lateral drainage** (always active):

$$Q_{s3} = \frac{S}{X_4 \cdot X_8}$$

$$S \leftarrow S - Q_{s3}$$

**Overflow** (when the store exceeds capacity):

$$Q_{s1} = \max(0,\ S - X_5)$$

$$S \leftarrow S - Q_{s1}$$

### Groundwater Store

The groundwater store receives infiltration from the surface store:

$$T \leftarrow T + I_s$$

**Threshold-based hypodermic flow** (activated when $T > X_7$):

$$Q_{t1} = \frac{\max(0,\ T - X_7)}{X_4 \cdot X_9}$$

$$T \leftarrow T - Q_{t1}$$

**Continuous baseflow**:

$$Q_{t2} = \frac{T}{X_4 \cdot X_8 \cdot X_9^2}$$

$$T \leftarrow T - Q_{t2}$$

**Groundwater evapotranspiration** from the remaining PET demand:

$$E_t = \min\!\left(T,\ E' \cdot \min\!\left(1,\ \frac{T}{X_7}\right)\right)$$

$$T \leftarrow T - E_t$$

### Total Streamflow

The total streamflow is the sum of all five drainage components:

$$Q_{total} = Q_{s1} + Q_{s2} + Q_{s3} + Q_{t1} + Q_{t2}$$

### Routing Delay

The total streamflow is delayed by $X_6$ time steps using a linear interpolation scheme. For a delay of $X_6$ days, a delay line of length $\lceil X_6 \rceil + 1$ distributes the flow between two adjacent positions to handle non-integer delays:

$$Q(t) = \text{delayed}(Q_{total},\ X_6)$$

## Differences from the Original CEQUEAU

The CEQU variant implemented in HOLMES differs from the original CEQUEAU model (Girard et al., 1972) in three ways:

1. **No impervious surface partitioning**: The TRI coefficient and HRIMP threshold are removed. All precipitation enters the surface store directly, reducing the parameter count by two.

2. **Fixed evapotranspiration threshold**: The original model uses a separate parameter (HINT) as the threshold above which actual ET equals potential ET. The simplified version fixes this threshold at half the surface store capacity ($X_5/2$), eliminating one parameter.

3. **Added routing delay**: A pure time delay parameter ($X_6$) is added to translate the total streamflow in time, representing channel routing. The original model handles routing through its distributed grid structure.

## References

Girard, G., Morin, G., & Charbonneau, R. (1972). Modèle précipitations-débits à discrétisation spatiale. *Cahiers ORSTOM, Série Hydrologie*, IX(4), 35-52.

Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit*. PhD Thesis, INPG Grenoble, Appendix 1, pp. 322-326. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
