#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 PROJECT_ZIP [PROJECT_DIR]" >&2
  echo "Example: $0 ~/Downloads/copyspace-guard-materials.zip ~/work/copyspace-guard" >&2
  exit 1
fi

ZIP_PATH="$1"
PROJECT_DIR="${2:-$HOME/work/copyspace-guard}"
PRESERVE_ARTIFACTS="${PRESERVE_ARTIFACTS:-1}"
PRESERVE_VENV="${PRESERVE_VENV:-1}"

if [ ! -f "$ZIP_PATH" ]; then
  echo "ERROR: zip not found: $ZIP_PATH" >&2
  exit 1
fi

for cmd in unzip rsync python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    echo "Install it, for example: sudo apt install unzip rsync python3-venv" >&2
    exit 1
  fi
done

TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

UNZIP_DIR="$TMP_DIR/unzip"
mkdir -p "$UNZIP_DIR"
unzip -q "$ZIP_PATH" -d "$UNZIP_DIR"

if [ -d "$UNZIP_DIR/copyspace-guard" ]; then
  SRC_DIR="$UNZIP_DIR/copyspace-guard"
else
  # If archive has a single top-level directory, use it. Otherwise use root.
  mapfile -t DIRS < <(find "$UNZIP_DIR" -mindepth 1 -maxdepth 1 -type d | sort)
  mapfile -t FILES < <(find "$UNZIP_DIR" -mindepth 1 -maxdepth 1 -type f | sort)
  if [ "${#DIRS[@]}" -eq 1 ] && [ "${#FILES[@]}" -eq 0 ]; then
    SRC_DIR="${DIRS[0]}"
  else
    SRC_DIR="$UNZIP_DIR"
  fi
fi

if [ ! -f "$SRC_DIR/pyproject.toml" ] && [ ! -d "$SRC_DIR/src/copyspace_guard" ]; then
  echo "ERROR: could not find Copy-Space Guard project inside zip" >&2
  echo "Detected source: $SRC_DIR" >&2
  exit 1
fi

mkdir -p "$(dirname "$PROJECT_DIR")"
if [ -d "$PROJECT_DIR" ]; then
  BACKUP_DIR="${PROJECT_DIR}.backup.$(date +%Y%m%d-%H%M%S)"
  echo "Creating backup: $BACKUP_DIR"
  cp -a "$PROJECT_DIR" "$BACKUP_DIR"
else
  mkdir -p "$PROJECT_DIR"
fi

EXCLUDES=()
if [ "$PRESERVE_VENV" = "1" ]; then
  EXCLUDES+=(--exclude '.venv/')
fi
if [ "$PRESERVE_ARTIFACTS" = "1" ]; then
  EXCLUDES+=(--exclude 'artifacts/')
fi

rsync -a --delete "${EXCLUDES[@]}" "$SRC_DIR"/ "$PROJECT_DIR"/

cd "$PROJECT_DIR"
if [ ! -d .venv ]; then
  echo "Creating virtualenv: $PROJECT_DIR/.venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip >/dev/null
python -m pip install -e .
copyspace-guard --help >/dev/null

echo "Update complete: $PROJECT_DIR"
echo "Try:"
echo "  cd $PROJECT_DIR"
echo "  source .venv/bin/activate"
echo "  copyspace-guard analyze --csv examples/ring15.csv --bw 256 --roi examples/roi.yml --outdir artifacts/demo"
