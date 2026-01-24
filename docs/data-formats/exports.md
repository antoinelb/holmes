# Exported Files

HOLMES exports results in CSV and JSON formats from calibration, simulation, and projection pages.

## Calibration Exports

### Parameters (JSON)

Filename: `<catchment>_<model>_params.json`

Contains the calibration configuration and optimized parameters.

```json
{
  "catchment": "Au Saumon",
  "hydroModel": "gr4j",
  "snowModel": "cemaneige",
  "objective": "nse",
  "start": "1980-01-01",
  "end": "1990-12-31",
  "hydroParams": {
    "X1": 350.2,
    "X2": -0.5,
    "X3": 90.1,
    "X4": 1.5
  }
}
```

### Results (JSON)

Filename: `<catchment>_<model>_calibration_results.json`

Contains the optimization history with parameters and objective values at each iteration.

```json
{
  "parameters": [
    {"X1": 300.0, "X2": 0.0, "X3": 50.0, "X4": 1.0},
    {"X1": 350.2, "X2": -0.5, "X3": 90.1, "X4": 1.5}
  ],
  "nse": [0.65, 0.82]
}
```

### Timeseries (CSV)

Filename: `<catchment>_<model>_calibration_data.csv`

Daily observed and simulated streamflow.

```csv
date,observation,simulation
1980-01-01,0.63,0.58
1980-01-02,0.58,0.55
```

## Simulation Exports

### Results (JSON)

Filename: `<catchment>_simulation_results.json`

Contains configuration and performance metrics for all simulations.

```json
{
  "calibrationConfig": [
    {
      "name": "simulation_1",
      "catchment": "Au Saumon",
      "hydroModel": "gr4j",
      "params": [350.2, -0.5, 90.1, 1.5]
    }
  ],
  "config": {
    "start": "1991-01-01",
    "end": "2000-12-31"
  },
  "results": {
    "nse": [0.78],
    "kge": [0.81]
  }
}
```

### Timeseries (CSV)

Filename: `<catchment>_simulation_data.csv`

Daily streamflow with columns for each simulation and observations.

```csv
date,simulation_1,simulation_2,observation
1991-01-01,0.45,0.48,0.52
1991-01-02,0.42,0.44,0.49
```

## Projection Exports

### Timeseries (CSV)

Filename: `<catchment>_projection_data.csv`

Daily simulated streamflow for the selected projection scenario.

```csv
date,streamflow,model,horizon,scenario
2050-01-01,0.32,CSI,2050,RCP45
2050-01-02,0.35,CSI,2050,RCP45
```

### Results (CSV)

Filename: `<catchment>_projection_results.csv`

Summary metrics for each ensemble member.

```csv
member,winter_min,summer_min,spring_max,autumn_max,mean
1,0.12,0.08,2.45,1.89,0.65
2,0.15,0.09,2.31,1.76,0.62
```
