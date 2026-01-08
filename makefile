static-analysis:
	black src tests
	ruff check src tests
	ty check src tests

test:
	pytest --cov --cov-report term-missing

publish:
	rm -r dist && uv build && uv publish

build-rs:
	uv run maturin develop --manifest-path src/holmes-rs/Cargo.toml --release
