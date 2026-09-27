# STATE — `research/synthetic-oe`

The single living status file for this branch. Always current, under 2 KB. Dated snapshots
belong in `archive/`. Updated at every sprint transition and whenever something blocks.

**Last updated:** 2026-09-27 (S3 work items 1–4 done) · **Updated by:** César

---

## Where we are

**Active sprint: S3** — frozen at `8353cf7`, work items 1–4 done. **S2 is done**
(2026-09-17). **Gate G1 read: ambiguous** — the L1 branch says proceed, but two gated arms fail
the identity branch under the design as frozen: `bm25_unigram` 0.8870 (clustered [0.7996,
0.9242]) and `bge_m3_colbert` 0.9861 (clustered [0.9463, 1.0000], straddling 0.98). S3 inherits
those ceilings; under D-032 they are read as per-method ceilings, not as a gate.

## Done

Release received and validated (`INTAKE.md`, 2026-09-08); proposal and plan written. Each
sprint below was audited in a fresh session, returned PASS WITH FINDINGS, and had every finding
resolved before it was marked done — see its `SPRINT_XX_AUDIT.md`.

- **S0 2026-09-15** — `data/` repopulated and re-verified, `SPLITS.md` (seed `20260915`), 77
  configs naming collection and retriever, E3 issued.
- **S1 2026-09-16** — five notebooks on one resolver, gold read from the query record, batched
  scoring. The OEB fixture reproduces to ten decimals: the migration moved no number.
- **S2 2026-09-17** — 15 stamped runs, 5 methods × 3 query sets on OE dev. Tuned BM25 falls
  under L1; the rules pipeline overtakes it in none of 8 contrasts; ColBERT inverts in 3 of 4.

## In flight

- **S3 open, frozen at `8353cf7`** ([design](sprints/SPRINT_S3_DESIGN.md), amendments A1–A4).
  **Work items 1–2 done** 2026-09-27; 3–11 open. D-012 closed on the ten-method set.
- **Runs in the sprint's own container, `bc3cat-s3`** — main checkout → `/work`, libraries
  identical to `bc3cat-s2`, papermill installed by hand; `logs/S3/` holds the executed notebooks.
  It reports *unhealthy* because the image expects JupyterLab and we run `sleep infinity`.
- **Worktree hazard closed** 2026-09-27: `run_context` now refuses a linked worktree, and the two
  containers that mounted one as `/work` are gone or repointed. D-018 amended.
- **Both upstream deliveries taken in** — see [`DELIVERIES.md`](DELIVERIES.md) for what was
  verified. Item-level scoring excludes duplicate-gold queries from work item 3 on (D-033).
- **[`DATASET_DEFECTS.md`](DATASET_DEFECTS.md)** — every corpus defect, classified by who fixes it.

## Incident — 2026-09-14

`data/`, `index/`, `runs/`, `logs/`, `hf-cache/` emptied by an agent session; rebuilt in S1.
[`archive/INCIDENT_2026-09-14.md`](archive/INCIDENT_2026-09-14.md) · D-019, D-020.

## Blocked / waiting

- **Real-query anchor** (200–500 Telice queries) — not requested. Off the path.

## Next action

S3 work item 5 — mint the six missing OE configs (`tfidf_unigram_phrases_replace`, `dense_gte`,
`dense_gte_instrQ`, `dense_es_hiiamsid`, `bge_m3_dense`, `bge_m3_sparse`), each declaring
`collection` and an explicit `retriever` block, and build their indexes over the full corpus
(D-023). Before that GPU block:
resolve and warm the E5, GTE and hiiamsid model revisions, since `hf-cache/hub` holds only
`BAAI/bge-m3`. ColBERT is the L1 reference (D-029, amended); the identity ceilings above stand.

## Latest results

Two directories, deliberately kept apart. **Every item-level figure is quoted with its scored n**
(D-033 note): the same run has one value on all queries and another on the duplicate-free
population, and both are correct about their own.

- [`results/S2/`](results/S2) — **what S2 reported.** Tuned BM25 falls under L1 (item Acc@1 0.608
  `unit_conversion`, 0.098 `num_to_text`, dev); the rules pipeline overtakes it in no contrast;
  ColBERT holds best under L1 and stacking, its advantage over *tuned* BM25 under
  `unit_conversion` being +0.083 [−0.010, +0.177], the one L1 contrast that does not invert.
- [`results/S3/s2_rescored/`](results/S3/s2_rescored) — **the control S3 inherits**, item-level on
  duplicate-free golds (`build_results_s3.py`, no retrieval, regenerates byte-identically). L1 and
  stacked move in the third decimal and no S2 conclusion turns on it. Identity moves materially and
  only for text-only methods: **`bge_m3_colbert` 0.9861 → 0.9998**, because 484 of its 492 identity
  misses were undecidable from the indexed field. `bm25_unigram_params` is unchanged at 0.9994 with
  **zero** duplicate-gold misses — the oracle signal of D-010, not robustness. Neither is a
  re-reading of G1 (D-032). `stacked_by_dose.md` re-stratifies on the corrected
  `texto_modification_count`: of the 730 dev queries S2 called dose 5, **193** show five
  modifications in the TEXTO, so S2's by-dose strata were misattributed, not merely uncertain. The
  cells' concept counts fall 27 → 17 → 8 → 2 → 1 with dose, which is the dose/family confound E3
  exists to remove — H4 is answered in S8, not here.

## Open decisions

See `DECISIONS.md` (`Open`). **D-012 (method scope on OE) is closed** — 2026-09-27, ten arms,
full `k1`/`b` re-sweep; it gated S3 and no longer does. Closed in S1:
**D-016**, **D-022**. Recorded in S1: **D-023** (index over the full corpus), **D-024**
(`OEB#`), **D-025** (the stacked dose is one lower than `modification_count` says — it reaches
H4), and an amendment to **D-008** adding `texto` as the fourth query set. Recorded in S2: **D-026** (structured
pipeline ported by file checkout, not merged), **D-030** (a threshold on an Acc@1 is read
against the concept-clustered interval). Rejected in S2: **D-027** (re-defining G1's stop rule
after the result). Still Proposed, amended: **D-028** (tie-free reading for every family),
**D-029** (ColBERT as the L1 reference for S3).
