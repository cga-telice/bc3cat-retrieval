# STATE — `research/synthetic-oe`

The single living status file for this branch. One file, always current, kept under 2 KB.
Dated snapshots belong in `archive/`, not here. Updated at every sprint transition and
whenever something blocks.

**Last updated:** 2026-09-14 · **Updated by:** César

---

## Where we are

**Active sprint:** none — branch scaffolding in place, S0 not yet opened.
**Phase:** pre-execution. No runs exist on this branch.

## Done

- BC3CAT-Syn/OE release received and validated (`INTAKE.md`, 2026-09-08): 70,242 corpus
  records, 4,439 single + 4,998 stacked queries, all gold keys verified present.
- Research proposal and sprint plan written (`RESEARCH_PROPOSAL.md`, `RESEARCH_PLAN.md`).
- Documentation and agent scaffolding created.
- 2026-09-14: the five OE data files verified byte-for-byte against the digests in
  `INTAKE.md` in the main checkout — part of S0's entry state, already satisfied.
- 2026-09-14: config↔module inventory over the 77 configs; three gaps found (D-016, D-017).

## In flight

- Nothing running.

## Blocked / waiting

- **E3 balanced dose set** (counts 1–5, randomised type mixes, `reorder` admitted) — to be
  requested from `bc3cat-dataset` in S0. Long external lead time; blocks S08 only.
- **Real-query anchor** (200–500 Telice estimator queries) — not requested yet. Off the
  critical path.

## Next action

Open **S0 — Reproducibility foundation and splits**: `/sprint-open S0`.

## Latest results

None yet. When runs exist, this section points at `results/` and names the last audited
sprint — it does not reproduce numbers.

## Open decisions

See `DECISIONS.md` (status `Open`). The ones that gate work: split design (D-007),
run layout (D-008), method scope on OE (D-012), `dense_colbert128` (D-017).
