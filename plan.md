# Simulation Module Implementation Plan

## Overview

Implement the Simulation module for HOLMES v3, allowing users to run single or multiple model configurations with different parameter sets and evaluate performance using multi-criteria assessment. This follows the v2 implementation but adapts it to the modern web architecture.

## Architecture Pattern

Follow the existing v3 architecture established in the Calibration module:
- **Core Logic**: Pure functions in `src/hydro/simulation.py`
- **API Layer**: HTTP endpoints in `src/api/simulation.py`
- **Frontend**: UI in `src/static/simulation.html` and `src/static/scripts/simulation.js`
- **Data Flow**: User → API → Hydro → API → Frontend visualization

## v2 vs v3 Key Differences

| Aspect | v2 (Desktop) | v3 (Web) |
|--------|-------------|----------|
| UI Framework | Tkinter | HTML/CSS/JS |
| Data Structure | Pandas DataFrames | Polars DataFrames |
| Plotting | Matplotlib | Plotly |
| File I/O | CSV import/export via file dialogs | Web file upload/download |
| Processing | Synchronous | Asynchronous |
| State Management | Class attributes | Stateless functions + session data |

## Implementation Tasks

### 1. Backend Core Functions (`src/hydro/simulation.py`)

**Purpose**: Implement multi-criteria evaluation and simulation orchestration.

**Functions to implement**:

1. **`compute_multi_criteria(observed, simulated, epsilon) -> dict`**
   - Compute all 6 performance criteria for a single simulation
   - Criteria:
     - High flows: NSE (no transformation)
     - Medium flows: NSE with sqrt transformation
     - Low flows: NSE with log transformation
     - Water balance: Mean bias (Q_sim.mean() / Q_obs.mean())
     - Flow variability: Deviation bias (CV_sim / CV_obs)
     - Correlation: Pearson correlation coefficient
   - Return dict with criterion names as keys
   - Use Numba JIT for performance

2. **`evaluate_multi_simulations(observed, simulations, epsilon, include_multimodel) -> pl.DataFrame`**
   - Evaluate multiple simulations at once
   - `simulations`: 2D array (n_simulations × n_timesteps)
   - Compute multi-criteria for each simulation
   - If `include_multimodel=True`: compute ensemble mean and evaluate it
   - Return Polars DataFrame with rows for each simulation + optional multimodel
   - Include "Optimal" row with ideal values [1, 1, 1, 1, 1, 1]

3. **`run_multi_simulations(data, hydrological_model, parameter_sets, snow_model, catchment) -> dict`**
   - Run model with multiple parameter sets
   - Return dict containing:
     - `dates`: Date column
     - `observed`: Observed flow
     - `simulations`: List of simulation arrays
     - `multimodel`: Ensemble mean (if requested)
     - `parameter_sets`: Echo back parameter sets for reference

4. **`plot_simulation_results(dates, observed, simulations, multimodel, multi_criteria) -> go.Figure`**
   - Create 2-panel plot:
     - Top: Time series (observed + all simulations + optional multimodel)
     - Bottom: Multi-criteria radar/spider plot
   - Use consistent color scheme from `utils.plotting.colours`
   - Follow v3 dark theme template

5. **`plot_multi_criteria_comparison(multi_criteria_df) -> go.Figure`**
   - Create radar/spider plot for multi-criteria comparison
   - Each simulation gets own trace
   - Optimal values shown as reference
   - All 6 axes with proper scaling

### 2. Backend API Endpoints (`src/api/simulation.py`)

**Purpose**: Expose simulation functionality via HTTP.

**Endpoints to implement**:

1. **`GET /simulation/config`**
   - Return available configuration options
   - Same as calibration: catchments, models, snow models
   - Add: option to enable multimodel ensemble

