# Todo

## In progress

- [ ] Add export functionality

## Next steps

### Frontend simplification (high priority)

- [ ] Extract repeated Plotly configuration to utils.js renderPlot()
- [ ] Create API call wrapper with centralized error handling
- [ ] Extract duplicated config table building logic (simulation/projection)
- [ ] Create loading state management wrapper function
- [ ] Remove dead code (equals, checkEscape functions in utils.js)
- [ ] Fix onKey bug: use || instead of | for logical OR

### Frontend simplification (medium priority)

- [ ] Simplify select/option population with template literals
- [ ] Extract theme detection to getTheme() utility
- [ ] Simplify slider creation using innerHTML templates
- [ ] Use classList.toggle() in header toggles
- [ ] Consider helper for hidden attribute toggling
- [ ] Standardize form data gathering pattern

### Testing

**Important:** Use function-based tests (see docs/function-based-testing-guide.md)
**Full details:** See docs/test-plan.md and docs/test-examples.md

**Phase 1: Setup**
- [ ] Create test directory structure (unit/, integration/, fixtures/)
- [ ] Setup conftest.py with common fixtures
- [ ] Create sample fixture data (test catchments, configs)
- [ ] Configure pytest markers and coverage settings

**Phase 2: Unit Tests**
- [ ] Test data module (src/data.py) - data loading functions
- [ ] Test hydro utils (src/hydro/utils.py) - evaluation criteria
- [ ] Test GR4J model (src/hydro/gr4j.py) - core hydrological model
- [ ] Test SCE algorithm (src/hydro/sce.py) - calibration algorithm
- [ ] Test hydro main module (src/hydro/hydro.py) - model interface
- [ ] Test API utils (src/api/utils.py) - decorators and helpers
- [ ] Test calibration module (src/hydro/calibration.py)
- [ ] Test simulation module (src/hydro/simulation.py)
- [ ] Test projection module (src/hydro/projection.py)
- [ ] Test utility modules (src/utils/*)
- [ ] Achieve >80% coverage for critical modules

**Phase 3: Integration Tests**
- [ ] Test calibration workflow (manual and automatic)
- [ ] Test simulation workflow (single, multi-model, ensemble)
- [ ] Test projection workflow (climate scenarios)
- [ ] Test API endpoints end-to-end

**Phase 4: Frontend Tests with Playwright**
- [x] Install and configure Playwright
- [x] Test page loading and navigation
- [x] Test theme toggle and settings
- [x] Test manual calibration workflow in browser
- [ ] Test automatic calibration workflow
- [ ] Test simulation workflow
- [ ] Test projection workflow
- [ ] Test file imports and exports
- [ ] Test plot rendering and interactions

### Other improvements

- [ ] Have plots be fetched again when theme changes
- [ ] Document all models

## Future ideas

- [ ] Convert the models to rust
