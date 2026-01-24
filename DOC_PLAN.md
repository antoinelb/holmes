# HOLMES v3 Documentation Plan

This document outlines the plan for comprehensive documentation similar to [Starlette](https://starlette.io/) and [Polars](https://docs.pola.rs/).

## Tooling

**Framework**: MkDocs with Material theme (like Starlette)
- Light/dark theme support
- Navigation tabs for major sections
- Code syntax highlighting with copy buttons
- MathJax for model equations

**Plugins**:
- `mkdocstrings[python]` - Auto-generate Python API docs from docstrings
- `mkdocs-include-markdown-plugin` - Include CHANGELOG.md
- `mkdocs-git-revision-date-localized-plugin` - Show last updated dates

**Dependencies** (add to `pyproject.toml`):
```toml
[dependency-groups]
docs = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.24",
    "mkdocs-include-markdown-plugin>=6.0",
    "mkdocs-git-revision-date-localized-plugin>=1.2",
]
```

---

## Directory Structure

```
docs/
├── index.md                          # Landing page
├── getting-started/
│   ├── index.md                      # Overview
│   ├── installation.md               # pip install, from source
│   ├── quickstart.md                 # 5-minute tutorial
│   └── configuration.md              # .env options
├── user-guide/
│   ├── index.md                      # Overview
│   ├── interface-overview.md         # Web UI navigation
│   ├── calibration.md                # Manual + automatic calibration
│   ├── simulation.md                 # Forward simulation
│   ├── projection.md                 # Climate projections
│   └── settings.md                   # Preferences, data persistence
├── concepts/
│   ├── index.md                      # Hydrological modeling overview
│   ├── models/
│   │   ├── gr4j.md                   # GR4J: structure, parameters, equations
│   │   ├── bucket.md                 # Bucket: structure, parameters
│   │   └── cemaneige.md              # CemaNeige: snow modeling
│   ├── pet.md                        # Oudin PET calculation
│   ├── calibration-algorithms.md     # SCE-UA explanation
│   └── metrics.md                    # RMSE, NSE, KGE formulas
├── developer-guide/
│   ├── index.md                      # Developer overview
│   ├── architecture.md               # System architecture diagram
│   ├── backend/
│   │   ├── index.md                  # Backend overview
│   │   ├── api-structure.md          # Starlette routes, decorators
│   │   ├── websocket-protocol.md     # Message types and schemas
│   │   ├── data-loading.md           # Polars lazy loading
│   │   └── model-registry.md         # Adding new models
│   ├── rust-extension/
│   │   ├── index.md                  # holmes-rs overview
│   │   ├── building.md               # maturin build instructions
│   │   ├── implementing-models.md    # How to add models
│   │   └── python-bindings.md        # PyO3 patterns
│   ├── frontend/
│   │   ├── index.md                  # Frontend overview
│   │   ├── mev-architecture.md       # Model-Event-View pattern
│   │   ├── pages.md                  # Page module structure
│   │   └── charts.md                 # D3.js visualization
│   └── testing.md                    # Test strategy, commands, coverage
├── api-reference/
│   ├── index.md                      # API overview
│   ├── python/
│   │   ├── data.md                   # data.py module (mkdocstrings)
│   │   ├── models.md                 # models/ package
│   │   └── api.md                    # api/ package
│   ├── rust/
│   │   └── index.md                  # Links to docs.rs + key examples
│   └── websocket/
│       ├── index.md                  # Protocol overview
│       ├── calibration.md            # /calibration endpoint messages
│       ├── simulation.md             # /simulation endpoint messages
│       └── projection.md             # /projection endpoint messages
├── data-formats/
│   ├── index.md                      # Data formats overview
│   ├── observations.md               # *_Observations.csv schema
│   ├── cemaneige-info.md             # *_CemaNeigeInfo.csv schema
│   ├── projections.md                # *_Projections.csv schema
│   └── exports.md                    # Downloaded result files
├── reference/
│   ├── changelog.md                  # Include from CHANGELOG.md
│   └── license.md                    # MIT license
├── assets/
│   ├── images/
│   │   ├── logo.svg                  # HOLMES logo
│   │   ├── favicon.svg               # Browser icon
│   │   ├── architecture.svg          # System architecture diagram
│   │   ├── gr4j-schematic.svg        # GR4J model diagram
│   │   ├── bucket-schematic.svg      # Bucket model diagram
│   │   └── screenshots/              # UI screenshots
│   └── stylesheets/
│       └── extra.css                 # Custom styles
└── overrides/                        # MkDocs Material overrides (if needed)
```

---

## Navigation Structure (mkdocs.yml)

```yaml
nav:
  - Home: index.md
  - Getting Started:
    - getting-started/index.md
    - Installation: getting-started/installation.md
    - Quickstart: getting-started/quickstart.md
    - Configuration: getting-started/configuration.md
  - User Guide:
    - user-guide/index.md
    - Interface Overview: user-guide/interface-overview.md
    - Calibration: user-guide/calibration.md
    - Simulation: user-guide/simulation.md
    - Projection: user-guide/projection.md
    - Settings: user-guide/settings.md
  - Concepts:
    - concepts/index.md
    - Models:
      - GR4J: concepts/models/gr4j.md
      - Bucket: concepts/models/bucket.md
      - CemaNeige: concepts/models/cemaneige.md
    - PET Calculation: concepts/pet.md
    - Calibration: concepts/calibration-algorithms.md
    - Metrics: concepts/metrics.md
  - Developer Guide:
    - developer-guide/index.md
    - Architecture: developer-guide/architecture.md
    - Backend:
      - developer-guide/backend/index.md
      - API Structure: developer-guide/backend/api-structure.md
      - WebSocket Protocol: developer-guide/backend/websocket-protocol.md
      - Data Loading: developer-guide/backend/data-loading.md
      - Model Registry: developer-guide/backend/model-registry.md
    - Rust Extension:
      - developer-guide/rust-extension/index.md
      - Building: developer-guide/rust-extension/building.md
      - Implementing Models: developer-guide/rust-extension/implementing-models.md
      - Python Bindings: developer-guide/rust-extension/python-bindings.md
    - Frontend:
      - developer-guide/frontend/index.md
      - MEV Architecture: developer-guide/frontend/mev-architecture.md
      - Page Modules: developer-guide/frontend/pages.md
      - D3.js Charts: developer-guide/frontend/charts.md
    - Testing: developer-guide/testing.md
  - API Reference:
    - api-reference/index.md
    - Python API:
      - api-reference/python/data.md
      - api-reference/python/models.md
      - api-reference/python/api.md
    - Rust API: api-reference/rust/index.md
    - WebSocket Protocol:
      - api-reference/websocket/index.md
      - Calibration: api-reference/websocket/calibration.md
      - Simulation: api-reference/websocket/simulation.md
      - Projection: api-reference/websocket/projection.md
  - Data Formats:
    - data-formats/index.md
    - Observations CSV: data-formats/observations.md
    - CemaNeige Info: data-formats/cemaneige-info.md
    - Projections CSV: data-formats/projections.md
    - Exported Files: data-formats/exports.md
  - Reference:
    - Changelog: reference/changelog.md
    - License: reference/license.md
```

---

## Key Content Outlines

### Landing Page (docs/index.md)
- Project tagline and description
- Key features (bullet points)
- Quick links to Getting Started, User Guide, Developer Guide
- "Part of" badge linking to Université Laval

### User Guide Pages
Each page should include:
- Overview of the feature
- Step-by-step instructions with screenshots
- Tips and best practices
- Common issues and solutions

### Concepts/Models Pages
Each model page should include:
- Model overview and use cases
- Parameter table (name, range, default, description)
- Mathematical formulation (MathJax)
- Python and Rust usage examples
- References (academic papers)

### WebSocket Protocol Pages
Each endpoint page should include:
- Connection URL
- Client → Server message table (type, data schema, description)
- Server → Client message table (type, data schema, description)
- JSON schema examples

### Data Format Pages
Each format page should include:
- File naming convention
- Required columns table (name, type, description)
- Optional columns table
- Example CSV snippet
- Validation rules and common errors

---

## Existing Content to Incorporate

1. **README.md** → Basis for `getting-started/installation.md` and `getting-started/quickstart.md`
2. **CHANGELOG.md** → Include directly in `reference/changelog.md`
3. **src/holmes-rs/README.md** → Excellent foundation for:
   - `concepts/models/*.md` (parameter tables, code examples)
   - `api-reference/rust/index.md`
   - `developer-guide/rust-extension/index.md`
4. **CLAUDE.md** → Basis for `developer-guide/testing.md`

## Build and Deployment

### Local Development
```bash
# Install docs dependencies
uv sync --group docs

# Serve with auto-reload
mkdocs serve

# Build static site
mkdocs build
```

### GitHub Actions (`.github/workflows/docs.yml`)
```yaml
name: Deploy Documentation
on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml', 'src/holmes/**/*.py']
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install uv && uv sync --group docs
      - run: mkdocs gh-deploy --force
```

---

## Implementation Phases

### Phase 1: Foundation
- [x] Create `docs/` directory structure
- [x] Create `mkdocs.yml` configuration
- [x] Add docs dependencies to `pyproject.toml`
- [x] Write landing page (`docs/index.md`)
- [x] Set up GitHub Actions workflow

### Phase 2: Getting Started & User Guide
- [ ] Installation guide
- [ ] Quickstart tutorial (with screenshots)
- [ ] Configuration reference
- [ ] Interface overview (with screenshots)
- [ ] Calibration, Simulation, Projection tutorials
- [ ] Settings documentation

### Phase 3: Concepts
- [ ] GR4J documentation with equations
- [ ] Bucket documentation with equations
- [ ] CemaNeige documentation
- [ ] PET (Oudin) documentation
- [ ] SCE-UA calibration algorithm
- [ ] Metrics (RMSE, NSE, KGE) with formulas

### Phase 4: Developer Guide
- [ ] Architecture overview with diagram
- [ ] Backend: API structure, WebSocket protocol, data loading, model registry
- [ ] Rust extension: building, implementing models, PyO3 patterns
- [ ] Frontend: MEV architecture, page modules, D3.js charts
- [ ] Testing guide

### Phase 5: API Reference
- [ ] Configure mkdocstrings for Python API
- [ ] Document WebSocket message schemas
- [ ] Link to Rust docs (docs.rs or inline)

### Phase 6: Data Formats
- [ ] Document all CSV schemas
- [ ] Document exported file formats

### Phase 7: Polish
- [ ] Cross-link between sections
- [ ] Add search keywords
- [ ] Test all code examples
- [ ] Review and copyedit
- [ ] Add UI screenshots

---

## Critical Files to Reference During Implementation

| Documentation Page | Source Files |
|-------------------|--------------|
| WebSocket Protocol | `src/holmes/api/calibration.py`, `simulation.py`, `projection.py` |
| Python API | `src/holmes/data.py`, `models/*.py`, `api/utils.py` |
| Rust Models | `src/holmes-rs/src/hydro/*.rs`, `snow/*.rs`, `pet/*.rs` |
| Model Parameters | `src/holmes-rs/README.md` (excellent parameter tables) |
| Data Formats | `src/holmes/data/*.csv` (example files) |
| Frontend Architecture | `src/holmes/static/scripts/*.js` |
| Configuration | `src/holmes/config.py`, `.env` example |

---

## Success Criteria

1. **Users** can follow the quickstart and run their first calibration within 5 minutes
2. **Developers** can understand the architecture
3. **Researchers** can understand the mathematical formulation of each model
4. All code examples are tested and work
5. Documentation is searchable and cross-linked
6. Dark mode works properly
7. Mobile-responsive layout
