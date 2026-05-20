# Customer report template

# Data Movement Audit — <Customer / Workload>

## Executive summary

- Workload analyzed:
- Input trace period:
- Model used:
- Current schedule ticks:
- Lower-bound ticks:
- Gap to lower bound:
- Candidate schedule ticks:
- Estimated savings:

## Key finding

The current movement plan is `<X>%` above the deterministic lower bound under the declared model. The candidate schedule reduces total ticks by `<N>` (`<Y>%`) and improves utilization from `<A>%` to `<B>%`.

## Method

1. Convert customer trace into `src_slot,dst_slot,bits_total` demand matrix.
2. Validate structural assumptions.
3. Generate baseline and candidate schedules.
4. Validate schedules under STRICT1.
5. Compute lower-bound gap, utilization and savings estimate.

## Metrics

| Metric | Current | Candidate |
|---|---:|---:|
| Ticks total | | |
| Lower-bound ticks | | |
| Gap to lower bound | | |
| Utilization | | |
| Bits moved | | |
| Estimated cost/run | | |

## Interpretation

- Lower-bound gap is not a promise of exact optimality; it is a deterministic pressure metric.
- Any candidate improvement should be tested against real topology and runtime constraints.
- If the gap remains large, next step is to extend the model or improve scheduling policy.

## CI gate recommendation

Suggested fail conditions:

```text
report.status must equal PASS
gap_to_lower_bound must not exceed <threshold>
ticks_total must not regress by more than <threshold>%
utilization must not fall below <threshold>%
```

## Next steps

- Confirm resource model.
- Import actual current schedule.
- Add topology/tier constraints if needed.
- Run nightly regression on representative traces.
