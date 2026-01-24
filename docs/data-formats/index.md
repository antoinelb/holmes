# Data Formats

HOLMES uses CSV files for input data and exports results in both CSV and JSON formats.

## Input Files

Input data files must be placed in the `src/holmes/data/` directory. Each catchment requires:

| File | Required | Description |
|------|----------|-------------|
| [`<Catchment>_Observations.csv`](observations.md) | Yes | Daily hydrometeorological observations |
| [`<Catchment>_CemaNeigeInfo.csv`](cemaneige-info.md) | No | Snow model configuration (required for CemaNeige) |
| [`<Catchment>_Projections.csv`](projections.md) | No | Climate projection data |

The catchment name in the filename determines how it appears in the application.

## Export Files

HOLMES can export results from calibration, simulation, and projection pages. See [Exported Files](exports.md) for detailed format specifications.

| Page | Files | Format |
|------|-------|--------|
| Calibration | Parameters, results, timeseries | JSON, JSON, CSV |
| Simulation | Results, timeseries | JSON, CSV |
| Projection | Timeseries, results | CSV, CSV |
