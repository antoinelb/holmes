# Snow Models

## CemaNeige Model

### Overview

In many catchments worldwide, snow plays a fundamental role in the hydrological cycle. Precipitation falls as snow during cold periods, accumulates in a snowpack, and releases water during spring melt—fundamentally altering the timing and magnitude of streamflow compared to rain-fed catchments. Understanding and modeling these processes is essential for water resources management in mountain regions.

CemaNeige (pronounced "say-ma-nezh") is a degree-day snow accounting model developed alongside GR4J by researchers at IRSTEA (formerly Cemagref) in France. The name means "snow accounting" in French. Like GR4J, CemaNeige emphasizes parsimony: it captures the essential dynamics of snow accumulation and melt with just three parameters, making it practical for catchments where detailed snow observations are unavailable.

CemaNeige operates as a preprocessor to the hydrological model. It receives precipitation and temperature, tracks snowpack evolution across elevation bands, and outputs effective precipitation (rain plus snowmelt) that feeds into GR4J or the bucket model.

### Key Concepts

- **Degree-day method**: A simple approach relating snowmelt to air temperature. Each degree above freezing produces a certain amount of melt. While physically simplistic, it works remarkably well in practice because temperature correlates with the energy balance components that drive melt.

- **Snow water equivalent (SWE)**: The amount of water contained in the snowpack, measured as the depth of water that would result if the snow melted instantaneously. More meaningful than snow depth because it accounts for snow density.

- **Thermal state**: The internal "temperature" of the snowpack. A cold snowpack (negative thermal state) must warm up before melt can begin, creating a delay between warm temperatures and melt onset.

- **Elevation bands**: Mountain catchments span wide elevation ranges with very different temperatures. CemaNeige divides the catchment into elevation layers, each with its own temperature and snowpack, to better represent spatial variability.

- **Rain-snow partitioning**: The transition between rain and snow is not sharp—near 0°C, precipitation can be a mixture. CemaNeige uses a linear transition over a 4°C temperature range.

### How It Works

CemaNeige processes precipitation through a sequence of steps for each elevation band:

**Step 1: Temperature adjustment**. The measured temperature (usually from a valley station) is adjusted for each elevation band using a temperature lapse rate that varies by day of year.

**Step 2: Rain-snow partitioning**. Precipitation divides between rain (passes through immediately) and snow (accumulates in the snowpack) based on air temperature.

**Step 3: Thermal state update**. The snowpack's thermal state evolves toward the current air temperature. A cold snowpack "remembers" previous cold periods and must warm before melting.

**Step 4: Melt calculation**. When the thermal state reaches freezing and air temperature exceeds freezing, melt occurs. The melt rate depends on temperature (degree-day factor) and snowpack size (small snowpacks melt faster per unit mass).

**Step 5: Aggregation**. Rain and melt from all elevation bands sum to give total effective precipitation for the hydrological model.

### Parameters

CemaNeige has three parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $C_{TG}$ | Thermal state coefficient | 0–1 | - | Controls how quickly the snowpack temperature responds to air temperature. Higher values = more "memory" of past conditions. |
| $K_f$ | Degree-day melt factor | 0–20 | mm/°C/day | Melt rate per degree above freezing. Higher values = faster melt. |
| $Q_{NBV}$ | Snowpack threshold | 50–800 | mm | Snowpack size for full melt efficiency. Below this, melt proceeds more slowly. |

**Understanding the parameters:**

- **$C_{TG}$** acts like thermal inertia. At $C_{TG} = 0$, the snowpack instantly matches air temperature. At $C_{TG} = 1$, the snowpack never responds (unrealistic). Typical values are 0.2–0.5.

- **$K_f$** varies by climate and terrain. Values around 3–5 mm/°C/day are typical for mid-latitude mountain catchments. Forested areas tend to have lower values due to shading.

- **$Q_{NBV}$ controls the transition from patchy to continuous snow cover. A small snowpack melts efficiently (high surface area relative to volume), while a deep snowpack melts at the full rate.

### Mathematical Formulation

#### Temperature Lapse Rate

For each elevation band $i$ with elevation $z_i$ and median catchment elevation $z_{median}$:

$$\Delta z_i = \frac{z_i - z_{median}}{100}$$

The temperature at each band is adjusted using a day-of-year-dependent lapse rate $\theta_{doy}$:

$$T_i = T_{measured} + \theta_{doy} \cdot \Delta z_i$$

The lapse rate varies seasonally, typically ranging from -0.4 to -0.5 °C per 100 m elevation.

#### Rain-Snow Partitioning

The fraction of precipitation falling as snow depends on temperature:

$$f_{solid} = \begin{cases}
1 & T_i < -1°C \\
1 - \frac{T_i + 1}{4} & -1°C \leq T_i \leq 3°C \\
0 & T_i > 3°C
\end{cases}$$

Precipitation partitions as:

$$P_{snow,i} = f_{solid} \cdot P_i$$

