.PHONY: demo test pilot-check wheel-smoke release-artifacts release-check clean docker-build build bench bench-suite production-check

demo:
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --outdir artifacts/demo

test:
	python -m ruff check --no-cache .
	python -m mypy src
	PYTHONPYCACHEPREFIX=/tmp/copyspace-guard-pycache python -m compileall -q src tests
	COVERAGE_FILE=/tmp/copyspace-guard.coverage python -m coverage run -m unittest discover -s tests -v
	COVERAGE_FILE=/tmp/copyspace-guard.coverage python -m coverage report --fail-under=80
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --summary-only --outdir /tmp/copyspace-guard-demo
	copyspace-guard gate /tmp/copyspace-guard-demo/summary.json --config examples/copyspace_guard.yml

pilot-check:
	copyspace-guard doctor --root .
	copyspace-guard doctor --root . --json
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --summary-only --outdir /tmp/copyspace-guard-pilot
	copyspace-guard validate-artifact --kind summary /tmp/copyspace-guard-pilot/summary.json
	copyspace-guard gate /tmp/copyspace-guard-pilot/summary.json --config examples/copyspace_guard.yml

bench:
	copyspace-guard bench --slots 64 --bits-per-edge 1048576 --bw 1048576 --outdir artifacts/bench

bench-suite:
	copyspace-guard bench-suite --outdir artifacts/bench-suite --max-total-seconds 30

production-check: release-check bench-suite

build:
	python -m pip install -e ".[dev]"
	python -m pip install --upgrade "setuptools>=77" wheel
	python -m build --no-isolation

wheel-smoke:
	rm -rf /tmp/copyspace-guard-wheel-smoke
	python -m venv /tmp/copyspace-guard-wheel-smoke
	/tmp/copyspace-guard-wheel-smoke/bin/python -m pip install --upgrade pip
	/tmp/copyspace-guard-wheel-smoke/bin/python -m pip install dist/*.whl
	/tmp/copyspace-guard-wheel-smoke/bin/copyspace-guard --version
	/tmp/copyspace-guard-wheel-smoke/bin/copyspace-guard analyze --csv examples/ring15.csv --bw 256 --summary-only --outdir /tmp/copyspace-guard-wheel-smoke/out

release-artifacts:
	python -m twine check dist/*
	python tools/release_artifacts.py --dist dist --out dist

release-check: clean test pilot-check build wheel-smoke release-artifacts

clean:
	rm -rf build dist src/*.egg-info src/copyspace_guard.egg-info .mypy_cache .ruff_cache
	find src tests -type d -name __pycache__ -prune -exec rm -rf {} +

docker-build:
	docker build -t copyspace-guard .
