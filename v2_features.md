# HOLMES v2 Features Documentation

## Overview
HOLMES (HydrOLogical Modeling Educational Software) is an educational desktop application designed for teaching graduate students hydrological prediction and operational hydrology. Developed at Université Laval, Québec, Canada, it provides hands-on learning experiences with real-world hydrological models and datasets. The application is built using Python with Tkinter for the GUI and follows a Model-View-Controller (MVC) architecture.

## Educational Context
This software is specifically designed for graduate-level courses in hydrological prediction, providing students with:
- Practical experience in model calibration techniques
- Understanding of objective functions and their impacts
- Exposure to climate change scenario analysis
- Hands-on work with real catchment data from Quebec watersheds

## Part 1: User-Facing Functionality

### A. Core Features

### 1. User Interface & Navigation
- **Desktop Application**: Built with Tkinter GUI framework
- **Main Task Manager**: Three primary workflows accessible via buttons:
  - Calibration
  - Simulation
  - Projection
- **Menu System**:
  - File menu with Exit option
  - Help menu with About dialog
- **Responsive Layout**: Auto-adjusts to 85% of screen size
- **Window Management**: Always on top focus handling

### 2. Hydrological Modeling

#### 2.1 Supported Models
- **GR4J**: 4-parameter daily rainfall-runoff model
  - Parameters: X1 (production store capacity), X2 (groundwater exchange), X3 (routing store capacity), X4 (unit hydrograph time base)
  - Daily timestep
  - Percolation and routing processes
  - Optimized with Numba JIT compilation

#### 2.2 Snow Modeling
- **CemaNeige**: Snow accounting routine
  - Optional integration with hydrological models
  - Parameters: Ctg (thermal state weighting), Kf (degree-day melt factor)
  - Elevation band-based approach
  - Temperature gradient calculations
  - Snow accumulation and melt processes

#### 2.3 Evapotranspiration
- **Oudin Method**: Temperature-based potential evapotranspiration
  - Latitude-dependent calculations
  - Solar radiation estimation
  - Daily timestep computation

### 3. Calibration Module

#### 3.1 Calibration Methods
- **Manual Calibration**:
  - Interactive parameter sliders
  - Real-time model runs
  - Visual feedback with plots
  - Parameter bounds enforcement

- **Automatic Calibration (SCE-UA)**:
  - Shuffled Complex Evolution algorithm
  - Configurable hyperparameters:
    - Number of complexes (ngs)
    - Complex members (npg)
    - Simplex members (nps)
    - Evolution steps (nspl)
    - Maximum evaluations (maxn)
    - Convergence criteria (kstop, pcento)
  - Default or custom hyperparameter values

#### 3.2 Objective Functions
- **NSE** (Nash-Sutcliffe Efficiency)
- **KGE** (Kling-Gupta Efficiency)
- **RMSE** (Root Mean Square Error)

#### 3.3 Flow Transformations
- **High Flows**: No transformation
- **Medium Flows**: Square root transformation
- **Low Flows**: Logarithmic transformation

#### 3.4 Calibration Settings
- Catchment selection from available datasets
- Date range specification
- Automatic 3-year warm-up period
- Snow model integration (optional)
- Export calibration results to CSV

### 4. Simulation Module

#### 4.1 Simulation Capabilities
- Import multiple calibrated parameter sets
- Run single or multiple model configurations
- Multimodel ensemble simulations
- Automatic warm-up period handling

#### 4.2 Performance Evaluation
- **Multi-criteria assessment**:
  - High flows (NSE)
  - Medium flows (NSE with sqrt transformation)
  - Low flows (NSE with log transformation)
  - Water balance (Mean bias)
  - Flow variability (Deviation bias)
  - Correlation coefficient
- Comparative visualization against optimal values

#### 4.3 Visualization
- Time series plots of observed vs simulated flows
- Multiple simulation overlay
- Multimodel mean calculation
- Grid-based multi-criteria performance plots
- Color-coded simulation differentiation

### 5. Projection Module

#### 5.1 Climate Scenarios
- **Climate Models**: Multiple GCM support (e.g., CSI_10Members, BNU_1Member, etc.)
- **RCP Scenarios**: RCP4.5 and RCP8.5
- **Time Horizons**:
  - H20 (2020s)
  - H50 (2050s)
  - H80 (2080s)
  - REF (Reference period)

#### 5.2 Projection Features
- Multi-member ensemble processing
- Automatic climate data processing
- Snow model integration for projections
- PET calculation using Oudin method
- Climate indicator computation

#### 5.3 Climate Indicators
- **EH**: Winter low water period (Jan-Mar)
- **CP**: Spring flood period (Mar-Jun)
- **EE**: Summer low water period (May-Oct)
- **CA**: Autumn flood period (Sep-Dec)
- **MI**: Mean annual flow

#### 5.4 Outputs
- Excel export with multiple sheets:
  - Climate indicators
  - Precipitation series
  - Evapotranspiration series
  - Temperature series
  - Streamflow projections
- Climatology visualization (mean interannual daily flows)

### 6. Data Management

#### 6.1 Input Data Formats (Subject to change)
- **CSV Files**: Observations with columns:
  - Date (YYYY-MM-DD format)
  - P (Precipitation in mm/day)
  - E0 (Potential evapotranspiration in mm/day)
  - Qo (Observed streamflow in mm/day)
  - T (Temperature in °C)
- **Pickle Files**: Climate projections (.pkl)
  - Nested dictionary structure with climate models, scenarios, and horizons
  - Contains ensemble member data for each variable
- **CemaNeige Info Files**: Catchment-specific snow parameters
  - QNBV: Median annual snowfall
  - AltiBand: Elevation bands (semicolon-separated)
  - Z50: Median elevation
  - Lat: Catchment latitude for PET calculations

