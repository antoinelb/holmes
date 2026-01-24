# Potential Evapotranspiration Models

## Oudin Model

### Overview

Potential evapotranspiration (PET) represents the maximum amount of water that would evaporate from a well-watered surface given unlimited water supply. It quantifies the atmospheric demand for water—how much the atmosphere "wants" to extract from the land surface based on available energy and vapor pressure deficit.

PET is a critical input for rainfall-runoff models because it determines how much precipitation returns to the atmosphere versus how much becomes streamflow. Without accounting for evapotranspiration, a water balance model would systematically overestimate runoff.

The Oudin method is a parsimonious approach to estimating PET that requires only temperature and latitude. Developed specifically for use with lumped rainfall-runoff models like GR4J, it trades physical complexity for practical applicability. While more sophisticated methods (like Penman-Monteith) require wind speed, humidity, and radiation measurements that are often unavailable, the Oudin method can be applied anywhere temperature records exist.

### Key Concepts

- **Evapotranspiration**: The combined process of evaporation from surfaces (lakes, soil, wet vegetation) and transpiration from plants. Together, these processes return water to the atmosphere.

- **Potential vs. actual evapotranspiration**: PET assumes unlimited water availability. Actual evapotranspiration (AET) may be less than PET when water is limiting (dry soil, stressed plants). The hydrological model calculates AET based on soil moisture availability.

- **Extraterrestrial radiation**: Solar radiation at the top of the atmosphere before any absorption by clouds or the atmosphere. It depends only on latitude and day of year, making it predictable from astronomical calculations.

- **Energy-temperature relationship**: Temperature serves as a proxy for the energy available for evaporation. Warmer air typically indicates more incoming solar radiation and greater evaporative demand.

### How It Works

The Oudin method calculates PET in two steps:

**Step 1: Calculate extraterrestrial radiation**. Using latitude and day of year, compute the solar radiation that would reach the catchment if there were no atmosphere. This captures the seasonal and latitudinal variation in available energy.

**Step 2: Convert to PET**. Scale the extraterrestrial radiation by a temperature-dependent factor. Above a threshold temperature, higher temperatures produce more PET. Below the threshold, PET is zero (no evaporation demand).

The method assumes that temperature captures the relevant energy balance information, avoiding the need for direct radiation measurements.

### Mathematical Formulation

#### Solar Geometry

The calculation begins with astronomical relationships that determine how much solar energy reaches the top of the atmosphere.

**Solar declination** (the angle between the Sun and the equatorial plane):

$$\delta = 0.409 \sin\left(\frac{2\pi \cdot DOY}{365} - 1.39\right)$$

where $DOY$ is the day of year (1–365).

