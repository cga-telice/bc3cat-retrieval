# STATE — `research/synthetic-oe`

The single living status file for this branch. One file, always current, kept under 2 KB.
Dated snapshots belong in `archive/`, not here. Updated at every sprint transition and
whenever something blocks.

**Last updated:** 2026-09-15 · **Updated by:** César

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

## Incident — 2026-09-14, working-set deletion

`data/`, `index/`, `runs/`, `logs/` and `hf-cache/` were emptied by an agent session. They
are git-ignored, so nothing is recoverable from any branch; no shadow copies existed. See
D-019.

| Path | Status | Repopulate from |
|---|---|---|
| `data/processed/OE_*` | restored 2026-09-15, digests verified | `Downloads/BC3CAT_Syn_OE_handoff` |
| `data/processed/OEB_*` | restored 2026-09-15 | `../bc3cat-dataset/data/processed/` |
| `index/`, `hf-cache/` | lost | derived — rebuild |
| `runs/` | **lost, not recoverable** | per-query rankings of the previous study; aggregate metrics survive in `eval/`, structured-line analyses in `analysis/` |
| `eval/`, `evals/`, `analysis/` | intact | now committed in full — see D-020 |

Impact on this branch: none. S0 and S1 do not touch `runs/`; OE runs are new work from S3.
The previous study's evaluation was already scheduled for a full re-run on a single query
sample (review recommendation 3), and the structured-pipeline runs were outside the
reproducible tag, so neither was citable as it stood.

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
