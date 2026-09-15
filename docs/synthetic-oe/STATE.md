# STATE — `research/synthetic-oe`

The single living status file for this branch. Always current, under 2 KB. Dated snapshots
belong in `archive/`. Updated at every sprint transition and whenever something blocks.

**Last updated:** 2026-09-16 · **Updated by:** César

---

## Where we are

**Active sprint:** **S1 — harness adaptation**, design frozen at `9cd244c`.
**Phase:** executing. Items 1-10 and 12 done; 11 done for all four query sets on dev. The
sprint report is what remains.

## Done

- Release received and validated (`INTAKE.md`, 2026-09-08); proposal and plan written.
- **S0 done 2026-09-15** — `data/` repopulated, five OE digests re-verified, `MANIFEST.md`,
  `SPLITS.md` (seed `20260915`), 77 configs naming collection and retriever, E3 issued.
  Audited fresh: PASS WITH FINDINGS, all six resolved
  ([`SPRINT_S0_AUDIT.md`](sprints/SPRINT_S0_AUDIT.md)).

## In flight

- **S1 opened 2026-09-15.** Five notebooks now run off one resolver; gold comes from the
  query record; scoring is batched (design amendment, 2026-09-15). 252 tests, none skipped.
  **The OEB golden fixture reproduces exactly after the migration** — all six figures, no
  differences — so the plumbing change moved no number. Four OE runs exist on dev.
  S1 produces no citable number; the run figures are plumbing evidence for S2.

## Incident — 2026-09-14

`data/`, `index/`, `runs/`, `logs/`, `hf-cache/` emptied by an agent session; `runs/` lost,
`data/` repopulated and verified. S1 rebuilds the lost baseline rather than doing without it.
[`archive/INCIDENT_2026-09-14.md`](archive/INCIDENT_2026-09-14.md) · D-019, D-020.

## Blocked / waiting

- **E3 balanced dose set** — requested from `bc3cat-dataset` 2026-09-15 (D-009). Blocks S8
  only; gate G3 decides if it is late.
- **Real-query anchor** (200–500 Telice queries) — not requested. Off the path.

## Next action

Write `sprints/SPRINT_S1_REPORT.md` against the frozen design, then `/audit S1` in a
session that did not do the work. Two things the report must carry: the manuscript's 0.974
comes from a 16,590-of-47,513 sample (`RANDOM_SAMPLE`, seed 42), and `ranx` is absent from
`requirements.txt` although the contract names ranx 0.3.7.

## Latest results

Five runs exist under `runs/{collection}/{queryset}/{method}`, four of them OE on dev.
**None is a result.** S1 is plumbing: its figures are evidence that the harness runs, and
the first reportable numbers come from S2. `results/` is still empty.

## Open decisions

See `DECISIONS.md` (`Open`). Gating: method scope on OE (D-012) — gates S3, not S1.
Closed in S1: **D-016** (the alias table is gone) and **D-022** (executed, scope widened to
five notebooks, verification numeric rather than structural). Recorded in S1: **D-023**
(the index is built over the full corpus; the split selects queries only), **D-024** (the
`OEB#` row), and an amendment to **D-008** adding `texto` as the fourth query set —
`resumen` is the replication baseline, not the identity rendering.
