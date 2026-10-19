# STATE — `research/synthetic-oe`

The single living status file for this branch. Always current, under the contract budget (≤ 12 KB). Dated
snapshots belong in `archive/` — the history up to 2026-10-19 is
[`archive/STATE_2026-10-19.md`](archive/STATE_2026-10-19.md), verbatim. Updated at every sprint transition and
whenever something blocks.

**Last updated:** 2026-10-19 (v2 re-runs of S4–S9 and S11 done and audited; D-061 accepted; S14 freezing) ·
**Updated by:** Claude

---

## Where we are

**The 2026-10-16 delivery is taken in and the closed sprints are re-run on it** ([`DELIVERIES.md`](DELIVERIES.md),
`tests/test_intake_20261016.py`). Upstream repaired 163 broken template paraphrases (**P10**,
[`DATASET_DEFECTS.md`](DATASET_DEFECTS.md)) and delivered **v2** of STACKED, SINGLE, dose and isolated (same
records, only `text` changed on 2,039 / 241 / 547 / 348 queries), **`bt_texto`** (4,670 back-translated gold
`texto`s, OPUS-MT, one per STACKED-P leaf, 40 dev / 39 test concepts) and the **STACKED-P filter**
(`exclusions.stacked_p`, 324 keys). **D-061 accepted** (César, 2026-10-19): v2 is the reference for S12 and the
re-runs, v1 stays beside it as sensitivity, closed sprints are amended, not reopened. Every re-run is an amendment
with its own clean runs, `results/Sx/v2/` and `comparison.md` (v1 beside v2, paired draws), a report section and a
fresh-context audit: S4 A6, S5 A4, S6 A8, S7 A8–A10 (also STACKED-P), S8 A8, S9 A13–A15, S11 A7–A10 — **seven
audits, all PASS WITH FINDINGS, resolved**. 72 + 20 + 25 clean v2 runs.

**What moved on v2.** No registered reading of S4–S7, S9 or S11 (21 / 15 / 21 / 44 / 11 unchanged); S8's X2 for
`bm25_unigram` and `bge_m3_dense` crosses the α boundary (supported → not supported, Holm 0.0486 → 0.0540,
estimates unmoved), H4 *partly supported* on both. K2 − ColBERT on stacked +0.3143 → +0.2967 (−0.0176 [−0.0301,
−0.0029], one part in eighteen), the method contribution still *established on dev*; ColBERT recovers +0.0152 on
stacked; K2 on the ladder −0.0091 [−0.0171, −0.0018] (D-053); the lexical arms are unmoved; S9's c* moves by
hundredths and its bins move with the repaired text.

