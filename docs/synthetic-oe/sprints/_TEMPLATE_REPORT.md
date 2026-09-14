# Sprint <ID> — <title> · report

| Field | Value |
|---|---|
| **Design** | [`SPRINT_<ID>_DESIGN.md`](SPRINT_<ID>_DESIGN.md) · frozen at `<SHA>` |
| **Closed** | `<date>` |
| **Code commit** | `<SHA>` |
| **Query-set digests** | `<name: sha256 prefix>` |
| **Runs** | `runs/<collection>/<queryset>/…` |
| **Results** | `results/<…>` — generated, not typed |

## What ran

Each experiment with its provenance stamp: `{run_id, config SHA, code commit, query-set
SHA-256}`. A number that cannot be stamped does not enter this report.

## Findings

The numbers, and what they mean. Point at `results/` for tables and figures; do not paste
bulk output here — this file has a 15 KB budget and the tables are derived artefacts.

## Hypotheses

| Hypothesis | Movement | Evidence |
|---|---|---|

State movement plainly: supported, refuted, unresolved, or not addressed. "Trending
towards" is not a movement.

## What is now known to be wrong

Assumptions this sprint falsified — about the data, the harness, the methods, or the plan.
This section is the most valuable one in the file and the easiest to leave empty. Resist.

## Exit criteria

| Criterion | Met | Evidence |
|---|---|---|

## Deviations from design

Anything done differently from the frozen design, with the amendment entry it corresponds
to. An undeclared deviation is a defect, not a footnote.

## What the next sprint inherits

Artefacts, open questions, and any debt created here.

## Decisions raised

New entries proposed for `DECISIONS.md`, or existing ones this sprint superseded.
