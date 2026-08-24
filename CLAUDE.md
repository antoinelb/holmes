# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

HOLMES v4 (HydrOLogical Modeling Educational Software) is a web-based hydrological modeling tool for teaching operational hydrology, built around the July 19–21 1996 Saguenay flood.
Python backend (Starlette/Uvicorn) with a vanilla JavaScript Elm-architecture frontend; all numerical computation lives in the `holmes-rs` Rust extension (PyO3).

Backend code lives in `src/holmes/`: `app.py` is the entry point, `api/` holds every route, the WebSocket handler (`api/api.py`), its per-domain message handlers (`calibration.py`, `simulation.py`, `projection.py`) and the serialization boundary (`api/utils.py`), `data/` holds data-loading logic, `model.py` wraps the `holmes_rs` models, `experiment.py` runs batch experiments, and `utils/` holds shared helpers.
Frontend code is under `src/holmes/static/`: JavaScript in `scripts/`, CSS in `styles/`, icons in `assets/icons/`, and the main page at `index.html`.
The Rust extension is `src/holmes-rs/` (own changelog, versioning, and CI).
Local data, map tiles, and experiment results live in `data/`, which is gitignored except the MELCC station CSVs — build inputs with no public source, so version control is their only backup (see below).

## Project Constitution

All code changes MUST align with these five core principles:

1. **Code Simplicity and Robustness** - Simple, readable, maintainable and anti-fragile code above all else
2. **Functional Over Object-Oriented** - Pure functions, immutability, composition
3. **Performance First** - Vectorization (NumPy/Polars), Rust via PyO3 for compute-intensive functions
4. **Extensibility by Design** - Plugin architecture, no core modifications
5. **Consistent, Intuitive, and Informative UI** - Clear patterns, feedback, accessibility

## Commands

- `holmes run` / `holmes r` — start the dev server (Uvicorn + Starlette). `holmes` is the console script pointing at `holmes.cli:run_cli` (a Typer app).
- `holmes download` / `holmes d` — build **all** data products from their true sources via `holmes.download.run_download` (maintainer/cron path; needs the `[download]` extra and CDS credentials — `~/.cdsapirc` or `CDSAPI_URL`/`CDSAPI_KEY`). Incremental by design: a daily re-run refetches only the 8 small streamflow files and the current year of era5/ministry-grid (plus the previous year in January, to close the UTC→Montreal Dec 31 boundary), upserts those rows into the products, always recomputes the cheap derived products (completed stations, nearest_stations 1–5, the 3 `grid_*.ipc` map products, the 7 `data_{method}.ipc` joins), and skips the static ones (station_data, projections) unless `--force`.
- `holmes package` / `holmes p` — zip the 45 products into `data-YYYY-MM-DD.zip` (`download.package.build_archive`; `--output PATH` optional). Fails listing every missing product.
- `holmes experiment` / `holmes e` — run the batch experiments in `src/holmes/experiment.py:run_experiment` (calibrate + simulate the hardcoded `Experiment` list).
- `ruff format src/holmes tests` / `ruff check src/holmes tests` — format and lint; treat all warnings as errors.
- `ty check src/holmes tests` — run type checks; treat all warnings as errors.

Makefile shortcuts (preferred):

- `make static-analysis` — ruff + ty on the Python side, `cargo fmt` + `cargo clippy -D warnings` on the Rust side.
- `make test` — full suite: holmes-rs Python-binding tests, Rust unit/integration coverage (`cargo +nightly llvm-cov`), Rust performance tests, then the Python unit+integration suite with coverage.
- `make test-e2e` — Playwright e2e suite (`--browser chromium` lives in that target, not in `addopts`, so plain `pytest` invocations stay decoupled from pytest-playwright).
- `make build-rs` — rebuild the Rust extension (release mode) after changes to `src/holmes-rs`.
- `make cov-rs` — Rust coverage report alone.
- `make package` / `make upload-data` — build the dated zip and push it to the repo's rolling `data` GitHub release (manual bootstrap path; the nightly `data.yml` workflow does the same thing on cron).

The venv is assumed active — never prefix with `uv run` or `.venv/bin/python`.

## Python version

`requires-python = ">=3.12"`; development and `.python-version` use 3.14, and CI tests 3.12 and 3.14.
Do not use 3.13/3.14-only grammar (e.g. PEP 758 parenthesis-free multi-exception `except` — multi-exception clauses here are parenthesized on purpose).
Ruff's lint selection is pinned in `pyproject.toml` to the pre-0.16 default rules the codebase was written against.

