# SCE-UA Calibration Implementation Plan

## Overview
This plan outlines the implementation of the Shuffled Complex Evolution (SCE-UA) algorithm for automatic calibration in HOLMES v3, transitioning from the v2 object-oriented implementation to a functional, web-optimized approach.

## Design Decisions

### 1. Real-time Progress Updates: WebSockets
- Use WebSockets for bidirectional communication between backend and frontend
- Stream calibration progress updates (iteration count, best parameters, objective values)
- Allow potential for user cancellation during optimization

### 2. Processing Model: Async with Streaming
- Implement as async endpoint that maintains WebSocket connection
- Non-blocking execution to handle multiple users
- Stream incremental results as algorithm progresses

### 3. Performance: Vectorization + Selective Numba
- Vectorize population evaluation where possible (batch model runs)
- Use Numba JIT for performance-critical inner loops
- Leverage existing GR4J Numba optimization

### 4. Results Structure: Manual-Compatible + Metadata
- Return same format as manual calibration for plot compatibility
- Include convergence diagnostics (gnrng, iteration history)
- Provide full parameter evolution for visualization

### 5. Error Handling: Minimal (MVP approach)
- Let errors propagate naturally for debugging
- Add comprehensive error handling in later iterations

---

## Implementation Architecture

### Core Components

```
src/hydro/sce.py              # SCE algorithm (functional implementation)
src/api/calibration.py         # Updated endpoint with WebSocket support
src/static/scripts/calibration.js  # WebSocket client integration
```

### Data Flow

```
Frontend (WebSocket)
    ↓ (calibration request)
Backend async handler
    ↓ (spawns)
SCE calibration loop
    ↓ (yields progress)
WebSocket stream
    ↓ (updates)
Frontend plot updates
    ↓ (final)
Return complete results
```

---

## Detailed Implementation Plan

### Phase 1: Core SCE Algorithm (Functional)

#### 1.1 Population Management Functions

**File**: `src/hydro/sce.py`

```python
# Pure functions for SCE operations

def generate_initial_population(
    n_complexes: int,
    n_per_complex: int,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
    initial_point: np.ndarray | None = None,
    seed: int | None = None,
) -> np.ndarray:
    """Generate initial population using Latin Hypercube or random sampling."""
    # Implementation: uniform random sampling within bounds
    # If initial_point provided, include as first individual

def evaluate_population(
    population: np.ndarray,
    model_func: Callable,
    data: pl.DataFrame,
    param_names: list[str],
    criteria: Literal["rmse", "nse", "kge"],
    transformation: Literal["log", "sqrt", "none"],
) -> tuple[np.ndarray, np.ndarray]:
    """
    Evaluate objective function for entire population.
    Returns: (sorted_objectives, sorted_population)

    Optimization: Vectorize where possible, but model runs are sequential
    due to Numba JIT compilation constraints.
    """
    # Extract data once (avoid repeated dataframe operations)
    # Loop through population and evaluate each parameter set
    # Sort by objective value (ascending for RMSE, descending for NSE/KGE)
    # Return sorted objectives and corresponding population
```

#### 1.2 Complex Partitioning

```python
def partition_into_complexes(
    population: np.ndarray,
    objectives: np.ndarray,
    n_complexes: int,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """
    Partition population into complexes using systematic sampling.
    Each complex gets every n_complexes-th member.
    """
    # Implementation matches v2: cx[k1, :] = x[k2, :] where k2 = k1 * ngs + igs

def merge_complexes(
    complexes: list[np.ndarray],
    complex_objectives: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Merge complexes back into single population and sort."""
    # Concatenate all complexes
    # Sort by objective value
    # Return merged population and objectives
```

#### 1.3 Simplex Selection and Evolution

