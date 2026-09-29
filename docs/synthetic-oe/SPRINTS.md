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
| S2 | backbone | **done** | Go/no-go probe ⚑ | H3 | S1 |
| S3 | backbone | **done** | E0 controls, replication, overlap characterisation | H1, H5 | S2 |
| S4 | backbone | **active** | E1 ablation — Track A | H1, H2 | S3 |
| S5 | backbone | planned | E1 ablation — Track B (structured) | H3 | S4 |
| S6 | backbone | planned | Statistical analysis and mediation | H1, H2, H5 | S4, S5 |
| S7 | backbone | planned | E2 stacked headline and stratifications | H1, H4 | S6 |
| S8 | backbone | planned | E3 balanced dose design | H4 | S7 |
| S9 | backbone | planned | Track C — query-side normalisation and rewriting | H6 | S6 |
| S10 | backbone | planned | Track D — learned representations | O4 | S6, G2 |
| S11 | backbone | planned | Track E — two-stage architecture | O4 | S6, G2 |
| S12 | backbone | planned | Frozen test evaluation and artefact release | O5 | S8–S11 |
| S13 | backbone | planned | Manuscript | — | S12 |
| S90 | probe | planned | Real-query anchor (Telice estimator queries) | validity | external (D-014) |
| S91 | probe | **done** | Coded vs decoded `resumen` | D-037, D-039, H5 | S3 |

Emergent sprints take the next free ID: backbone work continues the S0–S13 sequence at
S14+, probes take S91+.

## Decision gates