## Coding style & naming conventions

Python is formatted with Ruff at a 79-character line length.
Use standard naming — `snake_case` for functions and modules, `PascalCase` for classes — but use `snake_case` rather than uppercase for constants where appropriate.
For data processing use `polars`; do not introduce pandas or pandas-style workflows (`geopandas` is confined to the geometry boundary: reading shapefiles and reprojecting WKB polygons).
Keep code comments in English and concise; comments explain *why*, not *what*.

Both Python and JS modules are split by `#### public ####` / `#### private ####` (Python) or `/* model */ /* update */ /* view */` (JS) banner comments, with callers above callees.

## Backend architecture

Starlette app assembled in `src/holmes/app.py` (`create_app` factory); every route comes from `src/holmes/api/api.py:get_routes`.
`run_server` runs `holmes.data.archive.sync_data()` before `uvicorn.run` (never inside `create_app`: uvicorn installs its own SIGINT handler before calling the factory and that handler only sets a flag, so a Ctrl-C during the first-run download would be swallowed) unless `HOLMES_SKIP_DATA_SYNC` is set: it compares the newest `data-YYYY-MM-DD.zip` asset on the repo's rolling `data` release against the local `data/archive_date.txt` marker, streams + extracts atomically if newer (per-file `os.replace`, old data stays readable throughout), warns and keeps local data if the check fails but data exists, and raises `MissingDataError` if there is no data at all.
`run_server` then opens the default browser from a daemon thread (`_open_browser`, `browser_delay` seconds after uvicorn starts) unless `DEBUG` — a dev reloading does not want a new tab each time — and only warns if no browser exists. The e2e drivers and `capture_screenshots.py` boot `uvicorn holmes.app:create_app --factory` directly, so they never sync and never open a browser.
Config comes from a `.env` file via `src/holmes/config.py` (`DEBUG`, `RELOAD`, `PORT`, `HOST`, `HOLMES_DATA_DIR`, `HOLMES_SKIP_DATA_SYNC`).

Routes are:

- `GET /` — serves `src/holmes/static/index.html`.
- `GET /version` — package version from `importlib.metadata` (distribution `holmes-hydro`).
- `/static` — mounted `StaticFiles`.
- `/ws` — the single WebSocket endpoint (`_websocket`).
- `GET /map/{z}/{x}/{y}.png` — map tiles, cached flat as `data/map/tile_{z}_{x}_{y}.png`; on a miss it downloads from CartoDB (`dark_all`) and caches, returning a 1×1 black PNG on failure.

### WebSocket protocol (`src/holmes/api/api.py`)

`_handle_message` is a `match`/`case` dispatcher on `msg["type"]`: `"stations"`, `"weather"`, `"streamflow"`, `"model_info"`, the `"calibration_*"` family, `"simulation_data"`, `"projection_data"`.
Replies go out via `_send(ws, event, data)` as `{"type": event, "data": …}`, and every payload passes through `convert_for_json`.

Long loads run as tasks tracked in `ws.state.tasks` so `_cleanup_websocket` can cancel them on disconnect.
The two data messages differ deliberately:

- **weather** — a new pick supersedes any pending load (`ws.state.weather_task` is cancelled). The NetCDF work is minutes of synchronous CPU, so it is pushed off the event loop with `asyncio.to_thread`. The reply echoes `method` so a late reply for a superseded pick is identifiable.
- **streamflow** — one request per role, independent and cheap, so none supersedes another. The reply echoes `station` so the client can key its cache.

### Data layer is read-or-fail (`src/holmes/data/`)

The server **never builds data**. Every reader is sync, delegates to `archive.read_product(path)` (`pl.read_ipc(..., memory_map=False)`), and raises `archive.MissingDataError` with actionable guidance when the file is absent — the products come from the release zip via the startup sync. The read layer imports only polars/httpx/stdlib; the heavy geo stack lives in the build layer.

