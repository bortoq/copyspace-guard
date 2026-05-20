.PHONY: demo test docker-build build bench

demo:
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --outdir artifacts/demo

test:
	python -m ruff check --no-cache .
	PYTHONPYCACHEPREFIX=/tmp/copyspace-guard-pycache python -m compileall -q src tests
	python -m unittest discover -s tests -v
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --summary-only --outdir artifacts/demo
	copyspace-guard gate artifacts/demo/summary.json --config examples/copyspace_guard.yml

bench:
	copyspace-guard bench --slots 64 --bits-per-edge 1048576 --bw 1048576 --outdir artifacts/bench

build:
	python -m pip install -e ".[dev]"
	python -m build --no-isolation

docker-build:
	docker build -t copyspace-guard .
