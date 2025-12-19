static-analysis:
	black src tests
	ruff check src tests
	ty check src tests

publish:
	uv build && uv publish
