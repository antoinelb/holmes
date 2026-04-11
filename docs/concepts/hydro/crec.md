# CREC Model

## Overview

CREC (Centre de Recherche en Eau de Chatou) is a six-parameter daily lumped rainfall-runoff model developed at the Chatou Water Research Centre, part of Électricité de France (EDF).
The model is named after its institution of origin, reflecting its roots in French operational hydrology for hydropower generation.

CREC uses a sigmoid function to partition rainfall between direct runoff and soil infiltration based on current soil moisture.
This moisture-dependent splitting is the model's defining feature: rather than using fixed ratios or saturation curves, the partitioning smoothly transitions as the catchment wets up.
With six parameters, a nonlinear surface routing store, and a simple delay function, CREC occupies a middle ground between the parsimony of GR4J and the explicit flow-path separation of the bucket model.

The model structure consists of three interconnected stores: a soil moisture store that controls the rainfall split and evapotranspiration, a surface routing store with nonlinear (quadratic) drainage, and a groundwater store that receives percolation and produces baseflow through linear drainage.

## Key Concepts

- **Sigmoid splitting function**: A logistic function that smoothly partitions incoming precipitation between direct runoff and soil infiltration.
The split depends on current soil moisture relative to parameter $X_3$: when the soil is wet ($S \gg X_3$), most rainfall becomes runoff; when dry ($S \ll X_3$), most infiltrates.

- **Nonlinear (quadratic) routing**: The surface store empties following a quadratic relationship $Q = R^2 / (R + X_1)$, meaning outflow increases faster than storage.
This produces sharper flood peaks than linear reservoirs and better represents overland flow dynamics.

- **Linear percolation**: Water moves from the surface store to the groundwater store at a rate proportional to the surface store content ($R / X_5$), representing slow drainage through the soil column.

- **Groundwater baseflow**: The deep store drains linearly at rate $T / X_2$, producing the sustained low-flow component of the hydrograph.

- **Routing delay**: A simple translation of the combined hydrograph by $X_6$ days using linear interpolation, representing channel travel time.

## How It Works

The CREC model processes precipitation and evapotranspiration through the following steps:

**Step 1: Sigmoid rainfall partitioning**.
Incoming precipitation $P$ is split between direct runoff ($P_r$) entering the surface store and infiltration ($P_s$) entering the soil store.
The split uses a logistic function centered on the soil moisture level: $P_r = P / (1 + \exp((X_3 - S) / X_4))$.
When the soil is saturated, the exponential term vanishes and most rainfall becomes runoff.
When the soil is dry, the exponential term dominates and most rainfall infiltrates.

**Step 2: Soil moisture accounting**.
The infiltrated portion $P_s$ is added to the soil store $S$.
Evapotranspiration is then extracted as $E_s = E \cdot (1 - \exp(-S / X_F))$, where $X_F = 245$ mm is a fixed constant.
This formulation ensures that actual evapotranspiration approaches the potential rate when the soil is wet and decreases exponentially as the soil dries.

**Step 3: Surface routing with nonlinear drainage**.
Direct runoff $P_r$ enters the surface store $R$.
The store empties through two mechanisms: a quadratic outflow $Q_r = R^2 / (R + X_1)$ that produces the fast streamflow component, and a linear percolation $I_r = R / X_5$ that feeds the groundwater store.

**Step 4: Groundwater storage and baseflow**.
Percolation $I_r$ enters the groundwater store $T$, which drains linearly at rate $Q_t = T / X_2$ to produce baseflow.

**Step 5: Routing delay**.
The total outflow ($Q_r + Q_t$) is delayed by $X_6$ days using linear interpolation between adjacent time steps, accounting for channel routing.

## Parameters

The CREC model has six calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ | Ground reservoir emptying constant | 1–1000 | days | Controls how quickly the surface store empties via nonlinear drainage. Larger values produce slower, more subdued flood peaks. |
| $X_2$ | Linear percolation parameter | 1–1000 | - | Time constant for groundwater drainage. Larger values produce slower, more sustained baseflow. |
| $X_3$ | Splitting parameter for raw rainfall | 0–1000 | mm | Soil moisture threshold for the sigmoid split. When $S = X_3$, precipitation is split equally between runoff and infiltration. |
| $X_4$ | Splitting parameter for PET production | 1–500 | mm | Controls the sharpness of the sigmoid transition. Smaller values produce a sharper switch between infiltration and runoff. |
| $X_5$ | Linear emptying parameter of soil reservoir | 1–1000 | - | Controls the percolation rate from the surface to the groundwater store. Larger values mean slower percolation. |
| $X_6$ | Delay parameter | 0.5–5 | days | Translation time for flow to reach the outlet. Reflects channel length and velocity. |