```python
def select_simplex_indices(
    n_per_complex: int,
    n_simplex: int,
    seed: int | None = None,
) -> np.ndarray:
    """
    Select simplex from complex using triangular probability distribution.
    Matches v2 implementation:
    lpos = floor(npg + 0.5 - sqrt((npg + 0.5)^2 - npg*(npg+1)*random()))
    """
    # Implementation: sample n_simplex unique indices
    # Use triangular distribution (favors better points)
    # Ensure no duplicates

@numba.jit(nopython=True)
def competitive_complex_evolution(
    simplex: np.ndarray,
    simplex_objectives: np.ndarray,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
    alpha: float = 1.0,
    beta: float = 0.5,
) -> tuple[np.ndarray, float]:
    """
    CCE: Evolve simplex using Nelder-Mead-like operations.

    Steps:
    1. Reflection: snew = centroid + alpha * (centroid - worst)
    2. If out of bounds: random point
    3. If worse than worst: Contraction: snew = worst + beta * (centroid - worst)
    4. If still worse: random point

    Returns: (new_point, None)  # objective evaluated outside (not Numba compatible)
    """
    # Numba-optimized for performance
    # Return new point (evaluation happens outside)

def evolve_complex(
    complex_pop: np.ndarray,
    complex_obj: np.ndarray,
    n_simplex: int,
    n_evolution_steps: int,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
    model_func: Callable,
    data: pl.DataFrame,
    param_names: list[str],
    criteria: str,
    transformation: str,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Evolve a single complex for n_evolution_steps iterations.

    For each step:
    1. Select simplex
    2. Perform CCE
    3. Evaluate new point
    4. Replace worst point in simplex
    5. Reintegrate simplex into complex
    6. Sort complex
    """
    # Implementation: loop nspl times
    # Call select_simplex_indices, competitive_complex_evolution
    # Evaluate new point using model
    # Update complex
```

#### 1.4 Convergence Criteria

```python
def compute_normalized_geometric_range(
    population: np.ndarray,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
) -> float:
    """
    Compute gnrng: normalized geometric mean of parameter ranges.
    gnrng = exp(mean(log((max(x) - min(x)) / (bu - bl))))
    """
    # Implementation matches v2

def check_convergence(
    objective_history: np.ndarray,
    kstop: int,
    pcento: float,
) -> tuple[bool, float]:
    """
    Check if convergence criteria met.

    Requires at least kstop iterations.
    Computes percent change over last kstop iterations.

    Returns: (converged, percent_change)
    """
    # Implementation:
    # criter_change = abs(criter[-1] - criter[-kstop]) * 100 / mean(abs(criter[-kstop:]))
```

#### 1.5 Main SCE Loop

```python
async def run_sce_calibration(
    model: Callable,
    data: pl.DataFrame,
    params: dict[str, dict[str, int | float | bool]],
    criteria: Literal["rmse", "nse", "kge"],
    transformation: Literal["log", "sqrt", "none"],
    n_complexes: int,
    n_per_complex: int,
    min_complexes: int,
    n_evolution_steps: int,
    max_evaluations: int,
    kstop: int,
    pcento: float,
    peps: float,
    progress_callback: Callable[[dict], None] | None = None,
) -> Results:
    """
    Main SCE-UA calibration loop.

    Async to support WebSocket streaming.
    progress_callback: function to send updates (WebSocket.send)

    Algorithm:
    1. Generate initial population
    2. Evaluate initial population
    3. While not converged and evaluations < max_evaluations:
        a. Partition into complexes
        b. Evolve each complex (nspl steps)
        c. Merge complexes
        d. Sort population
        e. Check convergence (gnrng and pcento)
        f. Send progress update via callback
    4. Return Results with parameter evolution history
    """
    # Implementation:
    # - Initialize population
    # - Track: bestx, bestf, BESTX history, ICALL
    # - Main loop with convergence checks
    # - Yield progress at each shuffle
    # - Return Results compatible with plot_simulation
```

---

### Phase 2: WebSocket Integration

#### 2.1 Backend WebSocket Endpoint

**File**: `src/api/calibration.py`

```python
from starlette.websockets import WebSocket, WebSocketDisconnect

async def _run_automatic_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for automatic calibration.

    Protocol:
    1. Accept WebSocket connection
    2. Receive calibration config (JSON)
    3. Validate parameters
    4. Run SCE with progress callback
    5. Stream progress updates
    6. Send final results
    7. Close connection
    """
    await websocket.accept()

    try:
        # Receive config
        config = await websocket.receive_json()

        # Extract parameters (same as _run_automatic)
        data_ = _read_data(...)

        # Define progress callback
        async def send_progress(update: dict):
            await websocket.send_json(update)

        # Run calibration
        results = await hydro.models.calibrate_model(
            ...,
            progress_callback=send_progress,
        )

        # Generate final plot
        simulation = hydro.models.run_model(...)
        fig = hydro.models.plot_simulation(...)

        # Send final results
        await websocket.send_json({
            "type": "complete",
            "fig": fig.to_json(),
            "results": results,
        })

    except WebSocketDisconnect:
        # Handle client disconnect (cancel calibration?)
        pass
    finally:
        await websocket.close()

# Update get_routes()
def get_routes() -> list[BaseRoute]:
    return [
        ...,
        WebSocketRoute("/run_automatic_ws", endpoint=_run_automatic_ws),
    ]
```

