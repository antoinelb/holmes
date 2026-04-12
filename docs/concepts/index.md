# Concepts

This section introduces the fundamental concepts behind rainfall-runoff modeling and explains the hydrological models, algorithms, and metrics implemented in HOLMES.

## What is Rainfall-Runoff Modeling?

Rainfall-runoff modeling is the process of simulating how precipitation falling on a catchment transforms into streamflow at the outlet. This transformation involves complex physical processes: water infiltrates into the soil, evaporates back to the atmosphere, percolates to groundwater, and eventually reaches the stream through various pathways. A rainfall-runoff model attempts to represent these processes mathematically, allowing us to predict streamflow from meteorological inputs.

Understanding these models is essential for water resources management, flood forecasting, drought assessment, and infrastructure design. Rather than solving the full physics of water movement through soil and aquifers (which would require detailed spatial data rarely available), conceptual models use simplified representations that capture the essential behavior of catchment hydrology.

## The Water Balance Concept

At its core, hydrological modeling relies on the water balance equation:

$$\frac{dS}{dt} = P - E - Q$$

where:

- $S$ is the water stored in the catchment (soil moisture, groundwater, snow)
- $P$ is precipitation (rain and snow)
- $E$ is evapotranspiration (water returning to the atmosphere)
- $Q$ is streamflow at the outlet

This simple equation states that changes in storage equal inputs minus outputs. All conceptual hydrological models are elaborations of this principle, adding reservoirs, pathways, and time delays to represent how water moves through the system.

## The HOLMES Modeling Chain

HOLMES implements a complete modeling chain for rainfall-runoff simulation. Each step builds on the previous one:

### 1. Potential Evapotranspiration (PET)

Before running a hydrological model, we need to estimate the atmospheric demand for water. PET represents the maximum amount of water that would evaporate and transpire if water were unlimited. HOLMES uses the [Oudin method](pet-models.md), which estimates PET from temperature and solar radiation alone, making it practical when detailed meteorological data are unavailable.

### 2. Snow Accumulation and Melt

In catchments with significant snowfall, precipitation does not immediately contribute to runoff. Snow accumulates during cold periods and releases water during melt, fundamentally altering the timing of streamflow. The [CemaNeige model](snow-models.md) tracks snowpack evolution using a degree-day approach, partitioning precipitation between rain and snow and calculating melt based on temperature.

### 3. Hydrological Transformation

The core of the modeling chain is the rainfall-runoff model that transforms effective precipitation (rainfall plus snowmelt) into streamflow. HOLMES implements several models:

- **[Bucket model](hydro/bucket.md)**: A six-parameter model based on linear reservoir theory with explicit fast and slow flow paths. Offers more flexibility in flow partitioning and often captures recession behavior well.
- **[CEQUEAU](hydro/cequeau.md)**: A nine-parameter two-reservoir model (the "CEQU" simplification of the original CEQUEAU) that produces multiple threshold-based and continuous flow pathways, giving it considerable flexibility in hydrograph shape.
- **[CREC](hydro/crec.md)**: A six-parameter model featuring a sigmoid rainfall-splitting function that smoothly partitions precipitation between runoff and infiltration based on soil moisture. Uses nonlinear (quadratic) surface routing.
- **[GARDENIA](hydro/gardenia.md)**: A six-parameter BRGM model originally developed for rainfall → piezometric-level forecasting. Uses three reservoirs in series with a quadratic soil outflow law and a calibratable PET correction coefficient.
- **[GR4J](hydro/gr4j.md)**: A parsimonious four-parameter model widely used in research and operations. It represents the catchment as two stores (production and routing) connected by unit hydrographs.
- **[HBV](hydro/hbv.md)**: A nine-parameter model following Bergström's HBV0 formulation from Perrin's thesis. Uses a non-linear soil production with five-sub-step integration, a two-outflow intermediate reservoir, capped percolation, and a triangular unit hydrograph.
- **[IHACRES](hydro/ihacres.md)**: A seven-parameter model from Jakeman et al. (1990) built around a dimensionless catchment moisture index with PET-modulated drying, midpoint-trapezoidal effective rainfall, and parallel fast/slow linear routing reservoirs sharing a multiplicative time-constant coupling.
- **[HYMOD](hydro/hymod.md)**: A six-parameter model using a Pareto-distributed soil moisture store (variable-source-area runoff generation) combined with three linear reservoirs in cascade for fast flow and one linear groundwater reservoir for baseflow.
- **[MARTINE](hydro/martine.md)**: A seven-parameter BRGM model (Mazenc et al. 1984) with overflow-based surface production, a calibratable fast/slow distribution coefficient, quadratic direct routing, a dual-pathway intermediate reservoir (linear drainage + overflow), and linear groundwater recession.
- **[NAM](hydro/nam.md)**: A ten-parameter port of HOOPLA's HM12 version of the Nielsen & Hansen (1973) Danish operational model. Seven reservoirs (surface, soil, two interflow cascade reservoirs, two overland-flow cascade reservoirs, and a groundwater *deficit* store) with three-branch evapotranspiration, capillary rise from the saturated zone, and a fractional-delay unit hydrograph.
- **[PDM](hydro/pdm.md)**: An eight-parameter Probability-Distributed Model (Moore & Clarke 1981) with Pareto-distributed soil moisture capacity, threshold-gated drainage to a cubic groundwater store, two-stage linear cascade for fast routing, and a fractional-delay unit hydrograph.
- **[SACRAMENTO](hydro/sacramento.md)**: A nine-parameter variant of the Burnash et al. (1973) NWSRFS operational model following Perrin's simplification. Uses five reservoirs (interception, tension water, free water, lower-zone routing, direct routing) with a filling-feedback percolation scheme, interflow and hypodermic pathways, and an upward mass-balance correction between the lower-zone store and the free-water store.
- **[TOPMODEL](hydro/topmodel.md)**: A seven-parameter variant of the Beven & Kirkby (1979) topographic-index model following Perrin's simplification. An interception store, an unbounded groundwater deficit store with two sigmoid partition functions (recharge and evapotranspiration), a quadratic surface routing reservoir, and a fractional-delay unit hydrograph — pedagogically interesting because it replaces hard saturation thresholds with smooth probabilistic partitions.
- **[XINANJIANG](hydro/xinanjiang.md)**: An eight-parameter variant of the Zhao et al. (1980) Chinese operational model. Uses two power-distributed saturation-excess reservoirs in series (soil + free-water) feeding a calibratable fast/slow routing split and a two-tap fractional-delay unit hydrograph.

