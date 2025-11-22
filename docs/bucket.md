# BUCKET Hydrological Model Documentation

## Overview

The BUCKET model (also known as HydroModel1 or HydroMod1) is a daily lumped rainfall-runoff model with six parameters. It is based on the Thornthwaite-Mather water balance approach (Thornthwaite & Mather, 1955) and builds upon the formulation described in Perrin (2000). The model simulates the transformation of precipitation into runoff through soil moisture accounting and dual-pathway routing (slow and fast flow components).

Originally programmed by G. Seiller at Université Laval (2013), modified by A. Thiboult (2016), and translated to Python by Gabriel Couture (2022).

## Model Parameters

The BUCKET model uses six calibrated parameters:

| Parameter | Symbol | Unit | Range* | Description |
|-----------|--------|------|--------|-------------|
| **P0** | $C_{soil}$ | mm | [10, 1000] | Maximum capacity of the soil reservoir |
| **P1** | $\alpha$ | - | [0, 1] | Soil reservoir overflow dissociation constant |
| **P2** | $k_R$ | days | [1, 200] | Slow routing reservoir emptying constant |
| **P3** | $\delta$ | days | [0, 10] | Routing delay |
| **P4** | $\beta$ | - | [0, 1] | Rainfall partitioning coefficient |
| **P5** | $k_T$ | days | [0.5, 50] | General routing time constant |

*Note: These ranges are inferred from physical constraints and typical hydrological values. The original HOOPLApy repository does not explicitly document parameter bounds in the public code.

## State Variables

The model maintains five state variables:

- $S$ : Level of the soil moisture reservoir (mm)
- $R$ : Level of the slow routing reservoir (mm)
- $T$ : Level of the fast routing reservoir (mm)
- $DL$ : Delay distribution array for routing lag
- $HY$ : Hydrograph array for delayed flow

## Mathematical Formulation

### 1. Rainfall Partitioning

The incoming precipitation is split into two components based on the partitioning coefficient:

**Slow flow precipitation:**
$$P_s = (1 - \beta) \cdot P$$

**Fast flow precipitation:**
$$P_r = P - P_s = \beta \cdot P$$

Where:
- $\beta$ controls the proportion of rainfall going directly to fast routing (typically 0.1-0.3)
- $(1 - \beta)$ controls the proportion going through soil moisture accounting

### 2. Soil Moisture Accounting

The soil moisture accounting component manages the soil reservoir ($S$) based on the balance between precipitation and evapotranspiration.

#### 2.1 Wet Conditions: $P_s \geq E$

When precipitation exceeds evapotranspiration, the soil reservoir fills:

**Soil reservoir update:**
$$S_{temp} = S + P_s - E$$

**Infiltration excess (overflow):**
$$I_s = \max(0, S_{temp} - C_{soil})$$

**Final soil state:**
$$S_{t+1} = S_{temp} - I_s$$

The soil reservoir cannot exceed its maximum capacity, so any excess becomes infiltration.

#### 2.2 Dry Conditions: $P_s < E$

When evapotranspiration exceeds precipitation, the soil reservoir depletes exponentially:

**Soil reservoir depletion:**
$$S_{t+1} = S \cdot \exp\left(\frac{P_s - E}{C_{soil}}\right)$$

**Infiltration:**
$$I_s = 0$$

This exponential depletion prevents the soil moisture from becoming negative and represents the difficulty of extracting water as the soil dries.

### 3. Routing Function

The routing function uses a dual-pathway approach with delayed response.

#### 3.1 Slow Routing Component (R)

The slow routing reservoir receives a portion of the infiltration and empties gradually:

**Reservoir input:**
$$R_{in} = I_s \cdot (1 - \alpha)$$

**Reservoir update:**
$$R_{temp} = R + R_{in}$$

**Slow flow:**
$$Q_R = \frac{R_{temp}}{k_R \cdot k_T}$$

