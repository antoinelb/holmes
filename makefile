static-analysis:
	black src/holmes tests
	ruff check src/holmes tests
	ty check src/holmes tests
	cargo fmt --manifest-path src/holmes-rs/Cargo.toml
	cargo clippy --manifest-path src/holmes-rs/Cargo.toml --all-targets --all-features -- -D warnings

test:
	cd src/holmes-rs && pytest --cov
	cargo +nightly llvm-cov --manifest-path src/holmes-rs/Cargo.toml
	pytest tests/unit --cov
	pytest tests/integration
	pytest tests/e2e

build-rs:
	uv run maturin develop --manifest-path src/holmes-rs/Cargo.toml --release

cov-rs:
	cargo +nightly llvm-cov --manifest-path src/holmes-rs/Cargo.toml
