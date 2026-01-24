# Projection

The Projection page explores how streamflow might change under future climate scenarios. Using calibrated model parameters and climate model projections, you can assess potential impacts of climate change on water resources.

## Overview

Climate projection simulates streamflow using:

1. **Calibrated model parameters** from the Calibration page
2. **Future climate data** from climate models (GCM/RCM outputs)

Results show potential changes in streamflow seasonality and magnitude under different climate scenarios and time horizons.

<!-- ![Projection page](../assets/images/screenshots/projection-config.png) -->

## Prerequisites

Before using projections, you need:

1. **Calibrated parameters**: Export from the Calibration page
2. **Projection data**: Climate model outputs for your catchment (pre-loaded in HOLMES)

!!! note "Projection Data Availability"
    Projection data is catchment-specific. Not all catchments have projection data available.

## Importing Calibration Results

### Step 1: Prepare Calibration

1. Go to the **Calibration** page
2. Calibrate a model for your catchment
3. Click **Export parameters** to save the JSON file

### Step 2: Import to Projection

On the Projection page:

1. Click **Import model parameters**
2. Select your calibration JSON file
3. The calibration details appear in the table

!!! info "Single Calibration"
    Unlike Simulation, the Projection page uses only one calibration at a time. Importing a new calibration replaces the existing one.

### Calibration Results Table

The table displays the imported calibration:

| Field | Description |
|-------|-------------|
| Hydrological model | GR4J, Bucket, etc. |
| Catchment | Must match available projection data |
| Objective | Calibration objective used |
| Transformation | Streamflow transformation |
| Algorithm | Manual or SCE |
| Date start/end | Calibration period |
| Snow model | CemaNeige or none |
| Parameters | Calibrated parameter values |

## Projection Settings

After importing a calibration, configure the projection:

### Climate Model

Select the climate model that provides future climate data:

- Different models have different assumptions and biases
- Multiple models allow uncertainty assessment

### Horizon

Select the future time period:

| Horizon | Description |
|---------|-------------|
| Near-term | Typically 2021-2050 |
| Mid-term | Typically 2041-2070 |
| Long-term | Typically 2071-2100 |

Exact years depend on the available projection data.

### Climate Scenario

Select the emissions scenario (Representative Concentration Pathway):

| Scenario | Description |
|----------|-------------|
| RCP4.5 | Moderate mitigation scenario |
| RCP8.5 | High emissions scenario |

!!! info "Scenarios"
    Different scenarios represent different assumptions about future greenhouse gas emissions:

    - **RCP4.5**: Emissions peak around 2040, then decline
    - **RCP8.5**: Emissions continue rising through 2100

## Running a Projection

1. Import a calibration result
2. Select climate model, horizon, and scenario
3. Click **Run**

A loading indicator shows while the projection runs (this may take longer than calibration/simulation due to the longer time series).

<!-- ![Projection results](../assets/images/screenshots/projection-results.png) -->

## Understanding Results

### Projection Chart

The main chart shows the **mean daily hydrograph** (averaged across all years in the projection period):

- **X-axis**: Day of year (January to December)
- **Y-axis**: Streamflow
- **Light lines**: Individual ensemble members
- **Bold line**: Median across all members

This shows the expected seasonal pattern of streamflow under the selected scenario.

#### Chart Interactions

- **Zoom**: Click and drag to select a time range
- **Reset**: Double-click to return to full year view
- **Legend**: Identifies median vs. member lines

### Results Chart

The dot plot shows summary statistics for each ensemble member:

| Metric | Description |
|--------|-------------|
| **Winter min** | Minimum daily flow in January-March |
| **Spring max** | Maximum daily flow in March-June |
| **Summer min** | Minimum daily flow in May-October |
| **Autumn max** | Maximum daily flow in September-December |
| **Mean** | Annual mean streamflow |

Each dot represents one ensemble member, showing the spread of projections.

## Interpreting Projections

### Ensemble Spread

The spread of ensemble members indicates uncertainty:

- **Narrow spread**: Models agree on the projection
- **Wide spread**: Significant uncertainty in the projection

### Seasonal Changes

Look for changes in:

- **Peak timing**: Has the spring freshet shifted earlier/later?
- **Peak magnitude**: Are floods projected to increase/decrease?
- **Low flow timing**: When do minimum flows occur?
- **Low flow magnitude**: Are droughts projected to worsen?

### Comparing Scenarios

Run projections with different settings to understand:

- **Horizon effect**: How do projections change from near to long term?
- **Scenario effect**: How different is RCP4.5 from RCP8.5?
- **Model effect**: Do different climate models agree?

## Exporting Results

Click **Export data** to save:

1. **Projection timeseries (CSV)**: Daily mean streamflow by month

    ```csv
    date,member_1,member_2,member_3,median,model,horizon,scenario
    2021-01-01,15.2,14.8,16.1,15.2,CanESM2,2041-2070,rcp85
    2021-01-02,14.9,14.5,15.8,14.9,CanESM2,2041-2070,rcp85
    ...
    ```

2. **Projection results (CSV)**: Summary statistics per member

    ```csv
    member,winter_min,spring_max,summer_min,autumn_max,mean
    member_1,5.2,125.3,2.1,45.6,22.4
    member_2,4.8,118.7,1.9,42.3,21.1
    ...
    ```

## Use Cases

### Climate Impact Assessment

Quantify how climate change might affect water resources:

1. Run projections for multiple scenarios (RCP4.5, RCP8.5)
2. Compare to historical observations
3. Identify key changes (timing, magnitude)

### Infrastructure Planning

Inform long-term planning decisions:

1. Run projections for the facility's expected lifetime
2. Consider the range of ensemble projections
3. Design for uncertainty

### Education

Demonstrate climate change impacts on hydrology:

1. Compare near-term to long-term horizons
2. Contrast different emissions scenarios
3. Discuss sources of uncertainty

## Best Practices

### Calibration Quality

Projection reliability depends on calibration quality:

- Use well-calibrated parameters (high NSE/KGE)
- Include snow modeling if appropriate
- Validate on independent period before projecting

### Multiple Projections

Run multiple projections to understand uncertainty:

- Different climate models
- Different scenarios
- Different horizons

### Interpreting Results

Remember that projections are scenarios, not predictions:

- They show possible futures under specific assumptions
- Actual climate will depend on actual emissions
- Use for planning under uncertainty, not as forecasts

## Common Issues

### No Projection Data

If the projection settings don't appear after importing calibration:

- The catchment may not have projection data available
- Try a different catchment with projection data

### Long Run Times

Projections can take longer than calibration:

- Climate model data spans many years
- Multiple ensemble members are processed
- Wait for the loading indicator to complete

### Unexpected Results

If projections seem unrealistic:

- Verify calibration quality first
- Check that the correct catchment was calibrated
- Consider if the model is appropriate for future conditions
