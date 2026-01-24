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

The core of the modeling chain is the rainfall-runoff model that transforms effective precipitation (rainfall plus snowmelt) into streamflow. HOLMES implements two models:

- **[GR4J](gr4j.md)**: A parsimonious four-parameter model widely used in research and operations. It represents the catchment as two stores (production and routing) connected by unit hydrographs.
- **[Bucket model](bucket.md)**: A six-parameter model based on linear reservoir theory with explicit fast and slow flow paths. Offers more flexibility in flow partitioning and often captures recession behavior well.

### 4. Model Calibration

Hydrological models have parameters that cannot be measured directly and must be estimated by comparing model outputs to observed streamflow. This process, called calibration, searches for parameter values that minimize the difference between simulated and observed flows. HOLMES uses the [SCE-UA algorithm](calibration-algorithms.md), a global optimization method designed specifically for hydrological model calibration.

### 5. Performance Evaluation

After calibration, we need to assess how well the model performs. HOLMES provides several [performance metrics](metrics.md) that quantify different aspects of model accuracy:

- **RMSE** measures average error magnitude
- **NSE** measures skill relative to using the mean as a predictor
- **KGE** decomposes performance into correlation, variability bias, and mean bias

## Choosing the Right Model

The choice of model depends on your catchment characteristics and objectives:

| Consideration | GR4J | Bucket Model |
|--------------|------|--------------|
| Parameters | 4 | 6 |
| Flow partitioning | Fixed (90%/10%) | Calibratable ($\alpha$, $\beta$) |
| Routing | Unit hydrographs + nonlinear store | Linear reservoirs |
| Groundwater exchange | Yes ($X_2$ parameter) | No |
| Equifinality risk | Lower | Higher |
| Best for | Humid temperate catchments, benchmarking | Catchments with distinct recession components |

For catchments with significant snow, enable CemaNeige regardless of which hydrological model you choose.

## Further Reading

Each concept page provides detailed explanations, mathematical formulations, and practical guidance:

- [GR4J Model](gr4j.md) - Parsimonious four-parameter model
- [Bucket Model](bucket.md) - Linear reservoir model with flexible flow partitioning
- [Snow Models (CemaNeige)](snow-models.md) - Snow accumulation and melt
- [PET Models (Oudin)](pet-models.md) - Potential evapotranspiration calculation
- [Calibration Algorithms (SCE-UA)](calibration-algorithms.md) - Automatic parameter optimization
- [Performance Metrics](metrics.md) - RMSE, NSE, and KGE explained
