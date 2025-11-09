# Rust vs Numba: Performance Decision Guide

**Version**: 1.0
**Last Updated**: 2025-11-09
**Audience**: HOLMES developers implementing hydrological models

## Purpose

This guide helps you decide whether to implement a hydrological model using:
- **Numba JIT** (current approach for GR4J, CemaNeige, etc.)
- **Rust with PyO3** (future option for performance-critical models)

The goal is to balance **Performance First** with **Code Simplicity** from the project constitution.

---

## TL;DR - Quick Decision Tree

```
Is the model already working in Numba?
├─ Yes → Keep it unless you have a specific performance problem
└─ No → Start with Numba

Is Numba fast enough (< 1ms per run for 10 years daily data)?
├─ Yes → Keep Numba, it's simpler
└─ No → Consider Rust

Do you need features Numba doesn't support well?
├─ Complex data structures (graphs, trees, hashmaps)
├─ Advanced parallelism beyond simple loops
├─ Integration with external C/C++ libraries
├─ Distributable standalone binaries
└─ Yes to any → Consider Rust
    No to all → Stay with Numba

Is the model extremely performance-critical?
├─ Used in real-time applications
├─ Run millions of times in calibration
├─ Needs absolute maximum speed
└─ Yes → Consider Rust
    No → Numba is sufficient
```

**Default choice: Numba** (until you have a compelling reason to use Rust)

---

## Comparison Matrix

| Aspect | Numba JIT | Rust + PyO3 |
|--------|-----------|-------------|
| **Development Speed** | ⚡ Very fast - Python syntax | 🐢 Slower - new language, toolchain |
| **Runtime Performance** | 🚀 Excellent - near C speed | 🚀🚀 Excellent - native code |
| **Cold-start Time** | ⚠️ 1-3 seconds (cache helps) | ✅ Instant - pre-compiled |
| **Debugging** | ✅ Standard Python tools | ⚠️ More complex - gdb/lldb |
| **Maintenance** | ✅ Familiar to Python devs | ⚠️ Requires Rust knowledge |
| **Educational Value** | ✅ Students understand Python | ⚠️ Rust learning curve |
| **Data Science Integration** | ✅ Seamless NumPy/Polars | ✅ Good via PyO3 |
| **Deployment** | ✅ pip install | ⚠️ Compilation needed |
| **Type Safety** | ⚠️ Runtime inference | ✅ Compile-time guarantees |
| **Memory Control** | ⚠️ Python GC overhead | ✅ Manual control |
| **Parallelism** | ✅ Good for simple cases | ✅ Excellent - Rayon |
| **Complexity** | 🟢 Low | 🟡 Medium-High |

---

## When to Choose Numba

### ✅ Numba is the Right Choice When:

1. **Model is straightforward**
   - Iterative calculations over arrays
   - Pure numerical operations (no complex data structures)
   - Fits naturally in vectorized NumPy style

2. **Development speed matters**
   - Rapid prototyping and iteration
   - Educational software (students can read the code)
   - Frequent model modifications

3. **Performance is "good enough"**
   - Sub-millisecond execution for typical datasets
   - Cold-start time acceptable (< 5 seconds, mitigated by `cache=True`)
   - Throughput meets calibration needs

4. **Team has Python expertise**
   - Contributors know Python
   - Educational context requires accessible code
   - Maintenance will be by Python developers

5. **Examples in HOLMES v3**
   - GR4J rainfall-runoff model (`src/hydro/gr4j.py`)
   - CemaNeige snow model (`src/hydro/snow.py`)
   - Oudin PET calculation (`src/hydro/oudin.py`)
   - These achieve **excellent performance** with Numba

### Numba Best Practices

```python
# ✅ Good Numba usage
@numba.jit(nopython=True, cache=True)
def run_model(
    precipitation: np.ndarray,
    evapotranspiration: np.ndarray,
    *,
    x1: int,
    x2: float,
    x3: int,
    x4: float,
) -> np.ndarray:
    """
    Pure numerical operations, clear types, vectorized where possible.
    """
    flows = np.zeros(precipitation.shape[0])
    store_prod = x1 / 2.0
    store_rout = x3 / 2.0

    for t in range(precipitation.shape[0]):
        # Update stores and flows
        # ... calculations ...
        flows[t] = flow

    return flows
```

