.PHONY: demo test test-fast test-full property security release-guard bump-version pilot-check wheel-smoke release-artifacts release-check clean docker-build build bench bench-suite production-check dev-setup prepare-artifacts

PYTHON ?= python3
ARTIFACTS_DIR := artifacts
PYTHONPYCACHEPREFIX := $(ARTIFACTS_DIR)/pycache
COVERAGE_FILE := $(ARTIFACTS_DIR)/.coverage
TEST_DEMO_OUT := $(ARTIFACTS_DIR)/test-demo
PILOT_OUT := $(ARTIFACTS_DIR)/pilot
WHEEL_SMOKE_VENV := $(ARTIFACTS_DIR)/wheel-smoke-venv
WHEEL_SMOKE_OUT := $(WHEEL_SMOKE_VENV)/out
FAST_TEST_MODULES := tests.test_bounds_edge tests.test_cli tests.test_core tests.test_coverage_expansion tests.test_importers
export PYTHONPYCACHEPREFIX
export COVERAGE_FILE

ifeq ($(OS),Windows_NT)
VENV_BIN_DIR := Scripts
else
VENV_BIN_DIR := bin
endif

WHEEL_SMOKE_PYTHON := $(WHEEL_SMOKE_VENV)/$(VENV_BIN_DIR)/python

prepare-artifacts:
	$(PYTHON) -c "from pathlib import Path; Path('$(ARTIFACTS_DIR)').mkdir(exist_ok=True)"

demo:
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --outdir artifacts/demo

test: test-full

test-fast: prepare-artifacts
	$(PYTHON) -m ruff check --no-cache .
	$(PYTHON) -m mypy src
	$(PYTHON) -m compileall -q src tests
	$(PYTHON) -m coverage run -m unittest $(FAST_TEST_MODULES) -v
	$(PYTHON) -m coverage report --fail-under=80
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --summary-only --outdir $(TEST_DEMO_OUT)
	copyspace-guard gate $(TEST_DEMO_OUT)/summary.json --config examples/copyspace_guard.yml

property:
	$(PYTHON) -m unittest tests.test_property -v

test-full: test-fast property

dev-setup:
	$(PYTHON) -m pip install -e ".[dev]"

security:
	$(PYTHON) -m bandit -q -r src tools
	$(PYTHON) -m pip_audit --progress-spinner off

release-guard:
	$(PYTHON) tools/release_version.py check --tag "$${TAG:-}"

bump-version:
	@test -n "$${VERSION}" || (echo "usage: VERSION=0.2.3 make bump-version" >&2; exit 2)
	$(PYTHON) tools/release_version.py bump "$${VERSION}" $${NOTE:+--note "$${NOTE}"}

pilot-check: prepare-artifacts
	copyspace-guard doctor --root .
	copyspace-guard doctor --root . --json
	copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --summary-only --outdir $(PILOT_OUT)
	copyspace-guard validate-artifact --kind summary $(PILOT_OUT)/summary.json
	copyspace-guard gate $(PILOT_OUT)/summary.json --config examples/copyspace_guard.yml

bench:
	copyspace-guard bench --slots 64 --bits-per-edge 1048576 --bw 1048576 --outdir artifacts/bench

bench-suite:
	copyspace-guard bench-suite --outdir artifacts/bench-suite --max-total-seconds 30

production-check: release-check bench-suite

build:
	$(PYTHON) -m build --no-isolation

wheel-smoke: prepare-artifacts
	$(PYTHON) -c "from pathlib import Path; import shutil; shutil.rmtree(Path('$(WHEEL_SMOKE_VENV)'), ignore_errors=True)"
	$(PYTHON) -m venv $(WHEEL_SMOKE_VENV)
	$(WHEEL_SMOKE_PYTHON) -m pip install --upgrade pip
	$(WHEEL_SMOKE_PYTHON) -m pip install --no-index --find-links dist copyspace-guard
	$(WHEEL_SMOKE_PYTHON) -m copyspace_guard.cli --version
	$(WHEEL_SMOKE_PYTHON) -m copyspace_guard.cli analyze --csv examples/ring15.csv --bw 256 --summary-only --outdir $(WHEEL_SMOKE_OUT)

release-artifacts:
	$(PYTHON) -m twine check dist/*
	$(PYTHON) tools/release_artifacts.py --dist dist --out dist

release-check: clean test pilot-check build wheel-smoke release-artifacts

clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(Path(p), ignore_errors=True) for p in ('build', 'dist', '.mypy_cache', '.ruff_cache')]; [shutil.rmtree(path, ignore_errors=True) for path in Path('src').glob('*.egg-info')]; shutil.rmtree(Path('src/copyspace_guard.egg-info'), ignore_errors=True)"
	$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for root in ('src', 'tests') for path in Path(root).rglob('__pycache__')]"

docker-build:
	docker build -t copyspace-guard .
