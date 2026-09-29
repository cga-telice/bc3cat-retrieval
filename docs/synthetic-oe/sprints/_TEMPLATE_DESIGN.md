# Sprint <ID> — <title> · design

> **Frozen at:** `<commit SHA>` · `<date>`
> This document is read-only from that commit. Changes go in
> [`SPRINT_<ID>_AMENDMENTS.md`](SPRINT_<ID>_AMENDMENTS.md) (D-045), dated and justified — never as
> in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `<S0x>` · backbone \| probe |
| **Status** | planned → active |
| **Serves** | `<hypotheses / objectives>` |
| **Depends on** | `<sprint IDs, upstream deliveries>` |
| **Decisions applied** | `<D-0xx, D-0yy>` |
| **Effort** | `<weeks>` |
| **Predecessor / successor** | `<IDs>` |

## Goal

One paragraph. What will be *known* at the end that is not known now. Not a list of tasks —
a change in knowledge.

## Entry state

What must already exist for this sprint to start: sprints closed, files present, digests
recorded, upstream deliveries received. Verified, not assumed — state how each was checked.

## Work

Numbered, each item concrete enough to execute. For every experiment: the methods, the
query sets, the conditions, and the split it runs on.

## Design constraints

The methodological commitments that make the results interpretable — paired comparisons,
which population an effect is estimated on, what must not be compared with what, which
caveats are carried in from the data. Written *before* results, because that is the point.

## Exit criteria

Verifiable conditions, not intentions. "Metrics computed" is not an exit criterion;
"identity control ≥ 0.98 for all three methods, reproduced from `runs/`" is.

## Stopping criterion — probes only

The time budget or the result that makes this sprint pointless. Mandatory for probes;
a probe without one is not approved.

## Out of scope

What this sprint deliberately does not do, and which sprint does it instead.

## Risks

| Risk | Handling |
|---|---|

## Amendments

In [`SPRINT_<ID>_AMENDMENTS.md`](SPRINT_<ID>_AMENDMENTS.md), append-only (D-045).
