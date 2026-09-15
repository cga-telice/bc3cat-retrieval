# STATE — `research/synthetic-oe`

The single living status file for this branch. One file, always current, kept under 2 KB.
Dated snapshots belong in `archive/`, not here. Updated at every sprint transition and
whenever something blocks.

**Last updated:** 2026-09-15 · **Updated by:** César

---

## Where we are

**Active sprint:** **S0** — Reproducibility foundation and splits. Design frozen at `f618571`.
**Phase:** pre-execution. No runs exist on this branch.

## Done

- BC3CAT-Syn/OE release received and validated (`INTAKE.md`, 2026-09-08); counts there.
- Research proposal and sprint plan written (`RESEARCH_PROPOSAL.md`, `RESEARCH_PLAN.md`).
- Documentation and agent scaffolding created.
- 2026-09-15: `data/` repopulated after the incident; five OE digests re-verified against
  `INTAKE.md §2`. Config inventory re-run by parsing all 77 (D-016 amended: 72, not 2).

## In flight

- **S0**, opened 2026-09-15. Done: manifest, split (D-021), E3 spec, D-017.
  Left: layout, configs, issuing E3.

## Incident — 2026-09-14

`data/`, `index/`, `runs/`, `logs/` and `hf-cache/` were emptied by an agent session. `runs/`
is lost; `data/` was repopulated and verified 2026-09-15. No impact on S0/S1. Record:
[`archive/INCIDENT_2026-09-14.md`](archive/INCIDENT_2026-09-14.md) · decisions D-019, D-020.

## Blocked / waiting

- **E3 balanced dose set** (counts 1–5, randomised type mixes, `reorder` admitted) — to be
  requested from `bc3cat-dataset` in S0. Long external lead time; blocks S08 only.
- **Real-query anchor** (200–500 Telice estimator queries) — not requested yet. Off the
  critical path.

## Next action

Execute S0 work items 1–6, then `/sprint-close S0`. No run happens in S0.

## Latest results

None yet. When runs exist, this section points at `results/` and names the last audited
sprint — it does not reproduce numbers.

## Open decisions

See `DECISIONS.md` (status `Open`). Gating: method scope on OE (D-012). Closed in S0:
D-007/D-021, D-008, D-016, D-017. D-022 is S1's entry decision.
