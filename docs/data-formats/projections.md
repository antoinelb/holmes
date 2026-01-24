# Projections CSV

Climate projection data for future scenario analysis.

## File Naming

```
<Catchment>_Projections.csv
```

Example: `Au Saumon_Projections.csv`

## Format

Standard CSV with header row. Contains multiple ensemble members, scenarios, and time horizons.

### Required Columns

| Column | Description | Units/Values |
|--------|-------------|--------------|
| `date` | Projection date | YYYY-MM-DD |
| `precipitation` | Daily precipitation | mm/day |
| `temperature` | Mean daily temperature | °C |
| `member` | Ensemble member number | integer |
| `scenario` | Climate scenario | e.g., `REF`, `RCP45`, `RCP85` |
| `model` | Climate model name | e.g., `CSI`, `CRCM5` |
| `horizon` | Time horizon | e.g., `REF`, `2050`, `2080` |

## Example

```csv
date,precipitation,temperature,member,scenario,model,horizon
1968-01-02,1.047,-4.488,10,REF,CSI,REF
1968-01-03,2.061,-5.056,10,REF,CSI,REF
1968-01-04,1.416,-14.492,10,REF,CSI,REF
1968-01-05,0.352,-15.485,10,REF,CSI,REF
```

## Notes

- The `REF` scenario/horizon typically represents the reference (historical) period
- Multiple ensemble members allow uncertainty quantification
- The projection page filters data by model, scenario, and horizon selections
- PET is calculated internally using the Oudin method from temperature and latitude