**Key points**:
- `nopython=True` ensures no Python object overhead
- `cache=True` eliminates cold-start on subsequent runs
- Type annotations help compilation
- Simple data structures (NumPy arrays)
- Pure functions (no side effects)

---

## When to Choose Rust

### ✅ Rust is the Right Choice When:

1. **Cold-start time is unacceptable**
   - Interactive applications requiring instant response
   - CLI tools that run once and exit
   - Serverless/lambda deployments with cold starts
   - **Note**: `cache=True` in Numba largely solves this for HOLMES

2. **Need absolute maximum performance**
   - Model runs billions of times
   - Real-time constraints (< 100μs per evaluation)
   - Embarrassingly parallel workloads (Rayon > Numba parallelism)
   - GPU acceleration via wgpu/CUDA

3. **Complex algorithms or data structures**
   - Graph-based models (river networks)
   - Spatial data structures (quadtrees, R-trees)
   - Advanced parallelism patterns
   - State machines or complex control flow

4. **Want compile-time guarantees**
   - Type safety prevents entire classes of bugs
   - Borrow checker prevents data races
   - Critical infrastructure code

5. **Distribution requirements**
   - Standalone binaries without Python runtime
   - Integration with other languages (C/C++/Java)
   - Mobile or embedded systems

### Rust Best Practices (with PyO3)

```rust
// Example: Rust implementation of GR4J (hypothetical)
use pyo3::prelude::*;
use numpy::{PyArray1, PyReadonlyArray1};

#[pyfunction]
fn run_model(
    precipitation: PyReadonlyArray1<f64>,
    evapotranspiration: PyReadonlyArray1<f64>,
    x1: f64,
    x2: f64,
    x3: f64,
    x4: f64,
) -> PyResult<Py<PyArray1<f64>>> {
    let precip = precipitation.as_slice()?;
    let pet = evapotranspiration.as_slice()?;
    let n = precip.len();

    let mut flows = vec![0.0; n];
    let mut store_prod = x1 / 2.0;
    let mut store_rout = x3 / 2.0;

    for t in 0..n {
        // Update stores and flows
        // ... calculations ...
        flows[t] = flow;
    }

    Python::with_gil(|py| {
        Ok(PyArray1::from_vec(py, flows).to_owned())
    })
}

#[pymodule]
fn holmes_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run_model, m)?)?;
    Ok(())
}
```

**Key points**:
- PyO3 provides seamless Python integration
- Type safety at compile time
- No runtime overhead
- Can use advanced Rust features (traits, iterators, Rayon)

---

## Performance Expectations

### Numba Performance (Typical)

**GR4J Model** (10 years daily data, 3650 days):
- Cold start (no cache): ~1-3 seconds
- Cold start (with cache): < 100ms
- Warm execution: < 1ms per run
- Throughput: > 1M days/second

**This is excellent performance** for educational software!

### When Rust Might Help

Rust could provide **marginal gains** (1.5-3x speedup) in:
- Very tight loops with complex branching
- Advanced parallelism (multi-threaded calibration)
- Large-scale batch processing

**But**: Numba is already fast enough for HOLMES use cases.

### Realistic Speedup Expectations

- **Numba → Rust**: 1.5-3x faster (diminishing returns)
- **Pure Python → Numba**: 50-500x faster (huge win!)
- **Pure Python → Rust**: 100-1000x faster (huge win!)

Since HOLMES already uses Numba, the **incremental benefit of Rust is small** compared to the **complexity cost**.

---

## Migration Strategy (If Needed)

If you decide a model needs Rust:

### Phase 1: Prototype in Numba
1. Implement model in Numba first (fast development)
2. Validate correctness with tests
3. Benchmark performance
4. Identify if Rust is truly needed

### Phase 2: Benchmark Before Migrating
1. Profile Numba implementation
2. Identify actual bottlenecks
3. Estimate Rust speedup potential
4. **Decision point**: Is the complexity worth it?

### Phase 3: Gradual Migration
1. Start with single hot function (not entire model)
2. Create Rust implementation with PyO3
3. Write comprehensive tests (same test suite)
4. Benchmark: is it actually faster?
5. If yes, continue; if no, stay with Numba

