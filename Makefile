all: ci

lint:
	ruff check
	mypy universalasync

checkformat:
	ruff format --check

format:
	ruff format

test:
	pytest tests/ ${TEST_ARGS}
	@coverage combine > /dev/null 2>&1 || true

ci: checkformat lint test