#### 6.2 Data Processing
- Automatic database building from data directory
- Multiple catchment support
- Temporal subsetting with warm-up periods
- Missing data handling
- Unit conversions (mm/day)

### 7. Visualization & Plotting

#### 7.1 Plot Types
- **Time Series**: Streamflow observations vs simulations
- **Parameter Evolution**: During manual calibration
- **Objective Function**: Convergence tracking
- **Multi-Criteria Spider Plots**: Performance assessment
- **Climatology Plots**: Mean seasonal patterns

#### 7.2 Visual Features
- ColorBrewer color schemes
- Interactive matplotlib plots
- Real-time plot updates during calibration
- Legend management
- Grid and axis customization
- Auto-scaling capabilities

### 8. Export & Save Features

#### 8.1 Calibration Results
- CSV format with calibration settings
- Best parameter sets
- Objective function values
- Model configuration

#### 8.2 Simulation Results
- CSV export with time series
- Multi-model results in columns
- Metadata preservation
- Performance metrics

#### 8.3 Projection Results
- Excel workbooks with multiple sheets
- Climate indicators summary
- Ensemble member results
- Formatted date indices

## Part 2: Technical Capabilities

### Architecture & Implementation
- **MVC Pattern**:
  - Model: Data handling and computations
  - View: Plotting and visualization
  - Controller: Application logic and user interaction

### Performance Optimizations
- **Numba JIT Compilation**: Core model routines
- **Numpy Arrays**: Efficient numerical computations
- **Vectorized Operations**: Batch processing capabilities

### Dependencies
- **Core**: Python 3.x, Tkinter
- **Scientific**: NumPy, Pandas, Matplotlib
- **Optimization**: Numba
- **File I/O**: CSV, Pickle, XlsxWriter

### Cross-Platform Compatibility
- Anaconda distribution support
- Platform detection (Windows/Linux/Mac)
- Configurable graphics backend

## Educational Features

### Learning Support
- Step-by-step calibration process
- Visual feedback for parameter sensitivity
- Comparative analysis tools
- Multiple objective function options
- Real-world catchment datasets

### Research Applications
- Climate change impact assessment
- Multi-model ensemble analysis
- Uncertainty quantification
- Performance benchmarking
- Scenario comparison

## File Organization

```
HOLMES_v2/
├── HOLMES_v2.py          # Main application entry
├── soft/
│   ├── Model.py          # Data management
│   ├── View.py           # Visualization
│   ├── CalFrame.py       # Calibration UI
│   ├── SimFrame.py       # Simulation UI
│   └── ProjFrame.py      # Projection UI
├── fun/
│   ├── GR4J.py           # Hydrological model
│   ├── CemaNeige.py      # Snow model
│   ├── Oudin.py          # PET calculation
│   └── SCE.py            # Optimization algorithm
└── data/
    ├── *_Observations.csv # Historical data
    ├── *_Projections.pkl  # Climate projections
    └── *_CemaNeigeInfo.csv # Snow parameters
```

## Part 3: Current Limitations & Web Migration Considerations

### Current Desktop-Specific Limitations
- **Single-user application**: No multi-user support or collaboration features
- **Local data storage**: All data must be stored locally in specific folder structure
- **Synchronous processing**: UI blocks during long computations
- **Platform dependencies**: Requires Anaconda installation and specific configuration
- **No data persistence**: Results must be manually saved/loaded
- **Limited scalability**: Cannot leverage cloud computing resources
- **No remote access**: Must be installed on each user's machine

### Technical Components Requiring Migration
- **Tkinter GUI components** → Web-based UI framework
- **File dialog interactions** → Web file upload/download components
- **Local file system access** → Cloud storage or database
- **Matplotlib desktop backend** → Web-compatible plotting libraries
- **Synchronous processing** → Asynchronous task queues
- **Pickle serialization** → JSON or database storage
- **Direct memory management** → Session-based state management

### Recommended Web Architecture Components
- **Frontend**:
  - React/Vue.js for interactive UI
  - TypeScript for type safety
  - Material-UI or Bootstrap for consistent design
  - Redux/Vuex for state management

- **Backend**:
  - FastAPI/Django for REST API
  - GraphQL for flexible data queries
  - WebSockets for real-time updates

- **Computation Engine**:
  - Celery/RQ for async task processing
  - NumPy/Pandas remain for calculations
  - Consider GPU acceleration for large ensembles

- **Data Layer**:
  - PostgreSQL for structured data
  - TimescaleDB for time series optimization
  - Redis for caching and session storage
  - S3-compatible storage for file uploads

- **Visualization**:
  - Plotly.js for interactive charts
  - D3.js for custom visualizations
  - Leaflet for potential map integration

- **Infrastructure**:
  - Docker containerization
  - Kubernetes for orchestration
  - CI/CD pipeline (GitHub Actions/GitLab CI)
  - Cloud deployment (AWS/GCP/Azure)

- **Additional Features for Web**:
  - User authentication and authorization
  - Multi-tenancy support
  - Collaborative features
  - API for programmatic access
  - Result sharing and export
  - Version control for configurations
  - Audit logging
  - Performance monitoring

### Migration Priority Features
1. **High Priority** (Core educational functionality):
   - Calibration workflow
   - Simulation execution
   - Basic visualizations
   - Data import/export

2. **Medium Priority** (Enhanced learning):
   - Multi-model comparisons
   - Climate projections
   - Advanced visualizations
   - Performance metrics

3. **Low Priority** (Nice to have):
   - Collaborative features
   - Custom model integration
   - Advanced analytics
   - Mobile responsiveness