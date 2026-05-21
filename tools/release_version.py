from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
INIT_PY = ROOT / "src" / "copyspace_guard" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[a-zA-Z0-9.-]+)?$")


def _read_version() -> tuple[str, str]:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    init_py = INIT_PY.read_text(encoding="utf-8")
    py_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    init_match = re.search(r'^__version__\s*=\s*"([^"]+)"', init_py, re.MULTILINE)
    if not py_match:
        raise SystemExit("pyproject.toml project.version not found")
    if not init_match:
        raise SystemExit("src/copyspace_guard/__init__.py __version__ not found")
    return py_match.group(1), init_match.group(1)


def _normalize_tag(tag: str | None) -> str | None:
    if not tag:
        return None
    return tag[1:] if tag.startswith("v") else tag


def check(tag: str | None = None) -> None:
    py_version, init_version = _read_version()
    if py_version != init_version:
        raise SystemExit(f"version mismatch: pyproject.toml={py_version} __init__.py={init_version}")
    tag_version = _normalize_tag(tag)
    if tag_version and py_version != tag_version:
        raise SystemExit(f"tag/version mismatch: tag={tag} project={py_version}")
    print(f"release version ok: {py_version}")


def _replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"expected one replacement in {path}")
    path.write_text(new_text, encoding="utf-8")


def bump(version: str, notes: list[str]) -> None:
    if not VERSION_RE.match(version):
        raise SystemExit(f"invalid release version: {version}")
    _replace_once(PYPROJECT, r'^version\s*=\s*"[^"]+"', f'version = "{version}"')
    _replace_once(INIT_PY, r'^__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"')
    changelog = CHANGELOG.read_text(encoding="utf-8")
    heading = f"## v{version} — {date.today().isoformat()}"
    if heading in changelog:
        raise SystemExit(f"changelog already has entry for v{version}")
    body_notes = notes or ["Release maintenance update."]
    entry = "\n".join(["", heading, "", "Highlights:", "", *[f"- {note}" for note in body_notes], ""])
    if not changelog.startswith("# Changelog\n"):
        raise SystemExit("CHANGELOG.md must start with '# Changelog'")
    CHANGELOG.write_text(changelog.replace("# Changelog\n", f"# Changelog\n{entry}", 1), encoding="utf-8")
    check(f"v{version}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or update Copy-Space Guard release version metadata")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--tag", default=None, help="optional tag name, for example v0.2.3")
    bump_parser = sub.add_parser("bump")
    bump_parser.add_argument("version", help="release version without leading v, for example 0.2.3")
    bump_parser.add_argument("--note", action="append", default=[], help="changelog bullet; can be repeated")
    args = parser.parse_args()
    if args.cmd == "check":
        check(args.tag)
    else:
        bump(args.version, args.note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
