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

screenshots:
	playwright install chromium
	python scripts/capture_screenshots.py
	command -v optipng > /dev/null \
		&& optipng -o2 -quiet docs/assets/images/screenshots/*.png \
		|| true

build-rs:
	uv run maturin develop --manifest-path src/holmes-rs/Cargo.toml --release

cov-rs:
	cargo +nightly llvm-cov --manifest-path src/holmes-rs/Cargo.toml --test unit --test integration --ignore-filename-regex '(lib\.rs|/mod\.rs|utils\.rs)$$'

package:
	holmes package

upload-data: package
	gh release view data > /dev/null 2>&1 || gh release create data \
		--title "Data assets" --notes "Prebuilt data archive (holmes package)."
	gh release upload data data-$$(date -u +%F).zip --clobber