**Inverse relative Earth-Sun distance** (accounts for Earth's elliptical orbit):

$$d_r = 1 + 0.033 \cos\left(\frac{2\pi \cdot DOY}{365}\right)$$

**Sunset hour angle** (determines day length):

$$\omega_s = \arccos\left(-\tan(\phi) \cdot \tan(\delta)\right)$$

where $\phi$ is latitude in radians. The argument is clamped to $[-1, 1]$ to handle polar latitudes where the sun doesn't set (midnight sun) or doesn't rise (polar night).

#### Extraterrestrial Radiation

The daily extraterrestrial radiation (energy per unit area at the top of the atmosphere):

$$R_e = \frac{24 \cdot 60}{\pi} G_{sc} \cdot d_r \left[\omega_s \sin(\phi) \sin(\delta) + \cos(\phi) \cos(\delta) \sin(\omega_s)\right]$$

where:

- $G_{sc} = 0.082$ MJ m⁻² min⁻¹ is the solar constant
- Result is in MJ m⁻² day⁻¹

#### Latent Heat of Vaporization

The energy required to evaporate water decreases slightly with temperature:

$$\lambda = 2.501 - 0.002361 \cdot T$$

where $\lambda$ is in MJ kg⁻¹ and $T$ is temperature in °C.

#### Potential Evapotranspiration

The Oudin formula for PET:

$$PET = \begin{cases}
\frac{R_e}{\lambda \cdot \rho} \cdot \frac{T + 5}{100} \cdot 1000 & T > -5°C \\
0 & T \leq -5°C
\end{cases}$$

where:

- $\rho = 1000$ kg m⁻³ is water density
- Result is in mm day⁻¹
- The factor $(T + 5)/100$ is an empirical calibration term

**Understanding the formula:**

The expression $R_e / (\lambda \cdot \rho)$ converts radiation energy to equivalent water depth (how much water could be evaporated by that energy). The factor $(T + 5)/100$ scales this based on temperature, with the +5 offset ensuring PET remains positive even at slightly negative temperatures (when sublimation can still occur).

### Constants and Parameters

The Oudin method uses fixed constants—there are no calibratable parameters:

| Constant | Value | Units | Description |
|----------|-------|-------|-------------|
| $G_{sc}$ | 0.082 | MJ m⁻² min⁻¹ | Solar constant |
| $\rho$ | 1000 | kg m⁻³ | Water density |
| $T_{offset}$ | 5 | °C | Empirical temperature offset |
| $T_{threshold}$ | -5 | °C | Minimum temperature for PET |

The only input parameter is **latitude**, which HOLMES obtains from the catchment data.

### Practical Considerations

#### Advantages of the Oudin Method

1. **Minimal data requirements**: Only needs temperature and location (latitude). No wind, humidity, or radiation measurements required.

2. **Robust for rainfall-runoff modeling**: Specifically designed and tested for use with lumped models like GR4J. The empirical calibration accounts for the fact that the hydrological model will further adjust actual evapotranspiration.

3. **Physically reasonable**: Despite its simplicity, captures the main drivers of evaporative demand—energy availability (radiation) and temperature.

4. **Consistent**: No subjective choices about crop coefficients, albedo, or other parameters that can introduce uncertainty.

#### Limitations

1. **No vegetation effects**: Does not distinguish between forest, grassland, or bare soil. In reality, vegetation type affects evapotranspiration rates.

2. **No wind or humidity**: Ignores atmospheric conditions that influence evaporation rate. May underperform in very windy or very humid conditions.

3. **Daily time step**: The formulation assumes daily averaging. Not suitable for sub-daily calculations without modification.

4. **Empirical calibration**: The $(T + 5)/100$ factor was calibrated against more complex PET methods and may not be optimal everywhere.

#### Comparison with Other Methods

| Method | Data Requirements | Complexity | Best For |
|--------|-------------------|------------|----------|
| **Oudin** | Temperature, latitude | Low | Lumped rainfall-runoff models |
| **Hargreaves** | Temperature, latitude | Low | Arid regions |
| **Penman-Monteith** | Temperature, humidity, wind, radiation | High | Irrigation scheduling, detailed studies |
| **Priestley-Taylor** | Temperature, radiation | Medium | Energy-limited environments |

For the purposes of educational rainfall-runoff modeling in HOLMES, the Oudin method provides an appropriate balance of simplicity and accuracy.

#### Typical PET Values

To help interpret model outputs, here are typical daily PET ranges:

| Climate | Summer | Winter |
|---------|--------|--------|
| Tropical | 4–6 mm/day | 3–5 mm/day |
| Mediterranean | 6–8 mm/day | 1–2 mm/day |
| Temperate | 3–5 mm/day | 0.5–1.5 mm/day |
| Continental | 4–6 mm/day | 0–1 mm/day |
| Subarctic | 2–4 mm/day | 0 mm/day |

If your calculated PET values fall outside these ranges, verify your input data (especially latitude and temperature units).

### References

Oudin, L., Hervieu, F., Michel, C., Perrin, C., Andréassian, V., Anctil, F., & Loumagne, C. (2005). Which potential evapotranspiration input for a lumped rainfall–runoff model?: Part 2—Towards a simple and efficient potential evapotranspiration model for rainfall–runoff modelling. *Journal of Hydrology*, 303(1-4), 290-306. [https://doi.org/10.1016/j.jhydrol.2004.08.026](https://doi.org/10.1016/j.jhydrol.2004.08.026)

This paper presents the Oudin method, comparing it against 27 other PET formulations across 308 catchments and showing that simple temperature-based methods work as well as complex ones for rainfall-runoff modeling.

Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). Crop evapotranspiration: Guidelines for computing crop water requirements. *FAO Irrigation and Drainage Paper 56*. Food and Agriculture Organization of the United Nations.

The definitive reference for the Penman-Monteith equation and evapotranspiration calculations. While more detailed than needed for HOLMES, it provides essential background on the physics of evapotranspiration.
