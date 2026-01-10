static-analysis:
	black src/holmes
	ruff check src/holmes
	ty check src/holmes
	cargo fmt --manifest-path src/holmes-rs/Cargo.toml
	cargo clippy --manifest-path src/holmes-rs/Cargo.toml --all-targets --all-features -- -D warnings

build-rs:
	uv run maturin develop --manifest-path src/holmes-rs/Cargo.toml --release

cov-rs:
	cargo +nightly llvm-cov --manifest-path src/holmes-rs/Cargo.toml