**Updated reservoir:**
$$R_{t+1} = R_{temp} - Q_R$$

Where:
- $\alpha$ is the dissociation constant determining the split between slow and fast routing
- $k_R$ is the slow routing time constant
- $k_T$ is the general routing time constant

#### 3.2 Fast Routing Component (T)

The fast routing reservoir receives direct precipitation and a portion of infiltration:

**Reservoir input:**
$$T_{in} = P_r + I_s \cdot \alpha$$

**Reservoir update:**
$$T_{temp} = T + T_{in}$$

**Fast flow:**
$$Q_T = \frac{T_{temp}}{k_T}$$

**Updated reservoir:**
$$T_{t+1} = T_{temp} - Q_T$$

#### 3.3 Routing Delay

The model implements a routing delay ($\delta$) to account for travel time within the catchment:

**Delay discretization:**
$$n = \lceil \delta \rceil$$

**Delay distribution weights:**
$$
DL(i) = \begin{cases}
0 & \text{for } i = 0, 1, ..., n-2 \\
\frac{1}{\delta - (n-1) + 1} & \text{for } i = n-1 \\
1 - DL(n-1) & \text{for } i = n
\end{cases}
$$

This creates a linear interpolation between the two nearest integer time steps.

**Hydrograph update:**

At each time step, the hydrograph array is shifted:
$$HY(i) = HY(i+1) \text{ for } i = 0, 1, ..., n-1$$
$$HY(n) = 0$$

Then the current flow is distributed according to the delay:
$$HY(i) = HY(i) + DL(i) \cdot (Q_T + Q_R)$$

#### 3.4 Total Streamflow

The total streamflow is the first element of the delayed hydrograph:

$$Q(t) = \max(0, HY(0))$$

The max function ensures non-negative streamflow.

## Initial Conditions

The model initializes the reservoirs as follows:

- **Soil reservoir:** $S_0 = 0.5 \cdot C_{soil}$ (half capacity)
- **Slow routing reservoir:** $R_0 = 10$ mm
- **Fast routing reservoir:** $T_0 = 5$ mm
- **Delay distribution:** Calculated based on $\delta$
- **Hydrograph array:** $HY = \vec{0}$ (all zeros)

## Model Conceptual Diagram

```
    P ────┬─────────────────────────────────────┐
          │                                     │
          ↓                                     ↓
      (1-β)·P                                  β·P
       = Ps                                    = Pr
          │                                     │
          ↓                                     │
    ┌─────────────┐                            │
    │   Soil      │ ← E                         │
    │  Moisture   │                             │
    │  Store S    │                             │
    │  (C_soil)   │                             │
    └─────────────┘                             │
          ↓                                     │
         Is                                     │
      ↙     ↘                                   │
   (1-α)    α                                   │
     ↓       ↓                                  ↓
    ┌──────┐ ┌──────────────────────────────────┐
    │ Slow │ │          Fast                    │
    │ Store│ │         Store                    │
    │   R  │ │           T                      │
    │ (kR) │ │          (kT)                    │
    └──────┘ └──────────────────────────────────┘
       ↓               ↓
      QR              QT
       └───────┬───────┘
               ↓
          QR + QT
               ↓
       ┌─────────────┐
       │   Routing   │
       │   Delay     │
       │     (δ)     │
       └─────────────┘
               ↓
            HY[0]
               ↓
               Q
```

## Key Model Features

1. **Dual-pathway routing**: Separates quick flow and baseflow components
2. **Exponential soil depletion**: Realistic representation of evapotranspiration from soil
3. **Rainfall partitioning**: Allows direct runoff bypass of soil storage
4. **Routing delay**: Accounts for travel time within catchment
5. **Overflow mechanism**: Handles saturation excess when soil is full
6. **Physical interpretation**: Parameters have clear hydrological meaning

## Model Behavior

### Parameter Sensitivities

