# Bucket Model

## Overview

The bucket model is a conceptual rainfall-runoff model based on the linear reservoir framework. It represents a catchment using interconnected "buckets" or reservoirs: a soil moisture store that controls evaporation, and two routing stores that produce slow (baseflow) and fast (quickflow) components of streamflow.

The model's modular structure explicitly separates different flow pathways, making it straightforward to understand how each component contributes to the total hydrograph. With six parameters, the bucket model offers more flexibility than GR4J in representing flow partitioning and recession behavior, though this comes with increased risk of parameter equifinality.

Bucket-style models (also called tank models) have a long history in hydrology and remain widely used. The explicit linear reservoir structure often captures recession dynamics well, particularly in catchments with distinct baseflow and quickflow components.

## Key Concepts

- **Soil moisture store**: The primary reservoir that receives precipitation and loses water to evapotranspiration. When full, excess water drains to the routing stores.

- **Linear reservoir**: A fundamental concept in hydrology where outflow is proportional to storage. The constant of proportionality is the recession coefficient $K$, representing the time for storage to decrease to $1/e$ (about 37%) of its initial value.

- **Baseflow (slow flow)**: The sustained flow that continues long after rainfall stops, fed by gradual drainage from soil and groundwater. Characterized by a long recession time constant.

- **Quickflow (fast flow)**: The rapid response to rainfall that produces flood peaks. Represents surface runoff and fast subsurface flow paths.

- **Routing delay**: The time required for water to travel from the catchment to the outlet, implemented as a simple translation of the hydrograph.

## How It Works

The bucket model processes precipitation and evapotranspiration through the following steps:

**Step 1: Precipitation partitioning**. Incoming precipitation splits between water that enters the soil store and water that bypasses it entirely (direct runoff). The parameter $\beta$ controls this split.

**Step 2: Soil moisture accounting**. Water entering the soil store is subject to evapotranspiration. During wet periods (precipitation exceeds PET), the store fills up. When the store exceeds its capacity $C_{soil}$, the excess becomes infiltration. During dry periods (PET exceeds precipitation), the store depletes exponentially.

**Step 3: Infiltration partitioning**. Water that infiltrates below the soil store splits between the slow store (becoming baseflow) and the fast store (becoming quickflow). The parameter $\alpha$ controls this split.

**Step 4: Linear reservoir outflow**. Each routing store releases water at a rate proportional to its content. The slow store uses time constant $K_r$, while the fast store uses $K_t$.

**Step 5: Routing delay**. The combined outflow is delayed by $\delta$ days to account for channel routing, using linear interpolation between adjacent time steps.

## Parameters

The bucket model has six calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $C_{soil}$ | Soil moisture capacity | 10–1000 | mm | Maximum water storage in the soil. Larger values allow more water retention before runoff occurs. |
| $\alpha$ | Infiltration split ratio | 0–1 | - | Fraction of infiltration going to the slow store. Higher values produce more baseflow-dominated hydrographs. |
| $K_r$ | Slow recession constant | 1–200 | days | Time scale for baseflow depletion. Larger values produce slower, more sustained baseflow. |
| $\delta$ | Routing delay | 2–10 | days | Translation time for flow to reach the outlet. Reflects channel length and velocity. |
| $\beta$ | Direct runoff fraction | 0–1 | - | Fraction of precipitation bypassing the soil store. Higher values produce flashier response. |
| $K_t$ | Fast recession constant | 1–400 | days | Time scale for quickflow depletion. Typically much smaller than $K_r$. |

**Understanding the parameters:**

- **$C_{soil}$** acts like the soil depth times porosity—how much water can the soil hold before it overflows?
- **$\alpha$ and $\beta$** together control the shape of the hydrograph. High $\beta$ and low $\alpha$ produce flashy, peaked responses; low $\beta$ and high $\alpha$ produce subdued, baseflow-dominated responses.
- **$K_r$ and $K_t$** control how quickly the catchment "forgets" past rainfall. A stream with $K_r = 100$ days will have baseflow lasting months after rainfall stops.
- **$\delta$** is primarily a timing parameter—it shifts the entire hydrograph but doesn't change its shape.

## Mathematical Formulation

### Initialization

Initial store levels:

$$S_0 = 0.5 \cdot C_{soil}, \quad R_0 = 10, \quad T_0 = 5$$

where $S$ is soil moisture, $R$ is the slow routing store, and $T$ is the fast routing store.

### Precipitation Partitioning

Precipitation $P$ splits into soil input and direct fast flow:

$$P_s = (1 - \beta) \cdot P$$

$$P_r = \beta \cdot P$$

where $P_s$ enters the soil store and $P_r$ goes directly to the fast routing store.

### Soil Moisture Dynamics

**Wet conditions ($P_s \geq E$):**

When precipitation input exceeds evapotranspiration demand:

$$S \leftarrow S + P_s - E$$

Any excess above capacity becomes infiltration:

$$I_s = \max(S - C_{soil}, 0)$$

$$S \leftarrow S - I_s$$

**Dry conditions ($P_s < E$):**

When evapotranspiration demand exceeds precipitation input, the store depletes exponentially:

$$S \leftarrow S \cdot \exp\left(\frac{P_s - E}{C_{soil}}\right)$$

This formulation ensures that evaporation decreases as the soil dries (water-limited evaporation).

### Infiltration Partitioning

Infiltration from the soil store splits between routing stores:

$$I_{slow} = (1 - \alpha) \cdot I_s$$

$$I_{fast} = \alpha \cdot I_s$$

### Routing Stores

Both routing stores follow linear reservoir dynamics.

**Slow store (baseflow):**

$$R \leftarrow R + I_{slow}$$

$$Q_r = \frac{R}{K_r}$$

$$R \leftarrow R - Q_r$$

**Fast store (quickflow):**

$$T \leftarrow T + P_r + I_{fast}$$

$$Q_t = \frac{T}{K_t}$$

$$T \leftarrow T - Q_t$$

### Total System Outflow

$$Q_{sys} = Q_r + Q_t$$

### Routing Delay

The routing delay is implemented using linear interpolation. For a delay of $\delta$ days, the model maintains a delay array and shifts flows forward:

$$Q(t) = \text{delayed}(Q_{sys}, \delta)$$

The delay uses linear interpolation when $\delta$ is not an integer, distributing water between adjacent time steps.

## References

Thornthwaite, C. W., & Mather, J. R. (1955). *The water balance*. Publications in Climatology, 8(1). Drexel Institute of Technology, Laboratory of Climatology.

Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit*  PhD Thesis, INPG Grenoble, Appendix 1, pp. 313-316. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
