# HOOPLA Hydrological Models — Lookup Table

Static index mapping every HOOPLA hydrological model to its HM folder number, parameter count, raw Matlab source URLs, and current HOLMES implementation status.
Used by the `add-hydro-model` skill so it does not have to rediscover the HOOPLA naming on every invocation.

**Source:** <https://github.com/AntoineThiboult/HOOPLA/tree/master/Tools/HydroModels>
**Reference:** Thiboult, A., Seiller, G., Poncelet, C., Anctil, F. (2020). *The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory*, HESS Discussions.
**Authoritative equations:** `perrin/these_annexe.pdf`, Annexe 1 "Description des modèles" (starting ~page 291).

Every HOOPLA model ships two Matlab files in its `HMn/` folder:

- `ini_HydroModN.m` — state initialization (reservoir defaults, unit-hydrograph setup, delay arrays).
- `HydroModN.m` — single time-step function. **This is the file with the human-readable model name in its header comment** and the production/routing equations.

## Models

| #  | Model      | Params | Status         | HOOPLA step file                                                                                              | HOOPLA init file                                                                                                  |
|----|------------|--------|----------------|----------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| 1  | BUCKET     | 6      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM1/HydroMod1.m>            | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM1/ini_HydroMod1.m>           |
| 2  | CEQUEAU    | 9      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM2/HydroMod2.m>            | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM2/ini_HydroMod2.m>           |
| 3  | CREC       | 6      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM3/HydroMod3.m>            | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM3/ini_HydroMod3.m>           |
| 4  | GARDENIA   | 6      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM4/HydroMod4.m>            | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM4/ini_HydroMod4.m>           |
| 5  | GR4H       | 4      | Implemented as GR4J † | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM5/HydroMod5.m>     | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM5/ini_HydroMod5.m>           |
| 6  | HBV        | 9      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM6/HydroMod6.m>            | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM6/ini_HydroMod6.m>           |
| 7  | HYMOD      | 6      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM7/HydroMod7.m>            | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM7/ini_HydroMod7.m>           |
| 8  | IHACRES    | 7      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM8/HydroMod8.m>            | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM8/ini_HydroMod8.m>           |
| 9  | MARTINE    | 7      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM9/HydroMod9.m>            | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM9/ini_HydroMod9.m>           |
| 10 | MOHYSE     | 7      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM10/HydroMod10.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM10/ini_HydroMod10.m>         |
| 11 | MORDOR     | 6      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM11/HydroMod11.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM11/ini_HydroMod11.m>         |
| 12 | NAM        | 10     | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM12/HydroMod12.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM12/ini_HydroMod12.m>         |
| 13 | PDM        | 8      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM13/HydroMod13.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM13/ini_HydroMod13.m>         |
| 14 | SACRAMENTO | 9      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM14/HydroMod14.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM14/ini_HydroMod14.m>         |
| 15 | SIMHYD     | 8      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM15/HydroMod15.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM15/ini_HydroMod15.m>         |
| 16 | SMAR       | 8      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM16/HydroMod16.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM16/ini_HydroMod16.m>         |
| 17 | TANK       | 7      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM17/HydroMod17.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM17/ini_HydroMod17.m>         |
| 18 | TOPMODEL   | 7 ‡    | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM18/HydroMod18.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM18/ini_HydroMod18.m>         |
| 19 | WAGENINGEN | 8 ‡    | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM19/HydroMod19.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM19/ini_HydroMod19.m>         |
| 20 | XINANJIANG | 8      | Implemented    | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM20/HydroMod20.m>          | <https://raw.githubusercontent.com/AntoineThiboult/HOOPLA/master/Tools/HydroModels/HM20/ini_HydroMod20.m>         |

### Footnotes

† **GR4J vs GR4H.** HOOPLA's HM5 is GR4H (hourly four-parameter model). HOLMES implements the daily variant GR4J (`src/holmes-rs/src/hydro/gr4j.rs`) with the same four-parameter structure (`x1`..`x4`). The equations are equivalent; only the time step and `x4` bounds differ.

‡ **Parameter-count typos in HOOPLA headers.** The HOOPLA comment blocks for HM18 and HM19 say "ten parameters" in free text but declare `[7,1]` and `[8,1]` respectively in the parameter-block size. The array dimension is authoritative — use 7 for TOPMODEL and 8 for WAGENINGEN. Cross-check against Perrin's thesis annex before implementing.

## How to use this file

1. User requests a new model (e.g. HYMOD). The skill presents the "To implement" rows above as an `AskUserQuestion` option list.
2. On selection, the skill reads the corresponding row to get the HM number, expected parameter count, and the two raw URLs.
3. The skill `WebFetch`es both URLs to inspect the Matlab source, then cross-checks against `perrin/these_annexe.pdf` Annexe 1.
4. The skill writes the Rust module following `src/holmes-rs/src/hydro/gardenia.rs` as a template, then follows the 11-file checklist in `SKILL.md`.

## Maintenance

Update the **Status** column of a row from "To implement" to "Implemented" after a model has been successfully added to HOLMES (after `make test` passes).
Do not edit any other column — the HM numbering and raw URLs are frozen upstream.
