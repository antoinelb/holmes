# GR4J Hydrological Model Documentation

## Overview

GR4J (modèle du Génie Rural à 4 paramètres Journalier) is a daily lumped rainfall-runoff model with four parameters. It was developed by Perrin et al. (2003) and is widely used for hydrological modeling due to its simplicity and efficiency. The model simulates the transformation of precipitation into runoff through two main functions: production and routing.

## Model Parameters

The GR4J model uses four calibrated parameters:

| Parameter | Symbol | Unit | Range | Description |
|-----------|--------|------|-------|-------------|
| **X1** | $x_1$ | mm | [10, 1500] | Maximum capacity of the production store |
| **X2** | $x_2$ | mm/day | [-5, 3] | Groundwater exchange coefficient |
| **X3** | $x_3$ | mm | [10, 400] | Maximum capacity of the routing store |
| **X4** | $x_4$ | days | [0.8, 10] | Time base of unit hydrograph |

## State Variables

The model maintains two state variables:
- $S$ : Level of the production store (mm)
- $R$ : Level of the routing store (mm)

## Mathematical Formulation

### 1. Production Function

The production function determines the partition of precipitation and evapotranspiration, managing the soil moisture store.

#### 1.1 Net Rainfall and Evapotranspiration

First, we calculate net rainfall ($P_n$) and net evapotranspiration ($E_n$):

**Case 1: When $P > E$ (wet conditions)**
$$P_n = P - E$$
$$E_n = 0$$

**Case 2: When $P < E$ (dry conditions)**
$$P_n = 0$$
$$E_n = E - P$$

**Case 3: When $P = E$**
$$P_n = 0$$
$$E_n = 0$$

#### 1.2 Production Store Update

The production store fills ($P_s$) or empties ($E_s$) according to:

**For net rainfall ($P_n > 0$):**
$$P_s = \frac{x_1 \cdot (1 - (\frac{S}{x_1})^2) \cdot \tanh(\frac{P_n}{x_1})}{1 + \frac{S}{x_1} \cdot \tanh(\frac{P_n}{x_1})}$$

$$E_s = 0$$

**For net evapotranspiration ($E_n > 0$):**
$$E_s = \frac{S \cdot (2 - \frac{S}{x_1}) \cdot \tanh(\frac{E_n}{x_1})}{1 + (1 - \frac{S}{x_1}) \cdot \tanh(\frac{E_n}{x_1})}$$

$$P_s = 0$$

The production store is then updated:
$$S_{t+1} = S_t - E_s + P_s$$

#### 1.3 Percolation

A percolation term ($Perc$) represents the water that leaves the production store:

$$Perc = S \cdot \left[1 - \left(1 + \left(\frac{4}{21} \cdot \frac{S}{x_1}\right)^4\right)^{-\frac{1}{4}}\right]$$

Note: Percolation only occurs when $\frac{x_1}{S} > 10^{-3}$

The production store is updated again:
$$S_{t+1} = S_t - Perc$$

#### 1.4 Total Routing Input

The total water available for routing ($P_r$) is:
$$P_r = P_n - P_s + Perc$$

### 2. Routing Function

The routing function splits the water into two flow paths using unit hydrographs.

#### 2.1 Flow Partitioning

The routing input is divided into two components:
- **90%** goes through unit hydrograph UH1 (slow routing)
- **10%** goes through unit hydrograph UH2 (fast routing)

$$Q_9 = 0.9 \cdot P_r$$
$$Q_1 = 0.1 \cdot P_r$$

#### 2.2 Unit Hydrographs

The model uses two unit hydrographs based on the S-curves:

**S-curve 1 (SH1):**

$$
SH1(t) = \begin{cases}
0 & \text{if } t = 0 \\
\left(\frac{t}{x_4}\right)^{1.25} & \text{if } 0 < t < x_4 \\
1 & \text{if } t \geq x_4
\end{cases}
$$

**S-curve 2 (SH2):**

$$
SH2(t) = \begin{cases}
0 & \text{if } t = 0 \\
\frac{1}{2} \cdot \left(\frac{t}{x_4}\right)^{1.25} & \text{if } 0 < t < x_4 \\
1 - \frac{1}{2} \cdot \left(2 - \frac{t}{x_4}\right)^{1.25} & \text{if } x_4 \leq t < 2x_4 \\
1 & \text{if } t \geq 2x_4
\end{cases}
$$

**Unit hydrographs:**

$$UH1(j) = SH1(j) - SH1(j-1)$$

$$UH2(j) = SH2(j) - SH2(j-1)$$

#### 2.3 Groundwater Exchange

A groundwater exchange term ($F$) allows water exchange with external catchments or deep aquifers:

$$F = x_2 \cdot \left(\frac{R}{x_3}\right)^{3.5}$$

Where:
- $F > 0$: water import from groundwater
- $F < 0$: water export to groundwater

#### 2.4 Routing Store and Flow Components

**Routing store update:**
$$R_{t+1} = R_t + Q_9 + F$$

**Routed flow from the routing store:**
$$Q_r = R \cdot \left[1 - \left(1 + \left(\frac{R}{x_3}\right)^4\right)^{-\frac{1}{4}}\right]$$

The routing store is then updated:
$$R_{t+1} = R_t - Q_r$$

**Direct flow:**
$$Q_d = \max(0, Q_1 + F)$$

#### 2.5 Total Streamflow

The total streamflow at time $t$ is:
$$Q(t) = Q_r + Q_d$$

## Initial Conditions

The model typically initializes the stores at half their maximum capacity:
- Production store: $S_0 = \frac{x_1}{2}$
- Routing store: $R_0 = \frac{x_3}{2}$

## Model Conceptual Diagram

```
    P ────┐
          ↓
    ┌─────────────┐
    │  Interception│ ← E
    └─────────────┘
          ↓
         Pn, En
          ↓
    ┌─────────────┐
    │ Production  │
    │   Store S   │ ← Es, Ps
    │   (x1)      │
    └─────────────┘
          ↓
        Perc
          ↓
         Pr
      ↙  0.9  0.1 ↘
    UH1         UH2
     ↓           ↓
    Q9          Q1
     ↓           ↓
    ┌─────────────┐
    │  Routing    │ ← F (x2)
    │  Store R    │
    │   (x3)      │
    └─────────────┘
          ↓
         Qr        Qd
          ↘      ↙
            Q
```

## Key Model Features

1. **Parsimony**: Only 4 parameters make the model easy to calibrate
2. **Physical Interpretation**: Parameters have hydrological meaning
3. **Non-linearity**: The model includes non-linear relationships that capture complex hydrological behaviors
4. **Flexibility**: The groundwater exchange parameter allows the model to handle gaining and losing catchments

## References

Perrin, C., Michel, C., & Andréassian, V. (2003). Improvement of a parsimonious model for streamflow simulation. Journal of Hydrology, 279(1-4), 275-289.

## Implementation Notes

The implementation uses:
- **Numerical optimization**: The `numba` JIT compiler is used for computational efficiency
- **Time step**: Daily (indicated by `TimeStep = "d"`)
- **Numerical stability**: Small thresholds (e.g., $10^{-3}$) are used to prevent division by zero