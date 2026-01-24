# Calibration Algorithms

## SCE-UA: Shuffled Complex Evolution

### Overview

Model calibration is the process of finding parameter values that make model outputs match observations as closely as possible. In rainfall-runoff modeling, this means adjusting parameters like soil capacity, recession rates, and routing times until simulated streamflow resembles observed streamflow.

This is fundamentally an optimization problem: we seek parameter values that minimize (or maximize) an objective function measuring the discrepancy between simulations and observations. The challenge is that hydrological models have complex response surfaces with multiple local optima—simple gradient-based methods often get trapped in suboptimal solutions.

SCE-UA (Shuffled Complex Evolution - University of Arizona) is a global optimization algorithm specifically designed for hydrological model calibration. Developed by Duan, Sorooshian, and Gupta in the early 1990s, it has become the de facto standard for automatic calibration of conceptual rainfall-runoff models. SCE-UA combines elements from multiple optimization traditions to efficiently explore the parameter space and reliably find the global optimum.

### Key Concepts

- **Objective function**: A mathematical measure of how well the model fits observations. Common choices include Nash-Sutcliffe Efficiency (NSE), Kling-Gupta Efficiency (KGE), or Root Mean Square Error (RMSE). The calibration algorithm tries to optimize this function.

- **Parameter space**: The multi-dimensional space defined by parameter bounds. For a 4-parameter model like GR4J, this is a 4-dimensional hypercube.

- **Global vs. local optimization**: Local methods find the nearest minimum; global methods search the entire space. Hydrological models need global methods because their response surfaces have many local minima.

- **Population-based search**: Rather than tracking a single solution, SCE-UA maintains a population of candidate solutions that collectively explore the parameter space.

- **Complex**: A subset of the population that evolves semi-independently. The "shuffled" aspect comes from periodically mixing complexes to share information.

### How SCE-UA Works

SCE-UA operates through an iterative process of evolution and shuffling:

**Step 1: Initialization**. Generate a random population of parameter sets spanning the feasible parameter space. Evaluate the objective function for each.

**Step 2: Partition into complexes**. Sort the population by objective function value and distribute points among complexes using a round-robin scheme. Each complex contains a mix of good and poor solutions.

**Step 3: Evolve each complex**. Within each complex, repeatedly select a subset (simplex) of points and improve them using a modified Nelder-Mead procedure:
- Select points favoring better solutions (using a triangular distribution)
- Compute a reflection point that moves away from the worst solution
- If reflection improves the solution, keep it
- Otherwise, try contraction toward the centroid
- If all else fails, generate a random point

**Step 4: Shuffle**. Recombine all complexes into a single population, sort by objective function, and redistribute into new complexes. This allows information to spread between complexes.

**Step 5: Check convergence**. Stop if:
- Maximum function evaluations reached
- Parameters have converged (all complexes found similar solutions)
- Objective function is no longer improving

**Step 6: Repeat** from Step 2 until convergence.

### Algorithm Parameters

SCE-UA has several algorithm parameters that control its behavior:

| Parameter | Description | Typical Value | Effect |
|-----------|-------------|---------------|--------|
| `n_complexes` | Number of complexes | 2–5 | More complexes = more exploration, slower convergence |
| `max_evaluations` | Maximum function evaluations | 5000–50000 | Computational budget |
| `geometric_range_threshold` | Convergence criterion | 0.001 | Stop when parameters converge to this precision |
| `p_convergence_threshold` | Objective improvement threshold | 0.1% | Stop when improvement falls below this |
| `k_stop` | Number of iterations for improvement check | 10 | Window for assessing improvement |

**Choosing the number of complexes:**

- For simple problems (4 parameters): 2–3 complexes
- For complex problems (7+ parameters): 4–5 complexes
- More complexes reduce risk of premature convergence but increase computation

### Mathematical Details

#### Population Structure

For $n$ model parameters, SCE-UA uses:

- Points per complex: $m = 2n + 1$
- Simplex size: $n + 1$
- Evolution steps per complex: $m$
- Total population: $p = m \times n_{complexes}$

#### Simplex Selection

Points within a complex are selected for the simplex using a triangular probability distribution that favors better solutions:

$$L_{pos} = \left\lfloor (m + 0.5) - \sqrt{(m + 0.5)^2 - m(m+1) \cdot U} \right\rfloor$$

where $U$ is a uniform random number in $[0, 1]$. This gives higher probability to points with better objective values (lower indices in the sorted complex).

#### Simplex Evolution

The evolution step uses reflection and contraction coefficients:

- Reflection coefficient: $\alpha = 1.0$
- Contraction coefficient: $\beta = 0.5$

**Reflection:**

$$\mathbf{x}_{reflect} = \mathbf{c} + \alpha(\mathbf{c} - \mathbf{x}_{worst})$$

