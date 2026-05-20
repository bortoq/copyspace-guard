# Security policy

## Supported versions

Security fixes are provided for the latest tagged release and the current `main` branch while the project is in v0.x.

## Reporting a vulnerability

Open a private security advisory in GitHub, or contact the maintainer listed in `pyproject.toml` if private advisory access is unavailable.

Include:

- affected version or commit;
- reproduction steps;
- expected and actual behavior;
- whether customer metadata, reports, or mapping files can be exposed.

## Data handling

Copy-Space Guard is a local CLI and does not make network calls at runtime. Inputs and outputs may still contain sensitive topology or endpoint metadata. Treat raw CSV files, anonymization mappings, and generated reports according to the customer's data policy.