2. **`POST /simulation/run`**
   - Run simulation(s) with provided parameter sets
   - Request body:
     ```json
     {
       "hydrological_model": "gr4j",
       "catchment": "Au Saumon",
       "snow_model": "cemaneige",
       "simulation_start": "2010-01-01",
       "simulation_end": "2015-12-31",
       "parameter_sets": [
         {"x1": 320, "x2": 0.5, "x3": 90, "x4": 1.8, "name": "Simulation 1"},
         {"x1": 350, "x2": 0.3, "x3": 100, "x4": 2.0, "name": "Simulation 2"}
       ],
       "include_multimodel": true
     }
     ```
   - Response:
     ```json
     {
       "fig": "<plotly json>",
       "multi_criteria": {
         "Optimal": [1, 1, 1, 1, 1, 1],
         "Simulation 1": [0.85, 0.82, 0.75, 0.98, 1.02, 0.89],
         "Simulation 2": [0.83, 0.80, 0.73, 0.97, 1.01, 0.87],
         "Multimodel": [0.86, 0.84, 0.77, 0.99, 1.00, 0.90]
       }
     }
     ```

3. **`POST /simulation/import_calibration`**
   - Import parameter sets from calibration results
   - Request body: calibration results JSON (from calibration module)
   - Response: formatted parameter set ready for simulation
   - Allows seamless workflow: calibrate → simulate

4. **`POST /simulation/export`**
   - Export simulation results to CSV
   - Request body: simulation results
   - Response: CSV file download
   - Columns: Date, Observed, Simulation_1, Simulation_2, ..., Multimodel

### 3. Frontend UI (`src/static/simulation.html`)

**Purpose**: User interface for simulation configuration and results.

**Layout sections**:

1. **Parameter Sets Panel**
   - Import from calibration results (button)
   - Manual entry table:
     - Columns: Name, X1, X2, X3, X4, [Remove]
     - Add row button
     - Validate parameter ranges
   - Import from CSV (file upload)
   - Display count of loaded parameter sets

2. **Simulation Settings Panel**
   - Catchment dropdown (same as calibration)
   - Date range inputs (start/end)
   - Snow model selection
   - "Include multimodel ensemble" checkbox
   - 3-year warmup (always enabled)

3. **Run Simulation Panel**
   - "Run Simulation(s)" button
   - Progress indicator (if needed)
   - Clear results button

4. **Results Visualization Panel**
   - Time series plot container
   - Multi-criteria table/chart container
   - Export button (download CSV)

### 4. Frontend Logic (`src/static/scripts/simulation.js`)

**Purpose**: Handle user interactions and API communication.

**Key functions**:

1. **`loadConfiguration()`**
   - Fetch `/simulation/config`
   - Populate dropdowns

2. **`importFromCalibration(calibrationResults)`**
   - Extract final parameters from calibration
   - Add to parameter sets table
   - Auto-name as "Calibration_1", "Calibration_2", etc.

3. **`addParameterSet(params, name)`**
   - Add row to parameter sets table
   - Validate inputs
   - Enable/disable run button based on validity

4. **`removeParameterSet(index)`**
   - Remove row from table
   - Update indices

5. **`runSimulation()`**
   - Collect all parameter sets from table
   - Collect simulation settings
   - POST to `/simulation/run`
   - Display results

6. **`displayResults(response)`**
   - Render Plotly figure
   - Display multi-criteria table
   - Enable export button

7. **`exportResults()`**
   - POST to `/simulation/export`
   - Trigger file download

### 5. Multi-Criteria Evaluation Details

**Implementation reference from v2 `Model.py:253-267`**:

```python
def compute_multi_criteria(simulated, observed, epsilon):
    """
    Compute 6 performance criteria.

    All computations use observed and simulated with epsilon added
    to avoid division by zero or log(0).
    """
    # 1. High flows (NSE)
    high_flows = 1 - sum((simulated - observed)**2) / sum((observed.mean() - observed)**2)

    # 2. Medium flows (NSE sqrt)
    medium_flows = 1 - sum((simulated**0.5 - observed**0.5)**2) / sum(((observed**0.5).mean() - observed**0.5)**2)

    # 3. Low flows (NSE log)
    low_flows = 1 - sum((log(simulated) - log(observed))**2) / sum((log(observed).mean() - log(observed))**2)

    # 4. Water balance (Mean bias)
    water_balance = simulated.mean() / observed.mean()

    # 5. Flow variability (CV ratio)
    flow_variability = (simulated.std() / simulated.mean()) / (observed.std() / observed.mean())

    # 6. Correlation
    correlation = corrcoef(observed, simulated)[0, 1]

    return [high_flows, medium_flows, low_flows, water_balance, flow_variability, correlation]
```