- `archive.py` — `sync_data()`, `read_product()`, `local_archive_date()`, `MissingDataError`; release discovery via the GitHub API (`releases/tags/data`), dated-asset regex, zip-slip-guarded extraction, atomic swap, marker file. The sync narrates itself with the `utils/print` task API (a first run says so explicitly and that the app follows), counts megabytes off `content-length`, and clears staging on `BaseException` so a Ctrl-C strands nothing.
- `hydro.py` — `STATIONS` (8 hardcoded ids), `get_station_data()` (`raw/hydro/station_data.ipc`), `get_streamflow_data(id)` (`raw/hydro/streamflow/{id}.ipc`).
- `weather.py` — `WeatherMethod = Literal["nearest_stations", "era5", "ministry_grid"]`, `read_weather_data(method=, n_stations=)` (`weather/nearest_stations_{n}.ipc` or `weather/{method}.ipc`), `read_weather_grid(method=)` (prebuilt `weather/grid_{...}.ipc` map products — the server needs no rasters).
- `projection.py` — `has_projection_data`, `read_projection_data` (concat of `raw/projection/{id}.ipc`).
- `joined.py` — `read_joined_data(method=, n_stations=)` (`raw/data_{method}[_{n}].ipc`), the calibration warm path (`api/calibration.py` reads it directly; `experiment.read_data` is a thin delegate).

### Build layer (`src/holmes/download/`)

Everything `holmes download`/`holmes package` and the nightly cron use; the only place cdsapi/xarray/rioxarray/exactextract/netcdf4/pystac-client are imported (the `[download]` optional extra — `cli.py` imports the package lazily so `holmes run` stays light). `run_download(force=)` in `__init__.py` runs the ten steps in dependency order: station_data → streamflow → era5 → ministry_grid → backfill → completed → nearest → grids → projections → joins.

Domain knowledge that lives here now:

