# STATE — `research/synthetic-oe`

The single living status file for this branch. Always current, under 2 KB. Dated snapshots
belong in `archive/`. Updated at every sprint transition and whenever something blocks.

**Last updated:** 2026-09-15 · **Updated by:** César

---

## Where we are

**Active sprint:** **S1 — harness adaptation**, design frozen at `9cd244c`.
**Phase:** pre-execution. No run exists yet; the first is S1's OEB golden fixture, captured
*before* any notebook is migrated.

## Done

- Release received and validated (`INTAKE.md`, 2026-09-08); proposal and plan written.
- **S0 done 2026-09-15** — `data/` repopulated, five OE digests re-verified, `MANIFEST.md`,
  `SPLITS.md` (seed `20260915`), 77 configs naming collection and retriever, E3 issued.
  Audited fresh: PASS WITH FINDINGS, all six resolved
  ([`SPRINT_S0_AUDIT.md`](sprints/SPRINT_S0_AUDIT.md)).

## In flight

- **S1 opened 2026-09-15.** Five notebooks onto one resolver (D-022, widened from three);
  gold decoupled from the query key, fail-loud; one BM25 config on OE over all four query
  sets, dev split only. S1 produces no citable number.

## Incident — 2026-09-14

`data/`, `index/`, `runs/`, `logs/`, `hf-cache/` emptied by an agent session; `runs/` lost,
`data/` repopulated and verified. S1 rebuilds the lost baseline rather than doing without it.
[`archive/INCIDENT_2026-09-14.md`](archive/INCIDENT_2026-09-14.md) · D-019, D-020.

## Blocked / waiting

- **E3 balanced dose set** — requested from `bc3cat-dataset` 2026-09-15 (D-009). Blocks S8
  only; gate G3 decides if it is late.
- **Real-query anchor** (200–500 Telice queries) — not requested. Off the path.

## Next action

S1 items 1–3, in order and as a gate: `run_context.py` with tests, the `pytest` harness
(`tests/` has no tracked file), then the OEB golden fixture. If the fixture is not captured
within three days, fall back to static path equality and record the downgrade as an
amendment rather than extending the sprint.

## Latest results

None yet. When runs exist this points at `results/` and names the last audited sprint; it
never reproduces numbers.

## Open decisions

See `DECISIONS.md` (`Open`). Gating: method scope on OE (D-012) — gates S3, not S1. Closed in
S0: D-007/D-021, D-008, D-016, D-017. D-022 is executed in S1, which raises **D-023** (index
over the full corpus; the split selects queries only) and **D-024** (the `OEB#` template
row), and amends D-008 to add `texto` as a fourth query set — `resumen` is the replication
baseline, not the identity rendering.
