# Observations CSV

Daily hydrometeorological observation data for a catchment.

## File Naming

```
<Catchment>_Observations.csv
```

Example: `Au Saumon_Observations.csv`

## Format

Standard CSV with header row. Date format must be `YYYY-MM-DD`.

### Required Columns

| Column | Description | Units |
|--------|-------------|-------|
| `Date` | Observation date | YYYY-MM-DD |
| `P` | Precipitation | mm/day |
| `E0` | Potential evapotranspiration | mm/day |
| `Qo` | Observed streamflow | mm/day |

### Optional Columns

| Column | Description | Units | Required For |
|--------|-------------|-------|--------------|
| `T` | Mean daily temperature | °C | Snow modeling (CemaNeige) |

## Example

```csv
Date,P,E0,Qo,T
1975-03-01,7.67,0.102,0.63,-3.75
1975-03-02,2.26,0.0,0.58,-5.7
1975-03-03,13.69,0.0,0.54,-7.2
1975-03-04,0.0,0.0,0.49,-10.56
```

## Notes

- All values should be in consistent units (mm/day for water fluxes)
- Missing temperature data disables snow modeling for the catchment
- The available date range is automatically detected from the file
- A warmup period (default 3 years) is used before the analysis period