where $\mathbf{c}$ is the centroid of all simplex points except the worst.

**Contraction:**

$$\mathbf{x}_{contract} = \mathbf{x}_{worst} + \beta(\mathbf{c} - \mathbf{x}_{worst})$$

If both reflection and contraction fail to improve upon the worst point, a random point within parameter bounds is generated.

#### Convergence Criteria

**Geometric normalized range (GNRNG):**

$$GNRNG = \exp\left(\frac{1}{n}\sum_{i=1}^{n} \ln\left(\frac{range_i}{bounds_i}\right)\right)$$

where $range_i$ is the range of parameter $i$ across the current population and $bounds_i$ is the feasible range. Convergence when $GNRNG < threshold$.

**Percentage change criterion:**

$$\Delta = \frac{|f_t - f_{t-k}|}{\bar{f}} \times 100$$

where $f_t$ is the best objective value at iteration $t$ and $\bar{f}$ is the mean of recent best values. Convergence when $\Delta < threshold$.

### Practical Considerations

#### Before Calibration

1. **Define parameter bounds carefully**. Bounds should be physically realistic but wide enough to allow exploration. Too narrow bounds may exclude the true optimum; too wide bounds waste computational effort.

2. **Choose an appropriate objective function**. NSE emphasizes peak flows; KGE provides a more balanced assessment. Consider what aspects of the hydrograph matter most for your application.

3. **Use a warm-up period**. The first year of simulation is often affected by initial conditions. Exclude it from the objective function calculation.

4. **Reserve data for validation**. Don't use all your data for calibration. Keep some years aside to test whether the calibrated model generalizes.

#### During Calibration

1. **Monitor progress**. Watch for:
   - Steady improvement in objective function
   - Parameters converging toward similar values
   - Adequate exploration of parameter space

2. **Be patient**. Global optimization takes time. Premature stopping may miss better solutions.

3. **Multiple runs**. Run calibration several times with different random seeds. If results differ substantially, the problem may have multiple optima.

#### Interpreting Results

1. **Check parameter values**. Parameters at or near bounds may indicate:
   - Bounds are too restrictive
   - Model structure is inappropriate
   - Data quality issues

2. **Examine residuals**. Plot simulated vs. observed flows. Systematic patterns (e.g., always underpredicting peaks) suggest model structural limitations.

3. **Compare metrics**. Calculate multiple performance metrics (RMSE, NSE, KGE) even if you only optimized one. This reveals trade-offs.

4. **Validate on independent data**. Apply the calibrated model to data not used for calibration. Performance degradation indicates overfitting.

### Common Issues and Solutions

| Issue | Possible Causes | Solutions |
|-------|-----------------|-----------|
| Calibration never converges | Bounds too wide, insufficient evaluations | Narrow bounds, increase `max_evaluations` |
| Different runs give different results | Multiple local optima | Increase `n_complexes`, run multiple times |
| Parameters hit bounds | Bounds too restrictive, data issues | Widen bounds, check data quality |
| Poor validation performance | Overfitting, non-stationary catchment | Use shorter calibration period, add regularization |
| Very slow progress | Too many parameters, expensive model | Reduce complexity, use efficient implementation |

### Transformation Options

HOLMES allows applying transformations to streamflow before computing the objective function:

| Transformation | Formula | Effect |
|----------------|---------|--------|
| None | $Q' = Q$ | Equal weight to all flows |
| Logarithmic | $Q' = \ln(Q)$ | Emphasizes low flows |
| Square root | $Q' = \sqrt{Q}$ | Moderate emphasis on low flows |

Log transformation is useful when you want the model to capture recession behavior accurately, not just peak flows.

### References

Duan, Q., Sorooshian, S., & Gupta, V. (1992). Effective and efficient global optimization for conceptual rainfall-runoff models. *Water Resources Research*, 28(4), 1015-1031. [https://doi.org/10.1029/91WR02985](https://doi.org/10.1029/91WR02985)

The original SCE-UA paper, presenting the algorithm and demonstrating its effectiveness on the Sacramento Soil Moisture Accounting model.

Duan, Q., Sorooshian, S., & Gupta, V. K. (1994). Optimal use of the SCE-UA global optimization method for calibrating watershed models. *Journal of Hydrology*, 158(3-4), 265-284. [https://doi.org/10.1016/0022-1694(94)90057-4](https://doi.org/10.1016/0022-1694(94)90057-4)

A follow-up paper providing practical guidance on algorithm settings and convergence criteria.

Nelder, J. A., & Mead, R. (1965). A simplex method for function minimization. *The Computer Journal*, 7(4), 308-313.

The original simplex algorithm that forms the basis for the complex evolution step in SCE-UA.
