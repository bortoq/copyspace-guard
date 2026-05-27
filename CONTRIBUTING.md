# Contributing

Thanks for contributing to Copy-Space Guard.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Required checks before opening a PR

```bash
make test
make security
make production-check
```

If your change touches release/versioning logic, also run:

```bash
make release-check
```

## Testing expectations

- Behavior changes require tests.
- CLI changes require CLI tests.
- Artifact/contract changes require schema/contract coverage.
- Documentation should be updated in the same PR when user-facing behavior changes.

## Branch and commit guidance

- Branch names: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- Keep commits focused and atomic.
- Prefer clear commit messages such as:
  - `feat: add ...`
  - `fix: handle ...`
  - `docs: update ...`

## Pull requests

- Describe what changed and why.
- Include risk notes (compatibility, perf, security).
- Include validation evidence (commands + key outputs).
- Link related issues.

## Security

For vulnerabilities, do not open a public issue first. Follow [SECURITY.md](SECURITY.md).