**Progress Update Schema**:
```python
{
    "type": "progress",
    "iteration": int,
    "evaluations": int,
    "best_objective": float,
    "best_params": dict[str, float],
    "gnrng": float,
    "percent_change": float,
}
```

#### 2.2 Frontend WebSocket Client

**File**: `src/static/scripts/calibration.js`

```javascript
async function runAutomatic(event) {
  event.preventDefault();

  // Create WebSocket connection
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${window.location.host}/calibration/run_automatic_ws`);

  ws.onopen = () => {
    // Send configuration
    const config = {
      hydrological_model: document.getElementById("calibration__hydrological-model").value,
      catchment: document.getElementById("calibration__catchment").value,
      // ... all other parameters
    };
    ws.send(JSON.stringify(config));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "progress") {
      // Update progress display
      updateProgress(data);
    } else if (data.type === "complete") {
      // Render final plot
      const figData = JSON.parse(data.fig);
      model.results = data.results;

      const fig = document.querySelector("#calibration .results__fig");
      clear(fig);
      Plotly.newPlot(fig, figData.data, figData.layout, {...});

      ws.close();
    }
  };

  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
  };
}

function updateProgress(data) {
  // Show iteration count, best objective, gnrng, etc.
  // Could update a simple text display or live plot
  console.log(`Iteration ${data.iteration}: objective = ${data.best_objective}, gnrng = ${data.gnrng}`);
}
```

---

### Phase 3: Results Formatting

#### 3.1 Results Structure

Match manual calibration structure:

```python
Results = TypedDict({
    "params": dict[str, list[float]],  # Parameter evolution history
    "objective": list[float],          # Objective value history
})
```

**For SCE**: Return every shuffle iteration's best point (not every evaluation)

This keeps data manageable and provides meaningful evolution trajectory.

#### 3.2 Plot Integration

Reuse existing `plot_simulation()` function:
- Bottom panel: observed vs simulated flow (final parameters)
- Top panels: parameter evolution + objective evolution

No changes needed to plotting code!

---

### Phase 4: Performance Optimization

#### 4.1 Vectorization Opportunities

**Limited vectorization** due to:
- GR4J model uses Numba JIT (not vectorizable across population)
- Each model run has state (stores, hydrographs)

**Possible optimizations**:
1. **Pre-extract data arrays** (precipitation, evapotranspiration, flow) once
2. **Vectorize post-processing** (transformations, objective calculations)
3. **Minimize Polars operations** in hot loop

#### 4.2 Numba Usage

Already optimized:
- `gr4j.run_model()` uses Numba
- `competitive_complex_evolution()` uses Numba

New Numba functions:
- `compute_normalized_geometric_range()` - simple math, good Numba candidate
- Simplex operations in CCE

**Do NOT Numba**:
- Main loop (needs async, callbacks)
- Model evaluation wrapper (calls Numba internally)

#### 4.3 Async Considerations

- Use `await asyncio.sleep(0)` periodically to yield control
- Send WebSocket updates at each shuffle (not every evaluation)
- Consider `asyncio.to_thread()` if blocking becomes issue

---

### Phase 5: Testing Strategy

#### 5.1 Unit Tests

```python
# tests/test_sce.py

def test_generate_initial_population():
    # Test shape, bounds, initial point inclusion

def test_evaluate_population():
    # Test with known parameters, check sorting

def test_partition_into_complexes():
    # Verify systematic sampling

def test_select_simplex_indices():
    # Check triangular distribution, no duplicates

def test_competitive_complex_evolution():
    # Test reflection, contraction, boundary handling

def test_convergence_criteria():
    # Test gnrng and pcento calculations