**S14 (BT, backbone)** — César ruled 2026-10-19: backbone, not probe; the oracle arms (readers of `parameters`,
which on BT hold the gold's values, `DELIVERIES.md`) are out of every S14 test and of S12's BT reading, printed as
bounds with the asymmetry stated; no regenerated BT is requested. Design
[`sprints/SPRINT_S14_DESIGN.md`](sprints/SPRINT_S14_DESIGN.md) freezes with those two conditions; then the P-fixing
stage from the S7 A8 runs, 21 BT runs, tables, report, audit.

**S12** is registered in [`RESEARCH_PLAN.md`](RESEARCH_PLAN.md) §S12: v2 digests, STACKED-P, `bt_texto` (test
side, once), the S14 pair list, model/prompt stamps on every LLM run.

## Sprints

| ID | Status | Documents | One line |
|---|---|---|---|
| S0–S3 | done | [`archive/STATE_2026-10-19.md`](archive/STATE_2026-10-19.md) ("Done", "In flight", "Latest results"); [S3 report](sprints/SPRINT_S3_REPORT.md), [audit](sprints/SPRINT_S3_AUDIT.md), [results](results/S3) | Harness, splits, 15 S2 runs, S3 ceilings / replication (BM25 0.6394 on OE `resumen`, does not replicate) / sweep / overlap |
| S4 | done, A6 v2 | [design](sprints/SPRINT_S4_DESIGN.md) `dd407c6`, [amendments](sprints/SPRINT_S4_AMENDMENTS.md), [report](sprints/SPRINT_S4_REPORT.md), [audit](sprints/SPRINT_S4_AUDIT.md), [results](results/S4) | E1 Track A, 15 arms × 9 types; H1 supported, H2 split; 21 of 21 readings unchanged on v2 |
| S5 | done, A4 v2 | [design](sprints/SPRINT_S5_DESIGN.md) `432b39e`, [amendments](sprints/SPRINT_S5_AMENDMENTS.md), [report](sprints/SPRINT_S5_REPORT.md), [audit](sprints/SPRINT_S5_AUDIT.md), [results](results/S5) | Track B rules pipeline; H3 refuted on dev, G2 no (D-046); 15 of 15 unchanged on v2 |
| S6 | done, A8 v2 | [design](sprints/SPRINT_S6_DESIGN.md) `8abf24f`, [amendments](sprints/SPRINT_S6_AMENDMENTS.md), [report](sprints/SPRINT_S6_REPORT.md), [audit](sprints/SPRINT_S6_AUDIT.md), [results](results/S6) | Mediation and mixed models; H1 for seven arms, H5 restated (D-049), D-048; 21 of 21 unchanged on v2 |
| S7 | done, A8–A10 v2 | [design](sprints/SPRINT_S7_DESIGN.md) `5e89809`, [amendments](sprints/SPRINT_S7_AMENDMENTS.md), [report](sprints/SPRINT_S7_REPORT.md), [audit](sprints/SPRINT_S7_AUDIT.md), [results](results/S7) | E2 stacked headline; no arm keeps half its item accuracy, BM25 loses the concept (D-050), density law not established (D-051); unchanged on v2 and on STACKED-P |
| S8 | done, A8 v2 | [design](sprints/SPRINT_S8_DESIGN.md) `4f62d5a`, [amendments](sprints/SPRINT_S8_AMENDMENTS.md), [report](sprints/SPRINT_S8_REPORT.md), [audit](sprints/SPRINT_S8_AUDIT.md), [results](results/S8) | E3 dose ladder, H4 *partly supported* (D-053, D-054); two X2 cells cross α on v2 |
| S9 | done, A13–A15 v2 | [design](sprints/SPRINT_S9_DESIGN.md) `587e466`, [amendments](sprints/SPRINT_S9_AMENDMENTS.md), [report](sprints/SPRINT_S9_REPORT.md), [audit](sprints/SPRINT_S9_AUDIT.md), [results](results/S9) | Track C: HyDE harms, rewriting harms dense arms, C recovers number-word damage, IDF cap (D-055–D-057); 44 of 44 unchanged on v2 |
| S10 | **blocked** | [request](requests/S10_TRAINING_SET.md), amended 2026-10-18 (repaired menus, disjoint from BT lists, no BT in training) | Waits on a training set from `bc3cat-dataset` whose menus are disjoint from every delivered query |
| S11 | done, A7–A10 v2 | [design](sprints/SPRINT_S11_DESIGN.md) `931ee0c`, [amendments](sprints/SPRINT_S11_AMENDMENTS.md), [report](sprints/SPRINT_S11_REPORT.md), [audit](sprints/SPRINT_S11_AUDIT.md), [results](results/S11) | Track E two-stage: K2 beats ColBERT on stacked and the blind ladder, *established on dev* (D-059); EC3 accepted as not met on dev, the v2 runs stamp model and prompt (A8); H8 ColBERT batch dependence (D-060) |
| S12 | planned | [`RESEARCH_PLAN.md`](RESEARCH_PLAN.md) §S12 | One-shot test evaluation on v2, STACKED-P, `bt_texto`; registration list there |
| S14 | **freezing** → active | [design](sprints/SPRINT_S14_DESIGN.md) | External rendering (BT) paired leaf for leaf against STACKED-P v2; B1–B4 |
| S91 | done | [report](sprints/SPRINT_S91_REPORT.md), [results](results/S91) | Coded vs decoded `resumen` (D-037, D-039) |

## Environment and harness

- **Checkout.** Main checkout only (no worktrees; `run_context` refuses them). Container `bc3cat-s3` mounts it at
  `/work`; `host.docker.internal` reaches the BGE-M3 server (8800) and ollama (11434) again (2026-10-18), no hosts
  edit. **Never edit `src/` or `configs/` while a batch runs**: the stamp reads git status at save time (S7 A9,
  S11 A9).
- **Line endings (H5).** `.gitattributes` pins `*.py`, `*.yaml`, `*.sh`, `*.md`, `*.json` to LF (`4ef19aa`,
  2026-10-19); the CRLF working copies were re-checked out, so file digests equal the committed blobs' (`SPLITS.md`
  `8d520eb4…` as S11 recorded) and `test_golden_fixture` passes. `check_run_inputs.py` resolves a config modulo
  line endings (a note, not a failure): 557 of 557 OE runs resolve, 180 so. The remaining CRLF working copies are
  `.csv` / `.txt` / `.tex` under `analysis/`, `eval/`, `docs/reviews/`, none digested.
- **Archived runs.** `runs/_archive/dirty/2026-10-18/` (seven dirty or partial attempts, S7 A9 / S11 A9–A10) is
  kept, not deleted (César, 2026-10-19; D-019). `runs/_archive/S2/SHA256SUMS` was rewritten on 2026-10-01, so S5's
  T7 last line changes on regeneration (`f5705d08…` → `cb599ae3…`); César's to re-commit.
- **Generators.** `results/` is generated, never typed (prose guard, traceability test); each v2 mode generated
  twice, clean at its commit, hashes in `logs/v2/*.sha256`. The S9 generation caches are one file per set and
  need seeding for a new base (A14). `index/*/meta.json` still omits the ML stack (H4).
- **Audits.** The seven v2 audits were run by fresh-context subagents from the implementing session; César asked
  (2026-10-19) that at least S8's and S11's v2 amendments be repeated with `/audit` in a separate session. The
  others stand on the subagent audits.
- **Suite** at `70f2776`: 2,096 passed, 2 skipped, 1 xfailed.

## Blocked / waiting

- **S10** on the upstream training set (above). **Real-query anchor** (S90): not requested, off the path.

## Next action

1. Freeze S14 (header, SPRINTS, plan); P-fixing stage from the S7 A8 runs (`results/S14/pairs_stacked_p.md`,
   listed in the amendments file) before any BT run is read; the 21 BT runs (`logs/S14/run_s14.sh`), the BT family
   cache and the extractor's regeneration check; tables, report, audit.
2. `/audit` of S8 A8 and S11 A7–A9 in a separate session.
3. S12 registration (its design) once S14 is done.

## Open decisions

Searched by ID in [`DECISIONS.md`](DECISIONS.md). Accepted 2026-10-19: **D-061**. Still proposed: **D-028**
(tie-free reading), **D-029** (ColBERT as the L1 reference). The per-sprint roll of earlier decisions is in the
archive snapshot.
