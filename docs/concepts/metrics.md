# Performance Metrics

## Overview

After calibrating a hydrological model, we need to assess how well it performs. Performance metrics quantify the agreement between simulated and observed streamflow, providing objective measures of model quality.

No single metric captures all aspects of model performance. Peak flows, low flows, timing, volume, and variability each tell part of the story. Using multiple metrics provides a more complete picture of model strengths and weaknesses.

HOLMES implements three widely-used metrics: RMSE (Root Mean Square Error), NSE (Nash-Sutcliffe Efficiency), and KGE (Kling-Gupta Efficiency). Each emphasizes different aspects of performance and is appropriate for different applications.

## Notation

Throughout this page:

- $O_i$ = observed streamflow at time step $i$
- $S_i$ = simulated streamflow at time step $i$
- $\bar{O}$ = mean of observed streamflow
- $\bar{S}$ = mean of simulated streamflow
- $\sigma_O$ = standard deviation of observations
- $\sigma_S$ = standard deviation of simulations
- $n$ = number of time steps

## RMSE: Root Mean Square Error

### Definition

$$RMSE = \sqrt{\frac{1}{n}\sum_{i=1}^{n}(O_i - S_i)^2}$$

### Interpretation

RMSE measures the average magnitude of errors between simulated and observed values. It has the same units as the data (e.g., mm/day or m³/s), making it directly interpretable as "typical error size."

**Key properties:**

- **Range**: $[0, \infty)$
- **Perfect score**: 0 (no errors)
- **Units**: Same as input data
- **Squaring**: Large errors contribute disproportionately (a 10 mm/day error counts 100 times more than a 1 mm/day error)

### When to Use RMSE

- When you need error magnitude in physical units
- When large errors are particularly problematic
- For comparing models applied to the same catchment (not for cross-catchment comparison, as RMSE scales with flow magnitude)

### Limitations

- **Scale-dependent**: A large catchment with high flows will naturally have higher RMSE than a small catchment, even if both models perform equally well relatively
- **Sensitive to outliers**: A few large errors can dominate the metric
- **No skill reference**: RMSE doesn't tell you whether the model is better than a simple baseline

### Example Interpretation

If RMSE = 2.5 mm/day for a catchment with mean flow of 5 mm/day, the typical error is about 50% of mean flow—indicating moderate performance. For a catchment with mean flow of 25 mm/day, the same RMSE would indicate excellent performance (10% error).

## NSE: Nash-Sutcliffe Efficiency

### Definition

$$NSE = 1 - \frac{\sum_{i=1}^{n}(O_i - S_i)^2}{\sum_{i=1}^{n}(O_i - \bar{O})^2}$$

### Interpretation

NSE compares model errors to the variance of observations. It answers: "Is the model better than simply using the observed mean as a predictor?"

**Key properties:**

- **Range**: $(-\infty, 1]$
- **Perfect score**: 1 (simulations exactly match observations)
- **Benchmark score**: 0 (model is as good as using the mean)
- **Negative values**: Model is worse than the mean
- **Dimensionless**: Can compare across catchments

### Decomposition

NSE can be understood as:

$$NSE = 1 - \frac{MSE}{Var(O)}$$

where MSE is the mean squared error and Var(O) is the variance of observations. The model must explain more variance than it introduces as error to achieve positive NSE.

### Rating Guidelines

| NSE | Interpretation |
|-----|----------------|
| > 0.75 | Very good |
| 0.65 – 0.75 | Good |
| 0.50 – 0.65 | Satisfactory |
| 0.40 – 0.50 | Acceptable for some purposes |
| < 0.40 | Unsatisfactory |

These thresholds are guidelines, not strict rules. Acceptable performance depends on the application.

### When to Use NSE

- For general performance assessment
- When comparing models across different catchments
- For research publications (NSE is the most commonly reported metric)

### Limitations

- **Emphasis on high flows**: Because errors are squared, NSE is dominated by performance during peak flows. A model that captures peaks well but misses low flows may still have high NSE.
- **Sensitive to timing**: A simulation that is correct in magnitude but shifted in time will have poor NSE.
- **Mean benchmark**: Using the mean as a benchmark may be too easy in catchments with high autocorrelation.

## KGE: Kling-Gupta Efficiency

### Definition

$$KGE = 1 - \sqrt{(r-1)^2 + (\alpha-1)^2 + (\beta-1)^2}$$

where:

- $r$ = Pearson correlation coefficient between $O$ and $S$
- $\alpha = \frac{\sigma_S}{\sigma_O}$ = ratio of standard deviations (variability ratio)
- $\beta = \frac{\bar{S}}{\bar{O}}$ = ratio of means (bias ratio)

### Component Interpretation

KGE decomposes performance into three independent aspects:

| Component | Symbol | Optimal Value | Meaning |
|-----------|--------|---------------|---------|
| Correlation | $r$ | 1 | Timing and shape |
| Variability ratio | $\alpha$ | 1 | Amplitude of variations |
| Bias ratio | $\beta$ | 1 | Mean water balance |

**Correlation ($r$)**: Measures how well the timing and pattern of simulated flows match observations. High correlation means peaks and troughs occur at the right times, even if magnitudes differ.