- `hydro.build_station_data` — stations metadata CSV from `donneesquebec.ca`, watershed polygons from two zipped shapefiles (**CRS matters**: open watersheds `EPSG:4269`, closed `EPSG:32198`, both → `EPSG:4326`; stored once as WKB in `geometry` — the map's GeoJSON is derived per request by `api._for_map`, which already parses that WKB for the centroids), per-watershed DEM from the `mrdem-30` STAC collection clipped in `EPSG:3979` and reduced to band-median elevation layers. `_rename_stations` hardcodes the Pikauba Aval/Amont names the experiments match on. Skip-if-exists.
- `hydro.fetch_streamflow` — CEHQ `_Q.txt` per station (latin-1, regex per row), densified onto a dense daily grid (missing days explicit nulls), m³/s → **mm/day** (`× 86.4 / area` from the file header). Always refetches (full history is the only granularity); fetch failure keeps the old file with a warning, but a missing product raises — the **warn-or-fail rule** every refreshable dataset follows.
- `weather.update_era5` — cell caches are per-cell-per-year `era5/{lat:.2f}_{lon:.2f}_{year}.ipc`; CDS requests stay range-based (one request per cell). Incremental runs refresh `_years_to_refresh` (current year; + previous year in January) and upsert into `era5.ipc` at a Jan-1 cutoff. Three subtle rules: cell centres must be multiples of 0.25° (CDS snaps and relabels), `total_precipitation` is stamped end-of-hour (shift −1h before dating), and hours convert to `America/Montreal` before the daily reduction.
- `weather.update_ministry_grid` — *Grilles climatiques du Québec v3*, one NetCDF per parameter-year (PREC/TMOY only); refresh years are deleted + redownloaded (the current year's file changes at the source), reduced via `exactextract` coverage weights in `EPSG:32198` (intersecting in degrees would over-weight northern cells), gap-filled from the fresh era5 product, upserted.
- `weather.update_stations_backfill` / `rebuild_completed_stations` / `rebuild_nearest_stations` / `rebuild_grids` — the MELCC station CSVs (**the one input that cannot be refetched**: no public source, produced once by `scripts/convert_stations.py` from `.txt` files that no longer exist on disk, so they are committed under `data/raw/weather/stations/*.csv` — the `.gitignore` re-includes exactly that path — as well as shipped in the archive; without them a cold build cannot rebuild the completed stations) are completed column-wise from the backfill (ministry grid at the station's cell, era5 filling what the grids miss — both long-record stations are silent 1994-11→1997-03, so the July 1996 flood weather comes from the backfill); nearest products combine the `n_stations` (1–5) closest stations to each watershed centroid by IDW (`1/d²`); the grid products reuse the exact selection/weighting of the means so map and mean cannot drift. All derived products are always recomputed (cheap).
- `projection.build_projection_data` — ClimEx rcp8.5 (50 members) + ESPO-G6-R2 ssp2-4.5/ssp3-7.0 from PAVICS as raw DAP2 `.dods` slices over httpx (xarray serializes concurrent OPeNDAP; THREDDS can't serve ClimEx); `_parse_dods` validates three ways and a still-failing window **raises** (partial data would surface as the adjacent nulls `model._fill_missing` rejects). Per-member caches are the resume granularity; 2020→2099-12-30, noleap. Skip when all 8 products exist.
- `joined.build_joined_data` — the 7 `data_{method}[_{n}].ipc` joins; `package.archive_manifest`/`build_archive` — the 45-product zip.

All writes (both layers' history): staged `.part` → validate → `replace()`, `compression="zstd"`; reads pass `memory_map=False`.

### The data archive

**Neither the wheel nor the repo ships data products** (the repo does keep the MELCC station CSVs, which are inputs, not products). The single distribution channel is the dated zip (`data-YYYY-MM-DD.zip`, ~240 MB since the 2026-08-16 float32 cast of the projections; products only — no rasters/DEM/shapefiles/cell caches) on the rolling `data` release, produced nightly by `.github/workflows/data.yml` (07:00 UTC; gated on the `DATA_REFRESH_ENABLED` repo variable, manual `workflow_dispatch` always allowed; CDS credentials from the `CDSAPI_KEY` secret; restores the previous zip, runs `holmes download` incrementally, uploads the new zip **then** deletes every other asset). The server consumes it via the startup sync; map tiles are the one remaining lazy fetch (CartoDB).

Paths: `src/holmes/utils/paths.py` resolves `data_dir` from `HOLMES_DATA_DIR` when set (the checkout, tests, and CI set it to `data`), else `platformdirs.user_data_dir("holmes")` (Linux `~/.local/share/holmes`, macOS `~/Library/Application Support/holmes`, Windows `%LOCALAPPDATA%\holmes\holmes`); `results_dir` lives under it and `static_dir` is package-relative. Always build file paths from `utils/paths.py` — new modules import the module (`paths.data_dir`, patchable in one place), the surviving older modules import by value (and stay on the conftest patch list). Projections are noleap (no Feb 29 rows) — fine downstream since `model._prepare_data` only uses the day of year.

### Model layer (`src/holmes/model.py`)

Thin typed wrapper over the `holmes_rs` Rust extension.
`HydroModel` is a 20-member `Literal`, each mapped to `holmes_rs.hydro.<name>.simulate` in `_get_hydro_model`; snow is `cemaneige`, PET is `oudin`, calibration is `sce` (`Sce` driven by a bounded `for _ in range(max_iter)` loop over `.step()`, never `while True`).
Every dispatch ends in `assert_never`, so adding a `Literal` member without a `case` is a type error rather than a silent fallthrough.
`model_info.py` carries per-model display names and `param_descriptions` pulled from `holmes_rs`.

`_prepare_data` holds the two subtle data rules: leap days are remapped (Feb 29 → 28) and all years forced to 2021 because only the day-of-year is used downstream, and `_fill_missing` linearly interpolates single missing values but **raises** if two nulls are ever adjacent.

### Experiments (`src/holmes/experiment.py`)

`run_experiment` iterates a hardcoded list of `Experiment` NamedTuples.
Each is content-addressed: `src/holmes/utils/config.py:hash_config` gives an 8-char sha256 over the sorted config, and results land in `data/results/experiments/<hash>/` alongside a registry in `experiments.json`.
Every stage is skip-if-cached, so re-running is cheap; `hydro_model="all"` fans out over every `HydroModel` with `asyncio.gather`.
`read_data` assembles the station/streamflow/weather join into `data/raw/data_{weather_method}.ipc`.

### Serialization boundary (`src/holmes/api/utils.py`)

`convert_for_json` is the single chokepoint for anything sent to the client.
It recursively converts Polars `DataFrame`→list-of-dicts and replaces both NaN and ±inf with `null`.
Dates and datetimes become **Unix timestamps (seconds)** by default; the frontend rehydrates with `new Date(d.datetime * 1000)`.
Pass `dates_as_str=True` for ISO strings instead (used when writing `experiments.json`).

The `with_*_params` decorator family (`with_json_params`, `with_path_params`, …) extracts request params, returns a 400 `Response` on missing keys, and converts dashes to underscores in kwarg names.

## Frontend architecture (`src/holmes/static/scripts/`)

Vanilla JS, no build step, ES modules, Elm-style **Model-View-Update**.
State changes must be dispatched as messages handled by `update()`, then rendered by `view()` — avoid imperative DOM mutations and global listeners that directly mutate state.
Map rendering is the sanctioned exception: Leaflet and D3 are used together in `steps/stations.js`.

The mechanical contract:

- `index.js` owns a serial async dispatch queue: `dispatch(msg)` enqueues; the queue runs `model = await update(model, msg, dispatch) → view(model, dispatch)` one message at a time. All state lives in one flat `model` object. Because it is serial, a handler can dispatch a follow-up and rely on ordering.
- Messages are **flat, slash-prefixed strings** — `"stations/GotStations"`, `"weather/GetWeather"`, `"settings/ToggleTheme"`. `index.js`'s `default` branch routes on `msg.type.split("/")[0]` to `settings.update` or `pipeline.stepById[prefix].module.update`.
- WebSocket flow: server `_send` → client `ws.js` `onmessage` → `index.js:handleMessage` translates the wire event into a prefixed message. `ws.js` implements reconnect with exponential backoff + a circuit breaker, and `Connected` deliberately clears the weather cache so a request lost while disconnected is retried.
- DOM is built with the `create(type, attrs, children, events)` helper in `utils/elements.js`; `clear`, `createIcon`, `createLoading`, `createCheckbox`, `createSlider` come from the same module.
- The UI is bilingual (`utils/text.js`): every user-facing literal is an inline pair `t(en, fr)`, and `{en, fr}` wire payloads (model/parameter descriptions) are resolved with `pick`. The language lives in `localStorage` under `holmes--settings--language` and only changes via `settings/ToggleLanguage` (hotkey L), which writes the key and reloads — so the module-level `language` const never goes stale and no view invalidation is needed. Chart month names go through the `frenchLocale` in `utils/misc.js`. Model names, station names, and metric acronyms are never translated.
- `utils/plot.js:hydrographView` draws every timeseries chart with D3 (grid + bare tick labels, no spines; line or daily bars; x-axis brush zoom with double-click reset).

### The pipeline engine (`pipeline.js`)

The app is a linear pipeline of steps: stations → weather → model → calibration → simulation → projection.
Each step is a descriptor declaring `uses` and `provides` config keys, plus `map: true` if it wants the shared map.
**Unlocking and staleness are derived from those key lists, never hand-written per step** — `status()` returns `locked`, `available`, `done`, or `stale`.
`autoComplete` snapshots a step the moment every key it `provides` is filled, so per-field validation belongs in the step view before `SetConfig` is dispatched.

Each step module exports `update`, `controlsView`, `canvasView`.
`index.js:view` renders into four fixed shells created once in `initView`: `#canvas`, `#map`, `#sidebar`, `#controls`.
The map div persists across steps and is only toggled hidden, because re-creating a Leaflet map is expensive.

Two idioms recur in the views and both exist for the same reason — **rebuilding a subtree under a click swallows that click**:

- Views compare `element.dataset.step` and only `clear()` + rebuild on an actual step change, then reconcile in place via a `sync*` function.
- Charts store a `dataset.signature` of everything that should force a redraw and skip redrawing otherwise, which also preserves the brush zoom.

Step selection, `config`, and `snapshots` persist to `localStorage` under `holmes--pipeline` (`index.js:persist`); the transient step state never is.

A calibration worth keeping longer than a reload is exported to a JSON file (`calibration.js:exportJson`) and restored with the Import button next to it.
Import shape-validates the file (`validImport`, a trust boundary: enums pinned, params checked finite), diffs its config against the live one behind a native `<dialog>`, then restores the bench with `series: null` — that null is load-bearing: the next `GetSeries` takes its first-load branch, the only one that preserves restored attempts.

### Styles (`src/holmes/static/styles/`)

`index.css` is the only file `index.html` links; it `@import`s `template.css`, `elements.css`, `settings.css`, `map.css`, `pipeline.css`.
Colours go through `oklch(var(--colour))` with named colour classes, so charts and UI share one palette.

## Rust extension (`src/holmes-rs/`)

All performance-critical code: one file per hydro model in `src/hydro/`, CemaNeige in `src/snow/`, Oudin PET in `src/pet/`, SCE-UA and DDS in `src/calibration/`, objective functions in `metrics.rs`, custom exceptions in `errors.rs`.
Python type stubs live in `python/holmes_rs/`.
Rebuild after changes with `make build-rs` (maturin develop, release mode).

Versioned independently (`holmes-rs-X.Y.Z` tags, own `CHANGELOG.md`, own CI in `ci-holmes-rs.yml` publishing wheels to PyPI); the app depends on `holmes-rs>=X.Y.Z` with a `[tool.uv.sources]` editable path override for development.

## Testing

**All modifications MUST include tests and pass before being considered complete.**

- **holmes (Python)**: 100% coverage required, enforced over `tests/unit` + `tests/integration` **combined in a single pytest invocation** (`fail_under = 100`); do not split the suites for coverage runs.
- **holmes-rs Python bindings**: 100% coverage required (`cd src/holmes-rs && pytest tests/python_integration`).
- **holmes-rs Rust code**: minimum 99% coverage (`cargo +nightly llvm-cov`).
- **Frontend**: every functionality covered by a Playwright e2e test.

`make test` runs everything — including the Rust performance tests (160 real-data calibrations) — and is the **final verification only**; during development run the targeted category for what changed.

- `tests/unit/` mirrors `src/holmes/` (classes named `TestFunctionName`, mocking via `unittest.mock`/`monkeypatch` only). `tests/unit/conftest.py` holds the autouse isolation fixtures: `tmp_data_dir` (patches the by-value `data_dir`/`results_dir` imports in **every consuming module**), `no_network` (fails any real httpx request fast) and `_reset_api_state` (fresh module caches **and fresh `asyncio.Lock`s** — the locks remember their first event loop).
- `tests/integration/` drives the full app through `starlette.testclient.TestClient` + `websocket_connect`, with data loaders monkeypatched to the synthetic frames from `tests/conftest.py` but the **real holmes_rs models** running on them (SCE converges in <1 s with `n_complexes=2, max_evaluations=60`; anti-convergence params used by stop tests must always be paired with a stop or disconnect). Supersede tests are gated on `threading.Event` via `asyncio.to_thread` — never `sleep`.
- `tests/conftest.py` holds only lazy (non-autouse) fixtures because it is also in scope for e2e, which needs real network and data. Synthetic data is deterministic (`np.random.default_rng(0)`), 3 full civil years 2015–2017, no adjacent nulls (a `_fill_missing` constraint).
- `tests/e2e/` boots a real uvicorn server and needs a warmed `data/` directory (CI downloads the newest `data-*.zip` from the `data` release, unzips it, and writes `data/archive_date.txt` so the startup sync no-ops; locally, run the app once — the sync fetches the same zip). Map tiles are fetched lazily from CartoDB during the run.
- Targeted coverage checks must use `--cov=src/holmes` (a path), never a dotted module name: coverage imports dotted sources to locate them and the re-import can trip PyO3 single-init guards in compiled dependencies.
- `pragma: no cover` is reserved for statically unreachable `assert_never` arms and the shared `send` catch-all; everything else is exercised.

## Documentation

- Main documentation is in `docs/` and uses MkDocs Material (awesome-nav for navigation; `docs/concepts/hydro/` is auto-navigated by glob).
- The docs are bilingual via `mkdocs-static-i18n` in suffix mode: every page has a `.fr.md` sibling, nav titles are translated through `nav_translations` in `mkdocs.yml`, and a page without a `.fr.md` sibling falls back to English under `/fr/`. `theme.features` deliberately omits `navigation.instant`, which breaks the language switcher's contextual links.
- `docs/concepts/` documents the holmes-rs models, calibration algorithms, and metrics.
- `docs/guide/` is the user guide: one page per pipeline step plus an interface tour (`index.md`) and task-oriented recipes (`workflows.md`). Screenshots are embedded as `<scene>-{dark,light}.png` pairs (English pages) and `<scene>-fr-{dark,light}.png` pairs (French pages) with Material's `#only-dark`/`#only-light` fragments.
- `make screenshots` regenerates every screenshot in `docs/assets/images/screenshots/`: `scripts/capture_screenshots.py` boots the real server and walks the pipeline once per language (French set through localStorage) via the shared Playwright drivers in `tests/e2e/drivers.py` (also used by the e2e tests). Needs a warmed `data/`. Adding a UI feature means adding/refreshing its scene there and referencing the pair in the guide.

## Configuration

Environment variables via `.env`:
- `DEBUG=True` - Enable debug mode
- `RELOAD=True` - Auto-reload on code changes
- `HOST=127.0.0.1` - Server host
- `PORT=8000` - Server port

## Commit & pull request guidelines

History uses short, imperative commit messages (e.g. `Added legend`, `Added station markers`).
Keep commits focused and describe the user-visible change or internal behavior.
