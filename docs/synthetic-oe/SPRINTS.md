# SPRINTS — registry

Sprints are objects with identity, not positions in a list. **IDs are never reordered and
never reused**; gaps are normal and expected. A sprint that is abandoned keeps its ID and
its row.

**Backbone** sprints carry the paper's claims: changing one changes what the paper asserts,
and requires updating `RESEARCH_PLAN.md` in the same commit. **Probe** sprints are
exploratory and may be abandoned — each must declare its stopping criterion *in its design
document, before it starts*.

Statuses: `planned` · `active` · `done` · `abandoned` · `blocked`.

## Registry

| ID | Type | Status | Title | Serves | Depends on |
|---|---|---|---|---|---|
| S0 | backbone | **done** | Reproducibility foundation and splits | all | — |
| S1 | backbone | **done** | Harness adaptation to BC3CAT-Syn/OE | all | S0 |
| S2 | backbone | planned | Go/no-go probe ⚑ | H3 | S1 |
| S3 | backbone | planned | E0 controls, replication, overlap characterisation | H1, H5 | S2 |
| S4 | backbone | planned | E1 ablation — Track A | H1, H2 | S3 |
| S5 | backbone | planned | E1 ablation — Track B (structured) | H3 | S4 |
| S6 | backbone | planned | Statistical analysis and mediation | H1, H2, H5 | S4, S5 |
| S7 | backbone | planned | E2 stacked headline and stratifications | H1, H4 | S6 |
| S8 | backbone | blocked | E3 balanced dose design | H4 | S7 + upstream (D-009) |
| S9 | backbone | planned | Track C — query-side normalisation and rewriting | H6 | S6 |
| S10 | backbone | planned | Track D — learned representations | O4 | S6, G2 |
| S11 | backbone | planned | Track E — two-stage architecture | O4 | S6, G2 |
| S12 | backbone | planned | Frozen test evaluation and artefact release | O5 | S8–S11 |
| S13 | backbone | planned | Manuscript | — | S12 |
| S90 | probe | planned | Real-query anchor (Telice estimator queries) | validity | external (D-014) |

Emergent sprints take the next free ID: backbone work continues the S0–S13 sequence at
S14+, probes take S91+.

## Decision gates

| Gate | After | Question | If no |
|---|---|---|---|
| G1 | S2 | Does BM25 fall under L1 variation? | Reframe before S3; re-scope O4 |
| G2 | S5 | Does the structured/lexical ranking invert? | Method contribution moves from S11 to S10 |
| G3 | S8 | Did the balanced dose set arrive? | H4 becomes exploratory; sprint halves |
| G4 | S12 | Test split frozen | Any reopening is documented and re-run whole |

## Critical path

`S0 → S1 → S2 → S3 → S4 → S6 → S12 → S13` — about 14 weeks.

Parallelisable once S6 lands: S9, S10 and S11 are independent of one another. If time is
short, G2 decides which of S10/S11 gets the budget — the paper needs one method
contribution, not three. S7 and S8 are analysis over runs that already exist. S90 runs
entirely off the path.

## Log

Append one line per status transition. Date, ID, transition, one clause of reason.

| Date | ID | Transition | Note |
|---|---|---|---|
| 2026-09-14 | S0–S13, S90 | → planned | Registry seeded from `RESEARCH_PLAN.md` |
| 2026-09-15 | S0 | planned → active | Design frozen at `f618571`; entry state verified after the 2026-09-14 incident |
| 2026-09-15 | S0 | report written | All 7 exit criteria met; `done` withheld until `/audit S0` returns in a fresh session |
| 2026-09-15 | S0 | active → **done** | `/audit S0`: **PASS WITH FINDINGS** ([`SPRINT_S0_AUDIT.md`](sprints/SPRINT_S0_AUDIT.md)). All six findings resolved, F1 by adding the 77th config on `collection: "OE"` |
| 2026-09-15 | S1 | planned → **active** | Design frozen at `9cd244c`; entry state verified in the tree. Scope widened to five notebooks, and the golden fixture is captured before the migration rather than conceded as lost |
| 2026-09-15 | S1 | design amended | Work item 12 added: batch the retrieval scoring. The harness could not run the sprint's own exit criterion without it |
| 2026-09-16 | S1 | report written | All 8 exit criteria met; the fixture reproduces to ten decimal places. `done` withheld until `/audit S1` returns in a session that did not do the work |
| 2026-09-16 | S1 | design amended | Exit criterion 4 restated after audit F2, where the freeze rule sends it |
| 2026-09-16 | S1 | active → **done** | `/audit S1`: **PASS WITH FINDINGS** ([`SPRINT_S1_AUDIT.md`](sprints/SPRINT_S1_AUDIT.md)). Eight findings, two major, all resolved — the untracked fixture (F1) and the unamended criterion (F2) among them. D-025 raised from F3 |
