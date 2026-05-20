# Competitive landscape

## Positioning statement

Copy-Space Guard is not a file-transfer tool, not storage, and not a general workflow orchestrator.

It is an independent deterministic validation and audit layer for data-movement plans.

## Competitor categories

### 1. Existing internal scripts

Most common competitor.

Examples:

- Python scripts;
- spreadsheet analysis;
- ad-hoc OR-Tools model;
- custom scheduler metrics;
- manual review.

Response:

- Copy-Space Guard standardizes the contract, metrics and CI gate.
- It is deterministic and produces repeatable reports.
- It is easier to share with management and partners.

### 2. Data transfer products

Examples:

- AWS DataSync;
- IBM Aspera;
- Signiant;
- Resilio;
- Globus;
- rclone.

They move data. Copy-Space Guard validates whether the movement plan is conflict-free and efficient. It can sit above them.

### 3. AI/HPC transfer libraries

Examples:

- NVIDIA NIXL;
- UCX;
- RDMA-based transfer layers;
- GPUDirect Storage integrations.

They provide transport. Copy-Space Guard provides plan validation, schedule comparison and CI regression metrics.

### 4. AI storage platforms

Examples:

- VAST Data;
- WEKA;
- DDN;
- Hammerspace;
- Dell;
- NetApp;
- Pure Storage.

They provide storage/data platforms. Copy-Space Guard can be used by customers or vendors as a benchmark, proof-of-efficiency and regression harness.

### 5. Workflow orchestrators

Examples:

- Airflow;
- Dagster;
- Prefect;
- Argo;
- Kubeflow.

They answer “when should tasks run?” Copy-Space Guard answers “is the data movement inside those tasks efficient and non-regressing?”

## Differentiation table

| Capability | Copy-Space Guard | Transfer tools | Storage platforms | Orchestrators |
|---|---:|---:|---:|---:|
| Moves payload data | No | Yes | Yes | Sometimes |
| Metadata-only audit | Yes | Partial | Partial | Partial |
| Deterministic lower-bound gap | Yes | No | Rare | No |
| Independent scheduler validation | Yes | No | Rare | No |
| CI regression gate for movement plans | Yes | Partial | Partial | Partial |
| Receipt/ledger roadmap | Yes | No | Partial | No |

## Sales angle

Do not ask the customer to replace their infrastructure.

Ask for one trace and offer a deterministic report.
