static-analysis:
	ruff format src/holmes tests
	ruff check src/holmes tests
	ty check src/holmes tests
	cargo fmt --manifest-path src/holmes-rs/Cargo.toml
	cargo clippy --manifest-path src/holmes-rs/Cargo.toml --all-targets --all-features -- -D warnings

test:
	cd src/holmes-rs && pytest --cov
	cargo +nightly llvm-cov --manifest-path src/holmes-rs/Cargo.toml --test unit --test integration --ignore-filename-regex '(lib\.rs|/mod\.rs|utils\.rs)$$'
	cargo test --manifest-path src/holmes-rs/Cargo.toml --test performance
	pytest tests/unit tests/integration --cov=src/holmes --cov-report=term-missing

test-e2e:
	pytest tests/e2e --browser chromium

build-rs:
	uv run maturin develop --manifest-path src/holmes-rs/Cargo.toml --release

cov-rs:
	cargo +nightly llvm-cov --manifest-path src/holmes-rs/Cargo.toml --test unit --test integration --ignore-filename-regex '(lib\.rs|/mod\.rs|utils\.rs)$$'

upload-assets:
	gh release view data > /dev/null 2>&1 || gh release create data \
		--title "Data assets" \
		--notes "Prebuilt projection products for fresh installs."
	gh release upload data data/raw/projection/*.ipc \
		data/raw/weather/era5.ipc --clobber
	tar czf data-cache.tar.gz \
		data/map \
		data/raw/data_era5.ipc \
		data/raw/data_ministry_grid.ipc \
		data/raw/data_nearest_stations_3.ipc \
		data/raw/hydro/station_data.ipc \
		data/raw/hydro/stations.ipc \
		data/raw/hydro/streamflow_data.ipc \
		data/raw/hydro/streamflow \
		data/raw/hydro/watersheds/watersheds.ipc \
		data/raw/weather/ministry_grid.ipc \
		data/raw/weather/nearest_stations_2.ipc \
		data/raw/weather/nearest_stations_3.ipc \
		data/raw/weather/nearest_stations_4.ipc
	gh release upload data data-cache.tar.gz --clobber
	rm data-cache.tar.gz
