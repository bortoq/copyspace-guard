#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 PROJECT_ZIP [PROJECT_DIR]" >&2
  exit 1
fi

ZIP_PATH="$1"
PROJECT_DIR="${2:-$HOME/work/copyspace-guard}"

if [ ! -f "$ZIP_PATH" ]; then
  echo "ERROR: zip not found: $ZIP_PATH" >&2
  exit 1
fi

for cmd in unzip python3 tar; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: missing $cmd" >&2; exit 1; }
done

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
unzip -q "$ZIP_PATH" -d "$TMP_DIR/unzip"

if [ -d "$TMP_DIR/unzip/copyspace-guard" ]; then
  SRC_DIR="$TMP_DIR/unzip/copyspace-guard"
else
  SRC_DIR="$TMP_DIR/unzip"
fi

[ -f "$SRC_DIR/pyproject.toml" ] || { echo "ERROR: pyproject.toml not found in archive" >&2; exit 1; }
mkdir -p "$PROJECT_DIR"

BACKUP_ROOT="$(dirname "$PROJECT_DIR")/.copyspace-guard-backups"
mkdir -p "$BACKUP_ROOT"
BACKUP_FILE="$BACKUP_ROOT/copyspace-guard.$(date +%Y%m%d-%H%M%S).tgz"
if [ -d "$PROJECT_DIR" ]; then
  tar --exclude='.git' --exclude='.venv' --exclude='artifacts' -czf "$BACKUP_FILE" -C "$PROJECT_DIR" .
  echo "Backup: $BACKUP_FILE"
fi

python3 - "$SRC_DIR" "$PROJECT_DIR" <<'PY'
import os, shutil, sys
from pathlib import Path
src=Path(sys.argv[1]); dst=Path(sys.argv[2])
preserve={'.git','.venv','artifacts'}
for p in list(dst.iterdir()):
    if p.name in preserve: continue
    shutil.rmtree(p) if p.is_dir() else p.unlink()
for root, dirs, files in os.walk(src):
    rootp=Path(root); rel=rootp.relative_to(src)
    dirs[:] = [d for d in dirs if d not in preserve and d != '__pycache__' and not d.endswith('.egg-info')]
    (dst/rel).mkdir(parents=True, exist_ok=True)
    for f in files:
        if f.endswith(('.pyc','.pyo')): continue
        shutil.copy2(rootp/f, dst/rel/f)
PY

cd "$PROJECT_DIR"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
copyspace-guard --help >/dev/null

echo "Update complete: $PROJECT_DIR"
