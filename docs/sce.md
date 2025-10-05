# SCE-UA Algorithm Documentation

## Shuffled Complex Evolution - University of Arizona (SCE-UA)

### Overview

The SCE-UA algorithm is a global optimization method designed specifically for calibrating conceptual rainfall-runoff models. Developed by Duan, Sorooshian, and Gupta (1992), it combines the strengths of controlled random search, competitive evolution, complex shuffling, and the downhill simplex method.

### Mathematical Foundation

#### Problem Definition

The algorithm solves the minimization problem:

$$\min_{\mathbf{x}} f(\mathbf{x})$$

subject to:

$$\mathbf{x}_L \leq \mathbf{x} \leq \mathbf{x}_U$$

where:
- $\mathbf{x} \in \mathbb{R}^n$ is the parameter vector with $n$ parameters
- $f(\mathbf{x})$ is the objective function to minimize (e.g., difference between observed and simulated streamflow)
- $\mathbf{x}_L$ and $\mathbf{x}_U$ are the lower and upper bounds for parameters

### Algorithm Parameters

#### Population Structure

The algorithm organizes the search using several key hyperparameters:

- **$n_{opt}$**: Number of parameters to optimize
- **$n_{gs}$**: Number of complexes (sub-populations), typically set to 25
- **$n_{pg}$**: Number of points in each complex, calculated as:
  $$n_{pg} = 2n_{opt} + 1$$
- **$n_{ps}$**: Number of points in a simplex:
  $$n_{ps} = n_{opt} + 1$$
- **$n_{pt}$**: Total population size:
  $$n_{pt} = n_{gs} \times n_{pg}$$

#### Evolution Parameters

- **$n_{spl}$**: Number of evolution steps before shuffling:
  $$n_{spl} = 2n_{opt} + 1$$
- **$\alpha = 1.0$**: Reflection coefficient for simplex operations
- **$\beta = 0.5$**: Contraction coefficient for simplex operations

#### Convergence Criteria

- **$max_n$**: Maximum number of function evaluations (default: 5000)
- **$k_{stop}$**: Number of shuffling loops to check convergence (default: 10)
- **$p_{cento}$**: Percentage change threshold for convergence (default: 0.001)
- **$p_{eps}$**: Geometric range threshold (default: 0.1)

### Algorithm Steps

#### Step 1: Initial Population Generation

Generate initial population of $n_{pt}$ points randomly within bounds:

$$\mathbf{x}_i = \mathbf{x}_L + \mathbf{r} \odot (\mathbf{x}_U - \mathbf{x}_L)$$

where $\mathbf{r} \in [0,1]^n$ is a random vector and $\odot$ denotes element-wise multiplication.

#### Step 2: Complex Partitioning

Sort the population by objective function value and partition into $n_{gs}$ complexes:

$$\text{Complex}_k = \{\mathbf{x}_{k+j \cdot n_{gs}} : j = 0, 1, ..., n_{pg}-1\}$$

This ensures each complex contains points distributed across the fitness spectrum.

#### Step 3: Complex Evolution (CCE)

For each complex, repeat $n_{spl}$ times:

##### 3.1 Simplex Selection
Select $n_{ps}$ points from the complex using a triangular probability distribution:

$$P(rank = j) \propto (n_{pg} - j + 1)$$

##### 3.2 Simplex Operations

Given simplex points $\mathbf{s}_1, ..., \mathbf{s}_{n_{ps}}$ sorted by fitness:

1. **Calculate centroid** (excluding worst point):
   $$\mathbf{c} = \frac{1}{n_{ps}-1} \sum_{i=1}^{n_{ps}-1} \mathbf{s}_i$$

2. **Reflection**: Generate new point by reflecting worst point $\mathbf{s}_{worst}$:
   $$\mathbf{s}_{new} = \mathbf{c} + \alpha(\mathbf{c} - \mathbf{s}_{worst})$$

3. **Boundary check**: If $\mathbf{s}_{new}$ violates bounds, generate random point

4. **Contraction**: If reflection fails ($f(\mathbf{s}_{new}) > f(\mathbf{s}_{worst})$):
   $$\mathbf{s}_{new} = \mathbf{s}_{worst} + \beta(\mathbf{c} - \mathbf{s}_{worst})$$

5. **Random generation**: If contraction fails, generate random point within bounds

#### Step 4: Complex Shuffling

After evolution, merge all complexes and re-sort the entire population:

$$\text{Population} = \bigcup_{k=1}^{n_{gs}} \text{Complex}_k$$

#### Step 5: Convergence Check

##### Normalized Geometric Range

Calculate the parameter space contraction:

$$gnrng = \exp\left(\frac{1}{n_{opt}} \sum_{i=1}^{n_{opt}} \ln\left(\frac{\max_j x_{j,i} - \min_j x_{j,i}}{x_{U,i} - x_{L,i}}\right)\right)$$

##### Criterion Change

After $k_{stop}$ iterations, calculate relative change:

$$\text{change} = \frac{|f_{best}^{(t)} - f_{best}^{(t-k_{stop})}|}{\text{mean}(|f_{best}^{(t-k_{stop}:t)}|)} \times 100$$

##### Termination

Stop if any condition is met:
- Function evaluations exceed $max_n$
- $gnrng < p_{eps}$ (population has converged)
- $\text{change} < p_{cento}$ (objective function has stabilized)

### Key Advantages

1. **Global Search**: Multiple complexes explore different regions of parameter space
2. **Local Refinement**: Simplex operations provide efficient local search
3. **Information Sharing**: Shuffling allows complexes to share information
4. **Robustness**: Combination of deterministic and stochastic search strategies

### Implementation Notes

#### Objective Function Transformation

In the HOLMES implementation, the objective function transforms the calibration criterion to a minimization problem:

$$f(\mathbf{x}) = |C(\mathbf{x}) - C_{optimal}|$$

where $C$ is the chosen criterion (e.g., Nash-Sutcliffe efficiency) and $C_{optimal}$ is its theoretical optimum.

#### Computational Complexity

- **Per iteration**: $O(n_{gs} \times n_{spl} \times n_{opt})$ function evaluations
- **Memory**: $O(n_{pt} \times n_{opt})$ for storing population

### Example Parameter Settings

For a typical hydrological model with 4 parameters:
- $n_{opt} = 4$ (e.g., GR4J parameters)
- $n_{gs} = 25$ complexes
- $n_{pg} = 9$ points per complex
- $n_{ps} = 5$ points per simplex
- $n_{pt} = 225$ total population size
- $n_{spl} = 9$ evolution steps

### References

Duan, Q., Sorooshian, S., & Gupta, V. K. (1992). Effective and efficient global optimization for conceptual rainfall-runoff models. *Water Resources Research*, 28(4), 1015-1031.