### Phase 4: Maintain Both (Temporarily)
1. Keep Numba version as reference
2. Run both in test suite
3. Verify identical results
4. Once confident, deprecate Numba version

---

## Real-World Example: GR4J Decision

**Scenario**: GR4J rainfall-runoff model

**Numba Implementation**:
- Development time: 1-2 days
- Performance: < 1ms per run (10 years)
- Cold start: ~2 seconds (mitigated by `cache=True`)
- Maintainability: High (Python developers can modify)
- Educational value: High (students can read and understand)

**Hypothetical Rust Implementation**:
- Development time: 3-5 days (learning curve, FFI setup)
- Performance: ~0.3-0.5ms per run (2-3x faster)
- Cold start: Instant
- Maintainability: Medium (requires Rust expertise)
- Educational value: Medium (fewer contributors can modify)

**Decision**: **Keep Numba** ✅
- Current performance is excellent
- Educational context values accessibility
- Cold-start solved by `cache=True`
- 2-3x speedup not worth complexity cost

**When to Reconsider**:
- Real-time application requirements (< 100μs)
- Need to run on embedded systems
- Integration with other languages required
- Performance profiling shows GR4J is actual bottleneck (unlikely)

---

## Tooling and Ecosystem

### Numba Ecosystem
- **Installation**: `pip install numba`
- **Dependencies**: NumPy (already required)
- **IDE Support**: Excellent (Python)
- **Debugging**: Standard Python tools (pdb, pytest)
- **Profiling**: cProfile, line_profiler
- **Documentation**: Extensive, beginner-friendly

### Rust Ecosystem
- **Installation**: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Dependencies**: PyO3, maturin (build system)
- **IDE Support**: Good (rust-analyzer)
- **Debugging**: gdb/lldb (steeper learning curve)
- **Profiling**: cargo-flamegraph, perf
- **Documentation**: Excellent, but assumes Rust knowledge

---

## Recommendations for HOLMES v3

### Current Status (Good!)
- All models use Numba with excellent performance ✅
- Development velocity is high ✅
- Code is maintainable by Python developers ✅

### Action Items

1. **Immediate** (you're doing this):
   - Add `cache=True` to all `@numba.jit` decorators
   - Eliminates cold-start friction
   - No downside, pure win

2. **Short-term**:
   - Document expected performance baselines
   - Add performance tests to CI
   - Profile SCE-UA calibration to identify any bottlenecks

3. **Medium-term**:
   - Monitor performance as models become more complex
   - Keep Rust as option for future specialized needs
   - Consider Rust for:
     - Distributed calibration (parallel across machines)
     - Real-time forecasting modules (if added)
     - Integration with external tools (if needed)

4. **Long-term**:
   - Revisit this decision if:
     - Performance becomes measurably inadequate
     - Need features Numba can't provide
     - Team gains Rust expertise naturally
   - Don't rewrite working code just to use Rust

### Golden Rule

> **"Premature optimization is the root of all evil."** - Donald Knuth

Numba is already a massive optimization over pure Python. Rust is only needed if you **measure** a performance problem that Numba can't solve.

---

## Conclusion

**For HOLMES v3 educational software**:
- **Default: Numba** (simple, fast, maintainable)
- **Exception: Rust** (only when truly necessary)

The current Numba-based models are **excellent** and align perfectly with the project constitution:
- ✅ Code Simplicity
- ✅ Performance First (already achieved!)
- ✅ Functional Over OO
- ✅ Extensibility by Design
- ✅ Informative UI (Python is readable)

**Keep it simple. Measure before optimizing. Rust is a tool, not a goal.**

---

## Additional Resources

### Numba
- [Numba Documentation](https://numba.readthedocs.io/)
- [Performance Tips](https://numba.readthedocs.io/en/stable/user/performance-tips.html)
- [Troubleshooting](https://numba.readthedocs.io/en/stable/user/troubleshoot.html)

### Rust + Python
- [PyO3 Guide](https://pyo3.rs/)
- [Maturin (Build Tool)](https://www.maturin.rs/)
- [Calling Rust from Python (Tutorial)](https://blog.yossarian.net/2020/08/02/Writing-and-publishing-a-python-module-in-rust)

### Performance
- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
- [NumPy Performance](https://numpy.org/doc/stable/reference/performance.html)

---

**Questions?** Discuss with the team or file an issue on the project repository.
