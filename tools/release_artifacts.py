from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_project_metadata() -> tuple[str, str, list[str]]:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_py = (ROOT / "src" / "copyspace_guard" / "__init__.py").read_text(encoding="utf-8")
    name_match = re.search(r'^name\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    version_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_py)
    if not name_match or not version_match:
        raise SystemExit("could not read project name/version")
    deps_match = re.search(r"^dependencies\s*=\s*\[(.*?)\]", pyproject, re.MULTILINE | re.DOTALL)
    dependencies: list[str] = []
    if deps_match:
        dependencies = re.findall(r'"([^"]+)"', deps_match.group(1))
    return name_match.group(1), version_match.group(1), dependencies


def write_checksums(dist: Path, out: Path, files: list[Path]) -> Path:
    checksums = out / "SHA256SUMS"
    rows = [f"{sha256(path)}  {path.name}" for path in files]
    checksums.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return checksums


def write_manifest(out: Path, project: str, version: str, files: list[Path]) -> Path:
    manifest = out / "release_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["project", "version", "filename", "sha256", "bytes"])
        for path in files:
            writer.writerow([project, version, path.name, sha256(path), path.stat().st_size])
    return manifest


def write_sbom(out: Path, project: str, version: str, dependencies: list[str], files: list[Path]) -> Path:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    components: list[dict[str, Any]] = [
        {
            "type": "application",
            "name": project,
            "version": version,
            "purl": f"pkg:pypi/{project}@{version}",
        }
    ]
    for dep in dependencies:
        components.append({"type": "library", "name": dep})

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": now,
            "component": components[0],
            "properties": [{"name": "tool", "value": "tools/release_artifacts.py"}],
        },
        "components": components,
        "services": [],
        "externalReferences": [
            {
                "type": "distribution",
                "url": path.name,
                "hashes": [{"alg": "SHA-256", "content": sha256(path)}],
            }
            for path in files
        ],
    }
    sbom = out / "sbom.cdx.json"
    sbom.write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sbom


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release checksums, manifest and SBOM")
    parser.add_argument("--dist", default="dist")
    parser.add_argument("--out", default="dist")
    args = parser.parse_args()

    dist = Path(args.dist)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in dist.iterdir() if p.suffix in {".whl", ".gz"} and p.is_file()])
    if not files:
        raise SystemExit(f"no wheel/sdist files found in {dist}")

    project, version, dependencies = read_project_metadata()
    generated = [
        write_checksums(dist, out, files),
        write_manifest(out, project, version, files),
        write_sbom(out, project, version, dependencies, files),
    ]
    for path in generated:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