### 4. Model Calibration

Hydrological models have parameters that cannot be measured directly and must be estimated by comparing model outputs to observed streamflow. This process, called calibration, searches for parameter values that minimize the difference between simulated and observed flows. HOLMES uses the [SCE-UA algorithm](calibration-algorithms.md), a global optimization method designed specifically for hydrological model calibration.

### 5. Performance Evaluation

After calibration, we need to assess how well the model performs. HOLMES provides several [performance metrics](metrics.md) that quantify different aspects of model accuracy:

- **RMSE** measures average error magnitude
- **NSE** measures skill relative to using the mean as a predictor
- **KGE** decomposes performance into correlation, variability bias, and mean bias

## Choosing the Right Model

The choice of model depends on your catchment characteristics and objectives. Each row below links to the full concept page for that model:

| Model | Params | Soil store | Flow partitioning | Routing | GW exchange | Equifinality | Best for |
|-------|:------:|------------|-------------------|---------|:-----------:|:------------:|----------|
| [Bucket](hydro/bucket.md) | 6 | Single bucket | Calibratable ($\alpha$, $\beta$) | Linear reservoirs | No | Higher | Catchments with distinct recession components |
| [CEQUEAU](hydro/cequeau.md) | 9 | Two-reservoir (surface + groundwater) | Threshold + continuous pathways | Pure time delay | No | Higher | Flexible hydrograph shapes, threshold-driven response |
| [CREC](hydro/crec.md) | 6 | Single bucket + sigmoid split | Sigmoid (moisture-dependent) | Quadratic + linear stores | No | Moderate | Catchments with moisture-dependent runoff generation |
| [GARDENIA](hydro/gardenia.md) | 6 | Surface + soil + groundwater in series | Overflow at surface + quadratic soil outflow | Fractional delay | No | Moderate | Catchments with a strong aquifer component; rainfall → piezometric-level use cases |
| [GR4J](hydro/gr4j.md) | 4 | Single reservoir | Fixed 90% / 10% | Unit hydrographs + nonlinear store | Yes ($X_2$) | Lower | Humid temperate catchments, benchmarking |
| [HBV](hydro/hbv.md) | 9 | Non-linear soil (five sub-steps) | Threshold upper + linear lower intermediate reservoir | Triangular unit hydrograph | No | Higher | Nordic / temperate catchments, operational forecasting |
| [IHACRES](hydro/ihacres.md) | 7 | Dimensionless moisture index (unbounded, PET-modulated decay) | Calibratable fast/slow fraction ($X_2$) | Parallel linear reservoirs ($X_3$ / $X_3 \cdot X_4$) + fractional delay | No | Moderate | Catchments where recession analysis drives calibration; teaching contrast to soil-bucket models |
| [HYMOD](hydro/hymod.md) | 6 | Pareto-distributed (variable source area) | Saturation excess + calibratable $\alpha$ | Three linear reservoirs cascade + one slow reservoir | No | Moderate | Catchments where saturated-area runoff dominates |
| [MARTINE](hydro/martine.md) | 7 | Single bucket (overflow) | Calibratable fast/slow fraction ($X_5$) | Quadratic direct store + dual-pathway intermediate + linear GW + fractional delay | No | Moderate | Regionalization studies; catchments with distinct interflow and baseflow components |
| [NAM](hydro/nam.md) | 10 | Surface store + soil store with capillary rise | Three-branch ET + soil-ratio-driven overland/interflow/percolation split | Two parallel two-reservoir cascades + fractional-delay UH | Yes (deficit-based, threshold $X_1$) | Higher | Catchments where overland flow and interflow must be modelled separately; Scandinavian operational use cases |
| [PDM](hydro/pdm.md) | 8 | Pareto-distributed (variable source area) | Saturation excess + infiltration excess + threshold drainage | Two linear reservoirs cascade + cubic GW store + fractional delay | No | Moderate | Catchments with variable-source-area runoff and nonlinear baseflow recession; British operational use cases |
| [SACRAMENTO](hydro/sacramento.md) | 9 | Interception + tension + free water (three-store cascade) | Percolation with filling-feedback + threshold overflow | Direct routing store + fractional-delay register | Yes (via $X_8$ deep percolation) | Higher | Catchments with clear baseflow separation; operational NWS-style use cases |
| [TOPMODEL](hydro/topmodel.md) | 7 | Interception + unbounded groundwater deficit | Sigmoid recharge + sigmoid groundwater ET (logistic, no thresholds) | Quadratic surface store + exponential baseflow + fractional delay | No | Moderate | Catchments where smooth saturation-area dynamics matter; pedagogical contrast with threshold-based models |
| [XINANJIANG](hydro/xinanjiang.md) | 8 | Two power-distributed reservoirs (soil + free-water) | Saturation excess (fixed $B = 0.25$, calibratable $X_8$) | Fast/slow linear reservoirs + two-tap unit hydrograph | No | Moderate | Catchments with strong spatial variability of storage capacity; Chinese / monsoon operational use cases |