| Gate | After | Question | If no |
|---|---|---|---|
| G1 | S2 | Does BM25 fall under L1 variation? | Reframe before S3; re-scope O4 |
| G2 | S5 | Does the structured/lexical ranking invert? | Method contribution moves from S11 to S10 |
| G3 | S8 | ~~Did the balanced dose set arrive?~~ **It did** (2026-09-17, recorded 2026-09-27). Re-read: is H4 identifiable on it? | The two blocked interactions stay unclaimed; coverage is 7 concepts, 4 on dev, so a clustered interval is near-useless and the paired within-leaf slope carries the claim |
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
| 2026-09-17 | S2 | planned → **active** | Design frozen at `1f126f0`; entry state verified in the tree. Structured pipeline ported from `research/structured-retrieval` by file checkout (D-026), `bm25_unigram` added as a text-only arm (D-010), 8-day time-box |
| 2026-09-17 | S2 | design amended | A1 fifth arm `structured_pipeline_rules_valuenorm__OE` (Stage-3 decimal-comma defect, 1,640 leaves); A2 work item 1's exact-recovery test → never-misread; A3 port file list |
| 2026-09-17 | S2 | design amended | A4 harness repairs needed to run items 3–4; A5 run bookkeeping (indexes rebuilt, S1 runs archived, one commit for all 15 runs) |
| 2026-09-17 | S2 | report written | All 7 exit criteria met; G1 read **proceed**, pending César's ruling on `bm25_unigram` identity 0.8870 (D-027). Structured-overtake refuted for rules. `done` withheld until `/audit S2` in a fresh session |
| 2026-09-17 | S2 | audited fresh | **PASS WITH FINDINGS** (`SPRINT_S2_AUDIT.md`): 9 findings, 3 major. Tables regenerate byte-identically and the headline deltas recompute from the raw lists; the gate reading did not survive. All nine resolved in §Audit response |
| 2026-09-17 | S2 | active → **done** | G1 re-read under the frozen design: **ambiguous** — `bm25_unigram` 0.8870 (clustered [0.7996, 0.9242]) and `bge_m3_colbert` 0.9861 (clustered [0.9463, 1.0000], straddling), L1 branch *proceed*. D-027 rejected, D-030 accepted (thresholds read on the clustered interval), D-028/D-029 amended. New generated tables: `identity_misses.md`, `colbert_vs_bm25.md`, `tiebreak.md`; design amendment A6 |
| 2026-09-27 | S3 | planned → **active** | Design frozen at `8353cf7`; entry state verified in the tree. D-012 closed on the ten-method set; dev-only reading of the plan's `resumen→texto` scope recorded as a design constraint; first work item is the 2026-09-27 intake under D-033 |
| 2026-09-27 | S8 | — | Not a transition: the E3 balanced dose set was found to have arrived upstream on 2026-09-17 (`4d10af2`) and gone unrecorded here for ten days. S3 takes it in; S8 moves `blocked` → `planned` when that intake lands |
| 2026-09-27 | S8 | blocked → **planned** | S3 work item 2 took the E3 delivery in and verified it: nested ladder on all 600 leaves, 600 per rung, every claim re-derived (23 tests). D-009 **Delivered**. G3 has no absence left to rule on and is re-read as an identifiability question; three limitations recorded, of which the binding one is 7 concepts / 4 on dev |
| 2026-09-28 | S3 | report written | All 13 exit criteria met; 177 of 177 runs resolve; 11 generated tables regenerate byte-identically; suite 971 passed, 1 xfailed. Ten amendments, four of them unplanned harness repairs (H5–H7 and the batching fix). Headline findings are negative or mechanistic: the operating point **transfers** (D-036), OE is **15 points less verbatim** than OEB (D-037), and the oracle advantage is **exactly** the 776 undecidable queries. `done` withheld until `/audit S3` in a session that did not do the work |
| 2026-09-28 | S3 | audited fresh → **reopened** | **FAIL** (`SPRINT_S3_AUDIT.md`): 11 findings — 1 critical, 4 major, 6 minor. The headline numbers trace and all three result directories regenerate byte-identically, but the reported p-values (0.845 / 0.417) cannot be reproduced from committed code (F1). Exit criterion 5 is not met (F4). S3 stays **active** until every finding is resolved and a fresh audit passes |
| 2026-09-28 | S3 | findings resolved | All 11 findings addressed (§Audit response): nine fixed, F10 and F11 accepted with reasons. Generators now compute their prose, guarded by `tests/test_generated_prose.py`. Making the prose computed exposed three more misstatements, all corrected (query length, surface shape, sparse gold ranks). The mechanism and tuning claims are narrowed to what the design allows. Design amendment A11; D-036/037/038 amended. No run and no retrieval figure changed. **Re-audit pending** in a fresh session |
| 2026-09-28 | S3 | re-audited fresh | **PASS WITH FINDINGS** (`SPRINT_S3_AUDIT.md`, above the FAIL record): 9 findings, 2 major. Every headline figure, both sweep contrasts (independent seed) and byte-identical regeneration reproduced. Major: `build_results_s3.py` outside the prose guard (F1); `replication.md` without D-032's ceiling and headroom (F2) |
| 2026-09-28 | S3 | active → **done** | All nine re-audit findings fixed (§Audit response, Re-audit); design amendment A12, D-036 second amendment. Ceilings now per indexed field (oracle arms 1.0000 / 0.9972); the transferred point is the unique argmax in 3 of 6 cells plus one exact tie. No run and no retrieval figure changed. Suite 984 passed, 1 xfailed |
| 2026-09-28 | S3 | audited fresh (third) | **PASS WITH FINDINGS** (`SPRINT_S3_AUDIT.md`, at the top): 3 minor, none critical or major. Headline figures, both sweep contrasts, per-commit run counts and byte-identical regeneration of all 11 tables reproduced. All three resolved (§Third audit): identity ties stated as ties, `transferability.md` gains n scored / excluded, ceiling and headroom, the `src/` diff qualified as retrieval-path. Design amendment A13. No run and no retrieval figure changed; status stays **done** |
| 2026-09-28 | S91 | → planned → **active** | Emergent probe from D-039. Design frozen at `09d11f7`; entry state verified in the tree. Three paired renderings of dev `resumen` (coded, stripped, decoded) × ten arms; shared-words rule for TRABAJO `-`; 3-day time-box; stops if any retriever, builder or index must change (S9 territory) |
| 2026-09-29 | S91 | report written | 20 runs clean at `cf92bc8`, coded reused by recorded diff; 5 generated tables. P1 supported for both BM25 arms, not for TF-IDF; P2 supported for `bm25_unigram`, not for `bm25_unigram_params` (interval excludes 0, Holm p 0.0700, gain in 6 of 26 concepts). Codes mislead lexical arms at concept level; decoding lifts item-level for every arm but TF-IDF. Amendments A2, A3. `done` withheld until `/audit S91` in a fresh session; exit criterion 7 awaits César's ruling on D-039/D-037 |
| 2026-09-29 | S91 | audited fresh → **reopened** | **FAIL** (`SPRINT_S91_AUDIT.md`): 8 findings — 1 critical, 2 major, 5 minor. Retrieval numbers, CIs, flip counts and regeneration all reproduce; the freeze is clean. Critical: the coverage comparison behind "decoded OE reaches OEB's coverage" and the proposed D-037 amendment mixes samples (94.41 % on P vs 94.10 % on all OEB pairs); on all dev, decoded coverage is 89.83 % [83.43, 92.99] (F1). Exit criteria 4c and 7 not met. No re-run needed. S91 stays **active** until every finding is resolved and a fresh audit passes |
| 2026-09-29 | S91 | findings resolved | All eight audit findings resolved (report, Audit response). F1: coverage compared on S3's own population; decoded OE does not reach OEB's coverage, D-037 proposal rewritten. F2: every table stamps the runs and files it reads. F3: finding 1 names `bm25_unigram`. F4–F6: T2's rule, T5's rare share (85.6 %), the zero-delta claim withdrawn. F8: ceilings at both levels everywhere; every parent ceiling 1.0. F7: `tests/test_report_traceability.py`. No accuracy moved; no run re-done. S91 stays **active** until a fresh re-audit passes |
| 2026-09-29 | S91 | re-audited fresh → findings resolved | **PASS WITH FINDINGS** (`SPRINT_S91_AUDIT.md`, above the first): 3 major, 5 minor. Every T2 cell, headline interval, ceiling and T5 figure reproduces; full suite 1059 passed, 1 xfailed; tables byte-identical on regeneration. F1 (waiver recorded as design A4), F2 (params-arm parent move not a detected gain, Holm p 0.0896), F4–F8 (neural rows exploratory; stratum, population and in-sample wording; header) fixed in the report. **F3 open: exit criterion 7 waits on César's ruling on D-039/D-037.** S91 stays **active** until it lands |
| 2026-09-29 | S91 | active → **done** | Re-audit F3 closed: César accepted the proposed D-039 and D-037 amendments, appended to `DECISIONS.md`. Exit criterion 7 met; all nine exit criteria met. Still open under D-039: whether future `resumen` results are reported coded, decoded or both. D-040 and D-041 raised, not decided |
| 2026-09-29 | S4 | planned → **active** | Design frozen at `dd407c6`; entry state verified in the tree. Fifteen arms (ten indexed, two RRF, three CE-blend; PRF excluded, César) × nine single types on dev, paired against identity on the same leaves; 17 new runs, 13 reused; P1–P5 registered; thin-slice request issued as a work item |
| 2026-09-29 | S4 | report written | All 8 exit criteria met; 17 new runs clean at `36bed7a`, 13 reused by computed diff; T1–T7 byte-identical. P1–P5: 14 of 15 tests supported, 1 not supported (P5 ColBERT, which never leaves the concept). H1 supported on dev; H2 split: L1 and `reorder` clauses hold, L3 as a layer does not (`template_paraphrase`). Amendments A1–A3; P7 found and excluded; D-042, D-043. `done` withheld until `/audit S4` in a fresh session |
