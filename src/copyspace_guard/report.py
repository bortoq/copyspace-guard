from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .core import Report


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def money(x: float) -> str:
    return f"${x:,.2f}"


def _md_escape(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def _md_code(text: Any) -> str:
    value = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;")
    value = value.replace("`", "&#96;").replace("\r", " ").replace("\n", " ")
    return f"`{value}`"


def _inline_html(text: str) -> str:
    # Text is already HTML-safe from _md_escape / _md_code.
    # Only handle inline markers.
    result = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", result)


def _labels(summary: Dict[str, Any]) -> Tuple[str, str, Report, Report]:
    current_label = summary.get("current_label", "baseline")
    candidate_label = summary.get("candidate_label", "greedy")
    reports = summary["reports"]
    cur = Report(**reports.get(current_label, reports.get("baseline")))
    cand = Report(**reports[candidate_label])
    return current_label, candidate_label, cur, cand


def metric_table(current: Report, candidate: Report, comparison: Dict[str, Any], current_label: str = "current", candidate_label: str = "candidate") -> str:
    rows = [
        ("Validation status", current.status, candidate.status),
        ("Validation errors", str(current.total_errors), str(candidate.total_errors)),
        ("Ticks total", str(current.ticks_total), str(candidate.ticks_total)),
        ("Degree lower bound", str(current.degree_lower_bound), str(candidate.degree_lower_bound)),
        ("Capacity lower bound", str(current.capacity_lower_bound), str(candidate.capacity_lower_bound)),
        ("Density lower bound", str(current.density_lower_bound), str(candidate.density_lower_bound)),
        ("Effective lower-bound ticks", str(current.lower_bound_ticks), str(candidate.lower_bound_ticks)),
        ("Gap to lower bound", pct(current.gap_to_lower_bound), pct(candidate.gap_to_lower_bound)),
        ("Utilization", pct(current.utilization), pct(candidate.utilization)),
        ("Bits moved", f"{current.bits_total:,}", f"{candidate.bits_total:,}"),
    ]
    out = f"| Metric | {_md_code(current_label)} | {_md_code(candidate_label)} |\n|---|---:|---:|\n"
    for name, a, b in rows:
        out += f"| {_md_escape(name)} | {_md_escape(a)} | {_md_escape(b)} |\n"
    out += "\n"
    if not comparison.get("comparable", True):
        out += f"- Comparison status: **not comparable** - {_md_code(comparison.get('comparison_note', ''))}\n"
    else:
        out += f"- Saved ticks: **{comparison['saved_ticks']:,}** ({pct(comparison['saved_ticks_pct'])})\n"
        out += f"- Gap reduction: **{comparison['gap_reduction_ticks']:,} ticks**\n"
        out += f"- Utilization delta: **{pct(comparison['utilization_delta'])}**\n"
        if comparison.get("cost_per_tick", 0) > 0:
            out += f"- Estimated savings at {money(comparison['cost_per_tick'])}/tick: **{money(comparison['estimated_savings'])}** per run\n"
    return out


def roi_section(summary: Dict[str, Any]) -> str:
    roi = summary.get("roi") or {}
    if not roi or roi.get("cost_per_tick", 0) <= 0:
        return """## ROI model\n\nNo ROI configuration was provided. Add `--roi roi.yml` or `--cost-per-tick` to convert saved ticks into business impact.\n"""
    practical = roi.get("practical") or {}
    theoretical = roi.get("theoretical_max") or {}
    if practical and theoretical:
        return f"""## ROI model

| ROI metric | Practical (vs greedy) | Theoretical max (vs lower bound) |
|---|---:|---:|
| Saved ticks per run | {practical.get('saved_ticks', 0):,.2f} | {theoretical.get('saved_ticks', 0):,.2f} |
| Saved seconds per run | {practical.get('saved_seconds_per_run', 0):,.2f} | {theoretical.get('saved_seconds_per_run', 0):,.2f} |
| Savings per run | {money(practical.get('savings_per_run_usd', 0))} | {money(theoretical.get('savings_per_run_usd', 0))} |
| Savings per month | {money(practical.get('savings_per_month_usd', 0))} | {money(theoretical.get('savings_per_month_usd', 0))} |
| Savings per year | {money(practical.get('savings_per_year_usd', 0))} | {money(theoretical.get('savings_per_year_usd', 0))} |

Note: theoretical max is an upper estimate from the lower bound and may be unreachable in practice.
"""
    return f"""## ROI model

| ROI metric | Value |
|---|---:|
| Cost per tick | {money(roi.get('cost_per_tick', 0))} |
| Saved seconds per run | {roi.get('saved_seconds_per_run', 0):,.2f} |
| Saved hours per run | {roi.get('saved_hours_per_run', 0):,.4f} |
| Savings per run | {money(roi.get('savings_per_run_usd', 0))} |
| Runs per day | {roi.get('runs_per_day', 0):,.2f} |
| Savings per month | {money(roi.get('savings_per_month_usd', 0))} |
| Savings per year | {money(roi.get('savings_per_year_usd', 0))} |

Assumption source: `roi` config in `summary.json`. Treat this as a first-pass estimate until calibrated with real infrastructure costs.
"""


def bounds_warning_section(current: Report, candidate: Report) -> str:
    if current.bounds_complete and candidate.bounds_complete:
        return ""
    return """## Bound completeness warning

At least one schedule report was produced with partial lower-bound enumeration. For large slot counts, subset-density bounds are not exhaustively enumerated by default, so the true optimum may be higher than the reported lower bound and the reported gap may be understated.
"""


def audit_context_section(summary: Dict[str, Any]) -> str:
    audit = summary.get("audit")
    if not isinstance(audit, dict):
        return ""
    note = str(audit.get("audit_note", "")).strip()
    gap_vs_greedy = audit.get("gap_vs_greedy")
    line = ""
    if isinstance(gap_vs_greedy, (int, float)):
        line = f"\n- `gap_vs_greedy`: **{gap_vs_greedy:.4f}** (positive means current is slower than greedy)."
    if not note and not line:
        return ""
    return f"""## External schedule audit note

- {note or "No additional note."}{line}
"""


def diagnostics_section(current: Report, candidate: Report, current_label: str, candidate_label: str, *, max_examples: int = 5) -> str:
    reports = [(current_label, current), (candidate_label, candidate)]
    failing = [(label, rep) for label, rep in reports if rep.total_errors > 0]
    if not failing:
        return ""
    out = "## Validation diagnostics\n\n"
    for label, rep in failing:
        counts: Dict[str, int] = {}
        for err in rep.errors:
            kind = str(err.get("kind", "UNKNOWN"))
            counts[kind] = counts.get(kind, 0) + 1
        groups = ", ".join(f"{_md_code(kind)}: {count}" for kind, count in sorted(counts.items())) or "stored errors: 0"
        suffix = " Stored examples are truncated." if rep.errors_truncated else ""
        out += f"### {_md_code(label)}\n\n"
        out += f"- Total validation errors: **{rep.total_errors}**. Stored error groups: {groups}.{suffix}\n"
        for err in rep.errors[:max_examples]:
            kind = _md_code(err.get("kind", "UNKNOWN"))
            msg = _md_code(err.get("msg", ""))
            ctx = {k: v for k, v in err.items() if k not in {"kind", "msg"}}
            ctx_text = ", ".join(f"{_md_code(k)}={_md_code(v)}" for k, v in sorted(ctx.items()))
            detail = f" ({ctx_text})" if ctx_text else ""
            out += f"- `{kind}`: {msg}{detail}\n"
        out += "\n"
    return out


def render_markdown(summary: Dict[str, Any]) -> str:
    inst = summary["instance"]
    current_label, candidate_label, cur, cand = _labels(summary)
    comp = summary["comparison"]
    roi = summary.get("roi") or {}
    today = date.today().isoformat()
    inst_id = _md_code(inst.get("id", "unnamed"))
    model = _md_code(inst["model"])
    current_label_text = _md_code(current_label)
    candidate_label_text = _md_code(candidate_label)
    annual = roi.get("savings_per_year_usd", 0.0)
    if not comp.get("comparable", True):
        business_line = f"Savings are not computed because validation failed: {_md_code(comp.get('comparison_note', ''))}"
    else:
        business_line = (
            f"Estimated annualized savings under the supplied ROI model: **{money(annual)}**."
            if annual > 0 else
            "No annualized ROI model was supplied; this report quantifies technical savings in ticks, gap and utilization."
        )
    return f"""# Copy-Space Guard — Data Movement Audit Report

Date: {today}  
Workload: {inst_id}  
Model: {model}  
Slots: **{inst['slots']}**  
Bandwidth per slot-pair per tick: **{inst['copy_bw_bits_per_tick']:,} bits**  
Demands: **{len(inst.get('demands', []))} directed pairs**

## Executive summary

This report validates and compares two deterministic schedules for the same data-movement demand matrix.
The {current_label_text} schedule is treated as the current strategy. The {candidate_label_text} schedule is the deterministic candidate strategy.

**Business impact:** {business_line if not comp.get("comparable", True) else f"{candidate_label_text} saves **{comp['saved_ticks']:,} ticks** versus {current_label_text} and improves utilization by **{pct(comp['utilization_delta'])}**. {business_line}"}

{metric_table(cur, cand, comp, current_label, candidate_label)}

{roi_section(summary)}

{bounds_warning_section(cur, cand)}

{audit_context_section(summary)}

{diagnostics_section(cur, cand, current_label, candidate_label)}

## Commercial interpretation

- `degree_lower_bound` is derived from endpoint pressure.
- `capacity_lower_bound` is derived from total chunks divided by full-graph per-tick matching capacity.
- `density_lower_bound` is derived from all subset matching-capacity constraints when the slot count is within the exhaustive limit.
- `lower_bound_ticks` is the maximum of currently implemented deterministic lower bounds.
- `gap_to_lower_bound` estimates how far the schedule is from that lower bound under the declared {model} model.
- A positive saved-ticks number is potential time/capacity savings per workload run before deeper topology-specific modeling.
- The tool is metadata-only: it requires transfer demand metadata, not payload data.
- The CI gate can prevent future schedule regressions after scheduler, storage, ETL or infrastructure changes.

## Recommended next step

1. Replace the demo demand CSV with one real trace from the target system.
2. Confirm whether {model} matches the system constraints or extend the model.
3. Add this report as a CI regression gate: fail if `ticks_total`, `gap_to_lower_bound`, or utilization regress beyond agreed thresholds.
   For large instances, prefer `--max-gap-vs-greedy` as the primary metric.
4. If savings are material, build a customer-specific importer and compare the customer's scheduler against multiple candidate strategies.

## Files produced

- `instance.json` — normalized workload contract.
- `schedule_current` artifact — current/customer or baseline schedule.
- `schedule_greedy.json` — deterministic candidate schedule.
- `report_current` artifact — validation metrics for current/customer or baseline schedule.
- `report_greedy.json` — validation metrics for candidate.
- `summary.json` — machine-readable sales/engineering summary.
"""


def _card_html(title: str, value: str, sub: str = "") -> str:
    return f"<div class='kpi'><div class='kpi-title'>{html.escape(title)}</div><div class='kpi-value'>{html.escape(value)}</div><div class='kpi-sub'>{html.escape(sub)}</div></div>"


def executive_cards(summary: Dict[str, Any]) -> str:
    current_label, candidate_label, cur, cand = _labels(summary)
    comp = summary["comparison"]
    roi = summary.get("roi") or {}
    cards = [
        _card_html("Current ticks", f"{cur.ticks_total:,}", current_label),
        _card_html("Candidate ticks", f"{cand.ticks_total:,}", candidate_label),
        _card_html("Saved ticks", f"{comp.get('saved_ticks', 0):,}", pct(comp.get("saved_ticks_pct", 0))),
        _card_html("Utilization gain", pct(comp.get("utilization_delta", 0)), f"{pct(cur.utilization)} → {pct(cand.utilization)}"),
        _card_html("Candidate gap", pct(cand.gap_to_lower_bound), "to deterministic lower bound"),
    ]
    if roi.get("savings_per_year_usd", 0) > 0:
        cards.append(_card_html("Annualized savings", money(roi.get("savings_per_year_usd", 0)), "ROI estimate"))
    return "<div class='kpis'>" + "".join(cards) + "</div>"


def _visualization_block(summary: Dict[str, Any]) -> str:
    current_label, candidate_label, cur, cand = _labels(summary)
    lb = max(1, int(cand.lower_bound_ticks))
    mx = max(cur.ticks_total, cand.ticks_total, lb, 1)
    h = 160

    def bar_height(v: int) -> int:
        return max(2, int((v / mx) * h))

    cur_h = bar_height(cur.ticks_total)
    cand_h = bar_height(cand.ticks_total)
    lb_h = bar_height(lb)

    demands = summary.get("instance", {}).get("demands", [])
    slot_load: Dict[int, int] = {}
    for d in demands if isinstance(demands, list) else []:
        if not isinstance(d, dict):
            continue
        s = int(d.get("src_slot", 0))
        t = int(d.get("dst_slot", 0))
        b = int(d.get("bits_total", 0))
        slot_load[s] = slot_load.get(s, 0) + b
        slot_load[t] = slot_load.get(t, 0) + b
    top_slots = sorted(slot_load.items(), key=lambda x: x[1], reverse=True)[:5]
    top_slots_html = "".join(
        f"<li>slot {s}: {v:,} bits</li>" for s, v in top_slots
    ) or "<li>no demand stats available</li>"

    return f"""
<section class="viz">
  <h2>Gap Visualization</h2>
  <svg viewBox="0 0 420 220" role="img" aria-label="ticks comparison">
    <rect x="40" y="{190-cur_h}" width="90" height="{cur_h}" fill="#ff8f6b"><title>{current_label}: {cur.ticks_total} ticks</title></rect>
    <rect x="165" y="{190-cand_h}" width="90" height="{cand_h}" fill="#67e8f9"><title>{candidate_label}: {cand.ticks_total} ticks</title></rect>
    <rect x="290" y="{190-lb_h}" width="90" height="{lb_h}" fill="#86efac"><title>lower bound: {lb} ticks</title></rect>
    <text x="45" y="205" fill="#a8b3cf" font-size="12">{html.escape(current_label)}</text>
    <text x="170" y="205" fill="#a8b3cf" font-size="12">{html.escape(candidate_label)}</text>
    <text x="305" y="205" fill="#a8b3cf" font-size="12">lower bound</text>
  </svg>
  <h3>Top loaded slots</h3>
  <ul>{top_slots_html}</ul>
</section>
"""


def render_html(summary: Dict[str, Any]) -> str:
    md = render_markdown(summary)
    lines = md.splitlines()
    body: List[str] = []
    in_ul = False
    in_ol = False
    in_table = False
    table_rows: List[str] = []

    def flush_ul() -> None:
        nonlocal in_ul
        if in_ul:
            body.append("</ul>")
            in_ul = False

    def flush_ol() -> None:
        nonlocal in_ol
        if in_ol:
            body.append("</ol>")
            in_ol = False

    def flush_table() -> None:
        nonlocal in_table, table_rows
        if in_table:
            body.append("<table>" + "".join(table_rows) + "</table>")
            in_table = False
            table_rows = []

    for line in lines:
        if line.startswith("|"):
            flush_ul()
            flush_ol()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                in_table = True
                tag = "th"
            table_rows.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
            continue
        flush_table()
        if line.startswith("# "):
            flush_ul()
            flush_ol()
            body.append(f"<h1>{_inline_html(line[2:])}</h1>")
        elif line.startswith("## "):
            flush_ul()
            flush_ol()
            body.append(f"<h2>{_inline_html(line[3:])}</h2>")
        elif line.startswith("### "):
            flush_ul()
            flush_ol()
            body.append(f"<h3>{_inline_html(line[4:])}</h3>")
        elif line.startswith("- "):
            flush_ol()
            if not in_ul:
                body.append("<ul>")
                in_ul = True
            body.append(f"<li>{_inline_html(line[2:])}</li>")
        elif re.match(r"^\d+\. ", line):
            flush_ul()
            if not in_ol:
                body.append("<ol>")
                in_ol = True
            body.append(f"<li>{_inline_html(line.split('. ', 1)[1])}</li>")
        elif not line.strip():
            flush_ul()
            flush_ol()
            body.append("")
        else:
            flush_ul()
            flush_ol()
            body.append(f"<p>{_inline_html(line)}</p>")
    flush_ul()
    flush_ol()
    flush_table()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Copy-Space Guard Audit Report</title>
<style>
:root {{ --bg:#0b1020; --card:#121a33; --text:#ecf2ff; --muted:#a8b3cf; --accent:#67e8f9; --good:#86efac; --warn:#fde68a; --line:#263154; }}
body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif; background:linear-gradient(135deg,#08111f,#151b3a); color:var(--text); }}
main {{ max-width:1120px; margin:40px auto; padding:0 24px 60px; }}
h1 {{ font-size:44px; line-height:1.05; margin:0 0 20px; }}
h2 {{ margin-top:34px; color:var(--accent); }}
p, li {{ color:var(--muted); font-size:16px; line-height:1.55; }}
.card {{ background:rgba(18,26,51,.88); border:1px solid var(--line); border-radius:18px; padding:26px; box-shadow:0 20px 60px rgba(0,0,0,.35); }}
.kpis {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin:18px 0 24px; }}
.kpi {{ background:#0b1328; border:1px solid #2b3b62; border-radius:16px; padding:18px; }}
.kpi-title {{ color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.08em; }}
.kpi-value {{ color:var(--good); font-weight:800; font-size:32px; margin-top:8px; }}
.kpi-sub {{ color:var(--muted); font-size:13px; margin-top:4px; }}
.viz {{ margin: 10px 0 18px; padding: 14px 18px; border:1px solid var(--line); border-radius:16px; background:#0d1530; }}
.viz svg {{ width:100%; height:auto; display:block; margin:8px 0 6px; }}
table {{ width:100%; border-collapse:collapse; margin:18px 0; overflow:hidden; border-radius:12px; }}
th, td {{ padding:12px 14px; border-bottom:1px solid var(--line); text-align:left; }}
th {{ background:#1d2a52; color:#fff; }}
td:nth-child(2), td:nth-child(3), th:nth-child(2), th:nth-child(3) {{ text-align:right; }}
code {{ color:var(--good); background:#0c1428; padding:2px 6px; border-radius:6px; }}
.badge {{ display:inline-block; padding:6px 10px; border:1px solid var(--accent); color:var(--accent); border-radius:999px; margin-bottom:16px; }}
@media(max-width:860px) {{ .kpis {{ grid-template-columns:1fr; }} h1 {{ font-size:34px; }} }}
</style>
</head>
<body><main><div class="badge">Metadata-only deterministic audit</div>{executive_cards(summary)}{_visualization_block(summary)}<div class="card">
{''.join(body)}
</div></main></body></html>
"""


def write_reports(outdir: str | Path, summary: Dict[str, Any]) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render_markdown(summary), encoding="utf-8")
    (out / "report.html").write_text(render_html(summary), encoding="utf-8")