<!--
  Adding a new hydro model? Append one row to this table. The column schema
  is: Model (linked) | Params | Soil store | Flow partitioning | Routing |
  GW exchange | Equifinality | Best for. Keep rows ordered to match the
  alphabetical order in docs/concepts/hydro/ (which is the order awesome-nav
  will show in the sidebar).
-->

For catchments with significant snow, enable CemaNeige regardless of which hydrological model you choose.

## Further Reading

Each concept page provides detailed explanations, mathematical formulations, and practical guidance:

- [Bucket Model](hydro/bucket.md) - Linear reservoir model with flexible flow partitioning
- [CEQUEAU Model](hydro/cequeau.md) - Two-reservoir model with threshold-based and continuous flow pathways
- [CREC Model](hydro/crec.md) - Sigmoid splitting with nonlinear surface routing
- [GARDENIA Model](hydro/gardenia.md) - BRGM three-reservoir model with quadratic soil outflow and PET correction
- [GR4J Model](hydro/gr4j.md) - Parsimonious four-parameter model
- [HBV Model](hydro/hbv.md) - Nine-parameter Bergström formulation with five-sub-step soil production and triangular routing
- [IHACRES Model](hydro/ihacres.md) - Seven-parameter moisture-index model with PET-modulated drying and parallel fast/slow linear routing
- [HYMOD Model](hydro/hymod.md) - Pareto-distributed soil store with three-reservoir fast cascade
- [MARTINE Model](hydro/martine.md) - Seven-parameter BRGM model with quadratic routing and dual-pathway intermediate reservoir
- [NAM Model](hydro/nam.md) - Ten-parameter Danish HM12 port with seven reservoirs, groundwater-deficit store, and capillary rise
- [PDM Model](hydro/pdm.md) - Pareto-distributed soil store with cubic groundwater and threshold drainage
- [SACRAMENTO Model](hydro/sacramento.md) - Five-reservoir Burnash/NWSRFS cascade with filling-feedback percolation and deep-percolation damping
- [TOPMODEL](hydro/topmodel.md) - Seven-parameter Beven & Kirkby model with sigmoid recharge/ET partitioning and exponential baseflow
- [XINANJIANG Model](hydro/xinanjiang.md) - Two power-distributed saturation-excess reservoirs with fast/slow routing split
- [Snow Models (CemaNeige)](snow-models.md) - Snow accumulation and melt
- [PET Models (Oudin)](pet-models.md) - Potential evapotranspiration calculation
- [Calibration Algorithms (SCE-UA)](calibration-algorithms.md) - Automatic parameter optimization
- [Performance Metrics](metrics.md) - RMSE, NSE, and KGE explained