- **$C_{soil}$**: Controls soil storage capacity and baseflow recession
- **$\alpha$**: Splits infiltration between quick and slow response (higher = more quick flow)
- **$k_R$**: Controls slow flow recession time (higher = slower recession)
- **$\delta$**: Shifts hydrograph timing (higher = more delay)
- **$\beta$**: Controls direct runoff fraction (higher = flashier response)
- **$k_T$**: Controls overall routing speed (higher = slower response)

### Flow Components

The model generates two distinct flow components:

1. **Slow flow ($Q_R$)**: Represents baseflow and interflow from the soil reservoir
2. **Fast flow ($Q_T$)**: Represents quick surface runoff and rapid subsurface flow

The combination of these components allows the model to simulate both flashy and sustained flow responses.

## Comparison with GR4J

The BUCKET model shares some conceptual similarities with GR4J but differs in several ways:

| Aspect | BUCKET | GR4J |
|--------|--------|------|
| Parameters | 6 | 4 |
| Routing | Linear reservoirs | Unit hydrographs |
| Soil depletion | Exponential | Non-linear function |
| Rainfall split | Simple coefficient | Production store |
| Delay | Explicit delay parameter | Implicit in UH |
| Groundwater | Not included | Exchange parameter $x_2$ |

## References

1. Thornthwaite, C.W., & Mather, J.R. (1955). The water balance. Report. Drexel Institute of Climatology, United States.

2. Perrin, C. (2000). Vers une amélioration d'un modèle global pluie-débit [Toward an improvement of a lumped rainfall-runoff model]. PhD Thesis, Appendix 1, pp. 313-316. Retrieved from https://tel.archives-ouvertes.fr/tel-00006216

## Implementation Notes

The implementation features:
- **Time step**: Daily (indicated by the context of inputs)
- **Numerical stability**: Exponential function prevents negative soil moisture
- **Delay handling**: Ceiling function ensures integer array size
- **Flow constraint**: Maximum function prevents negative discharge
- **Simple structure**: Linear reservoirs make calibration more transparent

## Parameter Constraints and Guidance

### Physical Constraints

Some parameters have strict physical constraints:

| Parameter | Constraint | Reason |
|-----------|------------|--------|
| $\alpha$ | [0, 1] | Represents a proportion (cannot exceed 100%) |
| $\beta$ | [0, 1] | Represents a proportion (cannot exceed 100%) |
| $C_{soil}$ | > 0 | Physical storage capacity must be positive |
| $k_R$, $k_T$ | > 0 | Time constants must be positive |
| $\delta$ | ≥ 0 | Delay cannot be negative |

### Typical Parameter Values

While specific ranges depend on catchment characteristics, typical calibrated values include:

| Parameter | Typical Range | Unit | Notes |
|-----------|---------------|------|-------|
| $C_{soil}$ | 50-500 | mm | Larger for deep soils, smaller for shallow/rocky catchments |
| $\alpha$ | 0.1-0.9 | - | Higher values create flashier response |
| $k_R$ | 10-100 | days | Larger catchments typically have higher values |
| $\delta$ | 0-5 | days | Depends on catchment size and drainage density |
| $\beta$ | 0.1-0.5 | - | Higher in impervious or saturated catchments |
| $k_T$ | 1-10 | days | Should be less than $k_R$ (fast routing) |

### Calibration Guidance

- **$k_T < k_R$**: The fast routing time constant should be smaller than the slow routing constant
- **Small catchments** (< 100 km²): Lower $\delta$ (0-2 days), lower $k_R$ (10-50 days)
- **Large catchments** (> 1000 km²): Higher $\delta$ (2-5 days), higher $k_R$ (50-200 days)
- **Humid climates**: Higher $C_{soil}$ (200-1000 mm), lower $\beta$ (0.1-0.3)
- **Arid climates**: Lower $C_{soil}$ (10-200 mm), higher $\beta$ (0.3-0.7)

These ranges should be adjusted based on climate, catchment size, land use, and hydrological regime.