**Variability ratio ($\alpha$)**: Compares the "spread" of simulations to observations. $\alpha > 1$ means simulations are too variable; $\alpha < 1$ means simulations are too damped.

**Bias ratio ($\beta$)**: Compares mean flows. $\beta > 1$ means the model overestimates on average; $\beta < 1$ means underestimation.

### Expanded Form

The components are calculated as:

$$r = \frac{\sum_{i=1}^{n}(O_i - \bar{O})(S_i - \bar{S})}{\sqrt{\sum_{i=1}^{n}(O_i - \bar{O})^2} \cdot \sqrt{\sum_{i=1}^{n}(S_i - \bar{S})^2}}$$

$$\alpha = \frac{\sigma_S}{\sigma_O} = \frac{\sqrt{\frac{1}{n}\sum_{i=1}^{n}(S_i - \bar{S})^2}}{\sqrt{\frac{1}{n}\sum_{i=1}^{n}(O_i - \bar{O})^2}}$$

$$\beta = \frac{\bar{S}}{\bar{O}}$$

### Key Properties

- **Range**: $(-\infty, 1]$
- **Perfect score**: 1 (all components equal 1)
- **Benchmark**: KGE = -0.41 corresponds to using the observed mean (like NSE = 0)
- **Dimensionless**: Can compare across catchments
- **Diagnostic**: Components reveal which aspects need improvement

### Rating Guidelines

| KGE | Interpretation |
|-----|----------------|
| > 0.75 | Very good |
| 0.50 – 0.75 | Good |
| 0.00 – 0.50 | Acceptable |
| < 0.00 | Poor |

### When to Use KGE

- When you want diagnostic information about model errors
- When water balance (bias) matters for your application
- When you want a more balanced assessment than NSE provides
- For operational hydrology where total volumes matter

### Advantages Over NSE

1. **Balanced assessment**: NSE can be high even with significant bias if variability is captured. KGE explicitly penalizes bias.

2. **Diagnostic value**: The components tell you what to fix. Poor $r$? Work on timing. Poor $\beta$? Adjust the water balance.

3. **More intuitive benchmark**: NSE = 0 corresponds to using the mean, but KGE = 0 is a more meaningful threshold in practice.

## Comparison of Metrics

| Aspect | RMSE | NSE | KGE |
|--------|------|-----|-----|
| **Units** | Same as data | Dimensionless | Dimensionless |
| **Range** | $[0, \infty)$ | $(-\infty, 1]$ | $(-\infty, 1]$ |
| **Perfect** | 0 | 1 | 1 |
| **Cross-catchment comparison** | No | Yes | Yes |
| **Emphasis** | All errors equally (squared) | High flows | Balanced |
| **Diagnostic** | No | Limited | Yes (3 components) |
| **Bias sensitivity** | Implicit | Low | High |
| **Most common use** | Error magnitude | Research | Operational |

## Choosing a Metric

The choice of metric should align with your modeling objectives:

**For flood forecasting**: NSE or RMSE, as peak flow accuracy matters most.

**For water resources planning**: KGE, because water balance (total volumes) is critical.

**For low flow assessment**: Consider transforming flows (log or square root) before computing metrics, or use specific low-flow metrics.

**For research and publication**: Report multiple metrics. NSE for comparability with literature; KGE for diagnostic insight; RMSE for physical interpretation.

**Best practice**: Always report at least two metrics. High NSE with poor KGE components (e.g., biased mean) reveals important model limitations.

## Practical Tips

1. **Examine time series plots** in addition to metrics. A metric is a summary; the plot shows details.

2. **Calculate metrics for subperiods**: Calibration vs. validation, wet vs. dry years, different seasons. Performance may vary.

3. **Consider flow transformation**: Log transformation emphasizes low flows; square root provides intermediate emphasis.

4. **Watch for suspect values**: A single missing observation coded as -999 can ruin all metrics. Check data quality first.

5. **Report uncertainty**: If you run multiple calibrations, report the range of metrics, not just the best run.

## References

Nash, J. E., & Sutcliffe, J. V. (1970). River flow forecasting through conceptual models part I—A discussion of principles. *Journal of Hydrology*, 10(3), 282-290. [https://doi.org/10.1016/0022-1694(70)90255-6](https://doi.org/10.1016/0022-1694(70)90255-6)

The seminal paper introducing NSE, one of the most cited papers in hydrology. Establishes the concept of comparing model errors to observation variance.

Gupta, H. V., Kling, H., Yilmaz, K. K., & Martinez, G. F. (2009). Decomposition of the mean squared error and NSE performance criteria: Implications for improving hydrological modelling. *Journal of Hydrology*, 377(1-2), 80-91. [https://doi.org/10.1016/j.jhydrol.2009.08.003](https://doi.org/10.1016/j.jhydrol.2009.08.003)

Introduces KGE and demonstrates its advantages over NSE. Shows how NSE can mask important model deficiencies.

Moriasi, D. N., Arnold, J. G., Van Liew, M. W., Bingner, R. L., Harmel, R. D., & Veith, T. L. (2007). Model evaluation guidelines for systematic quantification of accuracy in watershed simulations. *Transactions of the ASABE*, 50(3), 885-900.

Provides widely-cited guidelines for acceptable performance levels (NSE > 0.5 for satisfactory performance).
