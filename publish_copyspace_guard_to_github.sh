#!/usr/bin/env bash
set -euo pipefail

# Publish local Copy-Space Guard project to GitHub.
#
# Defaults:
#   PROJECT_DIR=$HOME/work/copyspace-guard
#   REPO_NAME=copyspace-guard
#   VISIBILITY=private
#
# Examples:
#   bash publish_copyspace_guard_to_github.sh
#   VISIBILITY=public bash publish_copyspace_guard_to_github.sh
#   GITHUB_OWNER=my-org REPO_NAME=copyspace-guard-enterprise bash publish_copyspace_guard_to_github.sh

PROJECT_DIR="${PROJECT_DIR:-$HOME/work/copyspace-guard}"
REPO_NAME="${REPO_NAME:-copyspace-guard}"
VISIBILITY="${VISIBILITY:-private}"   # private | public | internal
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
DESCRIPTION="${DESCRIPTION:-Copy-Space Guard — deterministic data-movement audit MVP}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
RUN_SMOKE="${RUN_SMOKE:-1}"
USE_SSH="${USE_SSH:-0}"
OPEN_BROWSER="${OPEN_BROWSER:-0}"
COMMIT_MSG="${COMMIT_MSG:-Initial Copy-Space Guard MVP}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"; }

need git
need python3
need gh

[ -d "$PROJECT_DIR" ] || fail "project dir not found: $PROJECT_DIR"
[ -f "$PROJECT_DIR/pyproject.toml" ] || fail "pyproject.toml not found in: $PROJECT_DIR"
[ -d "$PROJECT_DIR/src/copyspace_guard" ] || fail "src/copyspace_guard not found in: $PROJECT_DIR"

log "Checking GitHub CLI auth"
gh auth status >/dev/null || fail "GitHub CLI is not authenticated. Run: gh auth login"
gh auth setup-git >/dev/null 2>&1 || true

if [ -z "$GITHUB_OWNER" ]; then
  GITHUB_OWNER="$(gh api user --jq .login)"
fi
FULL_REPO="$GITHUB_OWNER/$REPO_NAME"

case "$VISIBILITY" in
  private) VIS_FLAG=(--private) ;;
  public) VIS_FLAG=(--public) ;;
  internal) VIS_FLAG=(--internal) ;;
  *) fail "VISIBILITY must be private, public, or internal; got: $VISIBILITY" ;;
esac

cd "$PROJECT_DIR"

log "Writing/refreshing .gitignore"
touch .gitignore
ensure_ignore() {
  local line="$1"
  grep -qxF "$line" .gitignore || printf '%s\n' "$line" >> .gitignore
}
ensure_ignore ".venv/"
ensure_ignore "artifacts/"
ensure_ignore "__pycache__/"
ensure_ignore "*.py[cod]"
ensure_ignore "*.egg-info/"
ensure_ignore "build/"
ensure_ignore "dist/"
ensure_ignore ".pytest_cache/"
ensure_ignore ".mypy_cache/"
ensure_ignore ".ruff_cache/"
ensure_ignore ".DS_Store"
ensure_ignore "tmp/"

log "Initializing local git repository"
if [ ! -d .git ]; then
  git init
fi
git branch -M "$DEFAULT_BRANCH"

# Configure local git identity if missing.
if ! git config user.name >/dev/null; then
  git config user.name "$(gh api user --jq .login)"
fi
if ! git config user.email >/dev/null; then
  GH_LOGIN="$(gh api user --jq .login)"
  GH_ID="$(gh api user --jq .id)"
  git config user.email "${GH_ID}+${GH_LOGIN}@users.noreply.github.com"
fi

if [ "$RUN_SMOKE" = "1" ]; then
  log "Running local smoke test"
  if [ ! -d .venv ]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install -e . >/dev/null
  copyspace-guard analyze \
    --csv examples/ring15.csv \
    --bw 256 \
    --roi examples/roi.yml \
    --outdir artifacts/prepush-smoke
  copyspace-guard gate artifacts/prepush-smoke/summary.json \
    --config examples/copyspace_guard.yml
fi

log "Creating local commit if there are changes"
git add -A
if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "$COMMIT_MSG"
fi

log "Creating GitHub repository if needed: $FULL_REPO"
if gh repo view "$FULL_REPO" >/dev/null 2>&1; then
  echo "GitHub repo already exists: $FULL_REPO"
else
  gh repo create "$FULL_REPO" "${VIS_FLAG[@]}" --description "$DESCRIPTION"
fi

if [ "$USE_SSH" = "1" ]; then
  REMOTE_URL="git@github.com:${FULL_REPO}.git"
else
  REMOTE_URL="https://github.com/${FULL_REPO}.git"
fi

log "Configuring origin remote: $REMOTE_URL"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

log "Pushing to GitHub"
git push -u origin "$DEFAULT_BRANCH"

log "Verifying remote HEAD"
LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git ls-remote origin "refs/heads/$DEFAULT_BRANCH" | awk '{print $1}')"

if [ -z "$REMOTE_HEAD" ]; then
  fail "remote branch not found after push: $DEFAULT_BRANCH"
fi

if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  fail "remote HEAD mismatch: local=$LOCAL_HEAD remote=$REMOTE_HEAD"
fi

log "Verifying repository metadata via GitHub API"
gh repo view "$FULL_REPO" \
  --json nameWithOwner,visibility,url,defaultBranchRef \
  --jq '.nameWithOwner + " | " + .visibility + " | " + .url + " | default=" + .defaultBranchRef.name'

gh api "repos/$FULL_REPO/contents/README.md?ref=$DEFAULT_BRANCH" \
  --jq '"README.md found, size=" + (.size|tostring) + " bytes"' >/dev/null

echo "README.md verified via GitHub API."

echo
printf '\033[1;32mSUCCESS\033[0m\n'
echo "Repository: https://github.com/$FULL_REPO"
echo "Branch:     $DEFAULT_BRANCH"
echo "Commit:     $LOCAL_HEAD"

if [ "$OPEN_BROWSER" = "1" ]; then
  gh repo view "$FULL_REPO" --web
fi
