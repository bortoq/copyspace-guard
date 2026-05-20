#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
python -m pip install -e . >/dev/null
copyspace-guard analyze \
  --csv client-package/sample_demands.csv \
  --bw 256 \
  --current-schedule-csv client-package/sample_schedule.csv \
  --roi client-package/roi.yml \
  --outdir artifacts/client-demo
copyspace-guard gate artifacts/client-demo/summary.json --config client-package/copyspace_guard.yml
printf '\nOpen artifacts/client-demo/report.html\n'
