static-analysis:
	black src/holmes
	ruff check src/holmes
	ty check src/holmes

build-rs:
	uv run maturin develop --manifest-path src/holmes-rs/Cargo.toml --release
