# Updating `~/work/copyspace-guard` from a ZIP archive

Use the script below when you receive a new project ZIP.

It:

- extracts the ZIP into a temporary directory;
- detects whether the archive contains a top-level `copyspace-guard/` folder;
- backs up the current project directory;
- syncs new project files;
- preserves `.venv/` and `artifacts/` by default;
- reinstalls the package in editable mode.

See `tools/update_from_zip.sh`.