$$P_{rain,i} = (1 - f_{solid}) \cdot P_i$$

The snowpack accumulates:

$$SWE_i \leftarrow SWE_i + P_{snow,i}$$

#### Thermal State Evolution

The thermal state $U_i$ evolves as an exponential filter:

$$U_i \leftarrow \min\left(C_{TG} \cdot U_i + (1 - C_{TG}) \cdot T_i, \, 0\right)$$

The thermal state is bounded at 0°C (once the snowpack reaches melting temperature, it cannot get warmer without melting).

#### Snowmelt Calculation

Melt occurs only when the thermal state reaches freezing ($U_i \geq 0$) and air temperature exceeds the threshold ($T_i > 0$):

**Potential melt:**

$$M_{pot,i} = K_f \cdot (T_i - 0)$$

**Melt efficiency factor:**

$$f_{NTS,i} = \min\left(\frac{SWE_i}{0.9 \cdot Q_{NBV}}, 1\right)$$

$$f_{melt,i} = 0.9 \cdot f_{NTS,i} + 0.1$$

This ensures melt efficiency ranges from 0.1 (nearly bare ground) to 1.0 (full snowpack).

**Actual melt:**

$$M_i = \min(M_{pot,i} \cdot f_{melt,i}, \, SWE_i)$$

$$SWE_i \leftarrow SWE_i - M_i$$

#### Effective Precipitation

Total effective precipitation for the hydrological model:

$$P_{eff} = \sum_i \left(P_{rain,i} + M_i\right)$$

### Elevation Layers

CemaNeige uses elevation layers to represent the temperature gradient within a catchment. Each layer receives the same precipitation but has different temperature based on its elevation.

**Why elevation layers matter:**

1. **Temperature varies with elevation**. At a typical lapse rate of -0.5°C/100m, a catchment spanning 1000m elevation difference has a 5°C temperature gradient.

2. **Snow accumulates at high elevations while rain falls below**. A single catchment-average temperature would miss this critical spatial pattern.

3. **Melt timing differs by elevation**. Low-elevation snow melts first, followed progressively by higher elevations, spreading the melt season over time.

**HOLMES implementation**: The number of elevation layers and their properties are defined in the catchment data file (CemaNeigeInfo.csv), which specifies the fraction of catchment area at each elevation and the median elevation of each band.

### Practical Considerations

#### When to Enable CemaNeige

Enable CemaNeige when:

- The catchment experiences significant snowfall (>10% of annual precipitation)
- You observe a snowmelt-driven spring flood
- The catchment contains high-elevation areas where winter precipitation accumulates

Skip CemaNeige when:

- The catchment rarely receives snow
- Temperatures seldom drop below freezing
- You're working in tropical or subtropical climates

#### Interpreting Parameter Values

- **Low $C_{TG}$ (0.1–0.3)**: Snowpack responds quickly to temperature changes. Appropriate for shallow snowpacks or maritime climates.
- **High $C_{TG}$ (0.4–0.6)**: Snowpack responds slowly. Appropriate for deep, continental snowpacks.
- **Low $K_f$ (1–3)**: Slow melt rates. Forested catchments, high latitude, or shaded terrain.
- **High $K_f$ (5–10)**: Fast melt rates. Open terrain, strong solar radiation.

#### Common Issues

1. **Too early melt**: If simulated streamflow peaks before observed, try increasing $C_{TG}$ (more thermal inertia) or decreasing $K_f$ (slower melt).

2. **Too late melt**: If simulated streamflow peaks after observed, try decreasing $C_{TG}$ or increasing $K_f$.

3. **Wrong melt duration**: If melt is too concentrated or too spread out, adjust $Q_{NBV}$. Higher values spread melt over a longer period.

4. **Elevation data**: Ensure elevation bands properly represent the catchment's hypsometry (distribution of area with elevation).

### References

Valéry, A., Andréassian, V., & Perrin, C. (2014). 'As simple as possible but not simpler': What is useful in a temperature-based snow-accounting routine? Part 2 – Sensitivity analysis of the Cemaneige snow accounting routine on 380 catchments. *Journal of Hydrology*, 517, 1176-1187. [https://doi.org/10.1016/j.jhydrol.2014.04.058](https://doi.org/10.1016/j.jhydrol.2014.04.058)

This paper presents the sensitivity analysis of CemaNeige across hundreds of catchments, providing guidance on parameter ranges and model behavior.

Valéry, A., Andréassian, V., & Perrin, C. (2014). 'As simple as possible but not simpler': What is useful in a temperature-based snow-accounting routine? Part 1 – Comparison of six snow accounting routines on 380 catchments. *Journal of Hydrology*, 517, 1166-1175. [https://doi.org/10.1016/j.jhydrol.2014.04.059](https://doi.org/10.1016/j.jhydrol.2014.04.059)

The companion paper comparing CemaNeige to other snow models, demonstrating its effectiveness despite its simplicity.
