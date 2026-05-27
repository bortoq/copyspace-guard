# Governance

This project uses a lightweight maintainer model.

## Roles

- Maintainer: can approve, merge, and cut releases.
- Reviewer: trusted contributor who reviews changes.
- Contributor: anyone submitting issues or pull requests.

## Decision process

- Default merge rule: at least one maintainer approval and green required CI checks.
- For risky changes (security, schema contracts, release workflows), prefer two reviews.
- In case of disagreement, maintainers decide based on security, correctness, and backward compatibility.

## Release governance

- Release tags are created by maintainers.
- PyPI Trusted Publishing and GitHub release pipeline ownership must be held by at least two maintainers.
- If the primary maintainer is unavailable, another maintainer may run releases using the documented process in `doc/RELEASE_PROCESS.md`.

## Stability and breaking changes

- Contract-breaking changes require:
  - explicit changelog entry,
  - migration notes,
  - artifact version bump when needed.

## Security and incident handling

- Security reports follow [SECURITY.md](SECURITY.md).
- Maintainers coordinate triage, fix timeline, and disclosure.
