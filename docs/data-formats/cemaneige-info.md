# CemaNeige Info

Configuration file for the CemaNeige snow model. Required when using snow modeling.

## File Naming

```
<Catchment>_CemaNeigeInfo.csv
```

Example: `Au Saumon_CemaNeigeInfo.csv`

## Format

Key-value pairs in CSV format (no header row).

### Required Keys

| Key | Description | Units |
|-----|-------------|-------|
| `QNBV` | Mean annual solid precipitation | mm/year |
| `AltiBand` | Altitude band boundaries | m (semicolon-separated) |
| `Z50` | Median catchment altitude | m |
| `Lat` | Catchment latitude | degrees |

## Example

```csv
QNBV,354.9
AltiBand,379;433;474;532;672
Z50,474
Lat,45.482
```

## Notes

- `AltiBand` values define the boundaries of elevation bands, separated by semicolons
- The number of altitude layers is determined by the number of values in `AltiBand`
- `QNBV` (Quantité de Neige du Bassin Versant) represents average annual snowfall
- `Z50` is the median elevation, used for temperature lapse rate calculations
- `Lat` (latitude) is used for day length calculations in the snow model