**Understanding the parameters:**

- **$X_1$** governs the nonlinear routing behavior.
For low storage levels, outflow approximates $R^2 / X_1$ (quadratic), making the response slow.
For high storage levels, outflow approaches $R$ (nearly all water leaves), making the response fast.
- **$X_2$ and $X_5$** together control the baseflow regime.
Water must first percolate from the surface store (rate $1/X_5$) and then drain from the groundwater store (rate $1/X_2$), creating a two-step delay.
- **$X_3$ and $X_4$** define the sigmoid splitting curve.
$X_3$ sets *where* the transition occurs (the soil moisture level at the inflection point), while $X_4$ sets *how sharply* it transitions.
A small $X_4$ creates a near-threshold behavior; a large $X_4$ creates a gradual transition.
- **$X_6$** is purely a timing parameter that shifts the hydrograph without changing its shape.

## Mathematical Formulation

### Initialization

Initial store levels and fixed constant:

$$S_0 = 250, \quad R_0 = 10, \quad T_0 = 100, \quad X_F = 245$$

where $S$ is soil moisture, $R$ is the surface routing store, $T$ is the groundwater store, and $X_F$ is a fixed evapotranspiration scaling constant.

### Sigmoid Rainfall Partitioning

Precipitation $P$ is split using a logistic (sigmoid) function:

$$P_r = \frac{P}{1 + \exp\left(\frac{X_3 - S}{X_4}\right)}$$

$$P_s = P - P_r$$

where $P_r$ is direct runoff entering the surface store and $P_s$ is the portion entering the soil store.

The sigmoid function $\sigma(S) = 1 / (1 + \exp((X_3 - S) / X_4))$ has the following properties:

- When $S = X_3$: $\sigma = 0.5$, so precipitation splits evenly
- When $S \gg X_3$: $\sigma \to 1$, so nearly all precipitation becomes runoff
- When $S \ll X_3$: $\sigma \to 0$, so nearly all precipitation infiltrates
- $X_4$ controls the slope at the inflection point

### Soil Moisture Dynamics

The soil store gains water from infiltration and loses water to evapotranspiration:

$$S \leftarrow S + P_s$$

$$E_s = E \cdot \left(1 - \exp\left(\frac{-S}{X_F}\right)\right)$$

$$S \leftarrow \max(S - E_s, 0)$$

The exponential evapotranspiration formulation ensures that actual ET approaches potential ET when the soil is wet ($S \gg X_F$) and decreases as the soil dries.

### Surface Routing Store

The surface store receives direct runoff and produces outflow through two mechanisms:

$$R \leftarrow R + P_r$$

**Nonlinear (quadratic) outflow:**

$$Q_r = \frac{R^2}{R + X_1}$$

$$R \leftarrow R - Q_r$$

**Linear percolation to groundwater:**

$$I_r = \frac{R}{X_5}$$

$$R \leftarrow R - I_r$$

The quadratic outflow formula $R^2 / (R + X_1)$ behaves as:

- For small $R$: $Q_r \approx R^2 / X_1$ (slow, quadratic response)
- For large $R$: $Q_r \approx R - X_1$ (fast, nearly linear response)

### Groundwater Store

The groundwater store receives percolation and drains linearly:

$$T \leftarrow T + I_r$$

$$Q_t = \frac{T}{X_2}$$

$$T \leftarrow T - Q_t$$

### Total System Outflow

$$Q_{sys} = Q_r + Q_t$$

### Routing Delay

The routing delay is implemented using linear interpolation.
For a delay of $X_6$ days, the model maintains a delay array of size $\lceil X_6 \rceil + 1$ with weights:

$$d_{\lceil X_6 \rceil - 1} = \frac{1}{X_6 - \lceil X_6 \rceil + 3}, \quad d_{\lceil X_6 \rceil} = 1 - d_{\lceil X_6 \rceil - 1}$$

The delayed flow is computed by convolving the system outflow with this delay array:

$$Q(t) = \text{delayed}(Q_{sys}, X_6)$$

## References

Cormary, Y., & Guilbot, A. (1973). Étude des relations pluie-débit sur trois bassins versants d'investigation. *IAHS Publication*, 108, 265-279.

Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit*.  PhD Thesis, INPG Grenoble, Appendix 1, pp. 313-316. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
