static-analysis:
	black src tests
	ruff check src tests
	ty check src tests

test:
	pytest --cov --cov-report term-missing

publish:
	uv build && uv publish