```

#### 5.2 Integration Tests

```python
def test_full_sce_calibration():
    # Run on small test case (low maxn)
    # Verify results structure
    # Check improvement over iterations

async def test_websocket_endpoint():
    # Use Starlette TestClient
    # Verify message protocol
```

#### 5.3 Manual Testing

- Test with real catchment data
- Compare results with v2 implementation
- Verify WebSocket updates appear in browser console
- Check plot rendering

---

## Implementation Checklist

### Backend (Python)

- [ ] `src/hydro/sce.py` - Core algorithm functions
  - [ ] `generate_initial_population()`
  - [ ] `evaluate_population()`
  - [ ] `partition_into_complexes()`
  - [ ] `merge_complexes()`
  - [ ] `select_simplex_indices()`
  - [ ] `competitive_complex_evolution()` (Numba)
  - [ ] `evolve_complex()`
  - [ ] `compute_normalized_geometric_range()` (Numba)
  - [ ] `check_convergence()`
  - [ ] `run_sce_calibration()` (async, main loop)

- [ ] `src/api/calibration.py` - WebSocket endpoint
  - [ ] Add WebSocket route
  - [ ] Implement `_run_automatic_ws()`
  - [ ] Define progress update schema
  - [ ] Handle WebSocket disconnect

- [ ] `src/hydro/models.py` - Update calibrate_model
  - [ ] Add `progress_callback` parameter
  - [ ] Pass through to `sce.run_sce_calibration()`
  - [ ] Format results for plotting

### Frontend (JavaScript)

- [ ] `src/static/scripts/calibration.js`
  - [ ] Modify `runAutomatic()` to use WebSocket
  - [ ] Implement WebSocket connection logic
  - [ ] Add `updateProgress()` function
  - [ ] Handle WebSocket errors
  - [ ] Update UI during calibration

- [ ] `src/static/index.html`
  - [ ] Add progress display elements (optional)
  - [ ] Loading indicators during calibration

### Testing

- [ ] Unit tests for all SCE functions
- [ ] Integration test for full calibration
- [ ] WebSocket endpoint test
- [ ] Manual browser testing

---

## Implementation Order

1. **Core SCE functions** (bottom-up)
   - Start with utility functions (convergence, partitioning)
   - Then simplex operations
   - Finally main loop (without WebSocket)

2. **Basic async endpoint** (HTTP first)
   - Get calibration working with simple HTTP endpoint
   - Verify results structure and plotting

3. **WebSocket integration**
   - Add WebSocket endpoint
   - Implement progress streaming
   - Update frontend

4. **Performance optimization**
   - Profile bottlenecks
   - Add Numba where beneficial
   - Optimize data handling

5. **Polish and testing**
   - Comprehensive tests
   - Error handling improvements
   - Documentation

---

## Performance Expectations

### v2 Reference
- Default: ngs=25, npg=9 (for 4 params), maxn=5000
- Population size: 225 individuals
- ~5000 GR4J evaluations max
- Runtime: ~30-60 seconds (depends on data size)

### v3 Targets
- Same or better performance (Numba optimization)
- Real-time updates every shuffle (~every 450 evaluations for ngs=25, nspl=9)
- Non-blocking for web environment

---

## Open Questions / Future Enhancements

1. **Cancellation**: Allow user to stop calibration via WebSocket?
2. **Multiple users**: Queue system if many simultaneous calibrations?
3. **Progress visualization**: Live updating plots vs text indicators?
4. **Result caching**: Store calibration runs in database?
5. **Hyperparameter tuning**: Auto-compute npg, nps, nspl from n_params?
6. **Latin Hypercube Sampling**: Better initial population than random?

---

## References

- Duan, Q., Sorooshian, S., & Gupta, V. K. (1992). Effective and efficient global optimization for conceptual rainfall-runoff models. Water Resources Research, 28(4), 1015-1031.
- v2 implementation: `v2/holmes/fun/SCE.py`
- Van Hoey S. (2011). Original Python implementation (GitHub)

---

## Notes

- **Functional approach**: All functions are pure where possible (no side effects)
- **Type hints**: Full type annotations for maintainability
- **Async-first**: Designed for async/await from the start
- **Educational focus**: Keep code readable for students
- **Web-optimized**: Streaming, non-blocking, real-time feedback
