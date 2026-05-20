.PHONY: demo test pilot-check docker-build build bench

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
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --summary-only --outdir /tmp/copyspace-guard-pilot
	copyspace-guard validate-artifact --kind summary /tmp/copyspace-guard-pilot/summary.json
	copyspace-guard gate /tmp/copyspace-guard-pilot/summary.json --config examples/copyspace_guard.yml

bench:
	copyspace-guard bench --slots 64 --bits-per-edge 1048576 --bw 1048576 --outdir artifacts/bench

build:
	python -m pip install -e ".[dev]"
	python -m pip install --upgrade "setuptools>=77" wheel
	python -m build --no-isolation

docker-build:
	docker build -t copyspace-guard .
