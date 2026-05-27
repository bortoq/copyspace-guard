# CI Integration

Use `copyspace-guard` as a deterministic schedule-audit gate in CI.

## GitHub Actions

See [examples/github_actions_schedule_audit.yml](../examples/github_actions_schedule_audit.yml).

## GitLab CI

```yaml
audit_schedule:
  image: python:3.12
  script:
    - pip install copyspace-guard
    - copyspace-guard audit --demands demands.csv --bw 256 --schedule schedule.csv --max-gap-vs-greedy 0.15 --outdir artifacts/audit
  artifacts:
    paths:
      - artifacts/audit/
```

## Jenkins

```groovy
stage('Schedule audit') {
  sh 'pip install copyspace-guard'
  sh 'copyspace-guard audit --demands demands.csv --bw 256 --schedule schedule.csv --max-gap-vs-greedy 0.15 --outdir artifacts/audit'
  archiveArtifacts artifacts: 'artifacts/audit/**', fingerprint: true
}
```
