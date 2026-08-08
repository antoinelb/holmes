# Test Fixtures

This directory contains pre-generated test data files for integration tests.

## Files

### observations_normal.csv
A month of synthetic hydrological observations with varying precipitation, temperature, PET, and streamflow. Used for standard model testing.

### observations_constant.csv
Observations where all streamflow values are identical (5.0). Used specifically for testing edge cases like NSE with zero variance in observations (division by zero).

### observations_au_saumon.csv / observations_baskatong.csv
Raw daily observations for the Au Saumon (1975-2003) and Baskatong (1980-2017)
catchments, copied verbatim from `src/holmes/data/<name>_Observations.csv`
(columns `Date,P,E0,Qo,T`). Used by the performance tests to verify that every
hydro model calibrates to a good KGE on real data.

### cemaneige_info_au_saumon.csv / cemaneige_info_baskatong.csv
CemaNeige catchment metadata (`QNBV`, `AltiBand` `;`-separated elevation bands,
`Z50` median elevation, `Lat`), copied verbatim from
`src/holmes/data/<name>_CemaNeigeInfo.csv`.

### calibration_scenario.json
A calibration test scenario specifying:
- `hydro_model`: The hydrological model to use
- `snow_model`: Optional snow model (null if not used)
- `expected_nse`: Target NSE value for the calibration
- `tolerance`: Acceptable deviation from expected NSE

## Usage

Load fixtures using the `fixtures` module:

```rust
use crate::common::fixtures::{fixtures_dir, load_observations, load_calibration_scenario};

let path = fixtures_dir().join("observations_normal.csv");
let records = load_observations(&path)?;
```