### 6. Data Flow Diagram

```
User Input (Frontend)
    ↓
Parameter Sets + Settings
    ↓
POST /simulation/run (API)
    ↓
Load catchment data + apply warmup + snow model
    ↓
For each parameter set:
    run_model() → simulation array
    ↓
compute_multi_criteria() for each simulation
    ↓
If multimodel: compute mean → compute_multi_criteria()
    ↓
plot_simulation_results()
    ↓
Return JSON (fig + multi_criteria)
    ↓
Display in Frontend
```

### 7. Testing Strategy

**Unit tests** (`tests/test_simulation.py`):
1. `test_compute_multi_criteria()` - verify calculations
2. `test_evaluate_multi_simulations()` - multiple sims + multimodel
3. `test_run_multi_simulations()` - integration with GR4J
4. `test_plot_generation()` - ensure plots render

**Integration tests** (`tests/test_api_simulation.py`):
1. `test_simulation_config_endpoint()`
2. `test_simulation_run_endpoint()`
3. `test_simulation_export_endpoint()`

**Frontend tests** (Playwright):
1. Load parameter sets manually
2. Import from calibration
3. Run simulation and verify plots appear
4. Export results to CSV

### 8. Dependencies & Imports

**No new dependencies required** - all existing packages support this:
- Polars: DataFrames
- Numba: JIT compilation
- Plotly: Visualization
- NumPy: Numerical operations
- Starlette: API routing

### 9. Migration from v2

**Reusable v2 code** (with adaptations):
- `Model.CompMultiCrit()` → `compute_multi_criteria()` (Polars + Numba)
- `Model.Eval_MultiCrit()` → `evaluate_multi_simulations()` (functional style)
- Multi-criteria names and optimal values (unchanged)

**New v3 features**:
- Web-based parameter table (vs Tkinter grid)
- Seamless calibration → simulation workflow
- JSON-based data exchange
- Modern interactive plots

### 10. Constitutional Alignment

**Principle 1 - Code Simplicity**: Pure functions, clear separation of concerns
**Principle 2 - Functional Over OOP**: All functions are pure, no classes needed
**Principle 3 - Performance First**: Numba JIT for multi-criteria computations
**Principle 4 - Extensibility**: Plugin architecture allows adding new criteria
**Principle 5 - Consistent UI**: Follows calibration UI patterns

## Implementation Order

1. ✅ **Phase 1**: Core functions (`src/hydro/simulation.py`)
2. ✅ **Phase 2**: API endpoints (`src/api/simulation.py`)
3. ✅ **Phase 3**: Basic frontend UI (`src/static/simulation.html`)
4. ✅ **Phase 4**: Frontend logic (`src/static/scripts/simulation.js`)
5. ✅ **Phase 5**: Testing (unit + integration + playwright)
6. ✅ **Phase 6**: Documentation update (`CLAUDE.md`)

## Success Criteria

- [ ] User can import parameter sets from calibration results
- [ ] User can manually add/edit/remove parameter sets
- [ ] User can run simulations with multiple parameter sets
- [ ] System computes all 6 multi-criteria metrics correctly
- [ ] System displays time series plot with all simulations
- [ ] System displays multi-criteria comparison plot
- [ ] Optional multimodel ensemble works correctly
- [ ] User can export results to CSV
- [ ] All tests pass
- [ ] Performance is comparable to calibration module

## Notes

- Warmup period always 3 years (same as calibration)
- Epsilon value: `observed.mean() * 0.01` (same as v2)
- Multi-criteria optimal values: all 1.0 except correlation (0-1 range)
- Color scheme: use `utils.plotting.colours` cycling through simulations
- Error handling: validate parameter ranges, date ranges, data availability
