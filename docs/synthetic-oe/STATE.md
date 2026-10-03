# STATE — `research/synthetic-oe`

The single living status file for this branch. Always current, under 2 KB. Dated snapshots
belong in `archive/`. Updated at every sprint transition and whenever something blocks.

**Last updated:** 2026-10-02 (**S9 active**) · **Updated by:** Claude

---

## Where we are

**S9 is active** (2026-10-02; Track C, query-side normalisation and rewriting, H6; [design](sprints/SPRINT_S9_DESIGN.md) frozen at `587e466`, [amendments](sprints/SPRINT_S9_AMENDMENTS.md) empty). H6 is tested paired on 2,691 dev leaves rendered five ways (identity `texto`, coded `resumen`, single, L2, stacked), on the untransformed query's lexical coverage. Transforms: a catalogue-only canonicaliser, HyDE and LLM rewrite (`qwen2.5:14b`, local ollama), and the S91 decoder; plus an IDF guard and a `phi4` extractor in `rules_valuenorm`. 120 runs, 44 blind tests. Effort 3 weeks.

**S8 is done** (2026-10-02; E3 balanced dose design, H4; [design](sprints/SPRINT_S8_DESIGN.md) frozen at `4f62d5a`, [amendments](sprints/SPRINT_S8_AMENDMENTS.md) A1–A7, [report](sprints/SPRINT_S8_REPORT.md), [audit](sprints/SPRINT_S8_AUDIT.md), [results](results/S8)). 36 runs clean on 328 dev ladder leaves in 4 OEB concepts. Accuracy falls with every added edit for all seven arms (X3). X1 is supported for `dense_e5` only, not robust, and is floor-bound for most arms. X2 is supported for six arms, but none clears the registered draw-noise bar under both scorings, so no excess is attributed to interaction. **H4 is not resolved on this design**; the design's label reads *partly supported*. Two audits **PASS WITH FINDINGS**, all resolved; the second (F1) withdrew a post-hoc reading of X2 (T13), which now only motivates S12's signed reference. D-054 accepted as revised twice (César, 2026-10-02): H4 is not established on dev; S12 tests X2 against a signed reference registered in advance.

**S7 is done** (2026-10-01; E2 stacked headline and stratifications; [design](sprints/SPRINT_S7_DESIGN.md) frozen at `5e89809`, [amendments](sprints/SPRINT_S7_AMENDMENTS.md) A1–A7, [report](sprints/SPRINT_S7_REPORT.md), [audit](sprints/SPRINT_S7_AUDIT.md), [results](results/S7)). 18 runs on the corrected stacked set, all clean. No arm keeps half its item accuracy stacked (ColBERT highest, 0.4128 tie-free). W1 (gap widens) holds for all 7 arms; W2 holds for the encoders but not for BM25, whose **parent** level collapses (0.9980 → 0.2931). H1 is partly supported on stacked. The sibling-density law is not established: 1 of 7 supported; descriptively it holds within OEB for 5 of 7, not separated from the dose. Audit **PASS WITH FINDINGS**, 2 major and 5 minor, all resolved: A5–A6 add n excluded, concept counts and query-level CIs to T2–T7 (generated at `47cbbbd`, byte-identical twice), A7 corrects A1/A3, the rest is prose. D-050 accepted; D-051 amended after the audit (rationale restated), accepted by César.

**S6 is done** (2026-10-01; statistical analysis and mediation, H1 / H2 / H5; [design](sprints/SPRINT_S6_DESIGN.md) frozen at `8abf24f`, [amendments](sprints/SPRINT_S6_AMENDMENTS.md) A1–A7, [report](sprints/SPRINT_S6_REPORT.md), [audit](sprints/SPRINT_S6_AUDIT.md)). Audit **PASS WITH FINDINGS**, 2 major and 4 minor, all resolved: A7 adds n excluded to T2–T7 and the tie-free query-level CI to T1 (columns only, no earlier cell moved; generated at `c2ecdde`, byte-identical twice); the rest in prose. 15 runs on `single_l2_texto`; 21 tests, 16 supported, 5 not, 0 contradicted, tie-free. H1 supported for all seven non-floor arms; H2's L1 clause replicated blind on 9 L2 concepts, its L2 clause holds for BM25 (not robust to D-004) and not for ColBERT; H5 restated (D-049, amended after audit F2): overlap explains more of BM25's damage than of BGE-M3's, is not shown to explain most of it, and the L1 : L3 ratio is not shown to reach 10. M0's additive concept intercept does not hold for bag-of-words (D-048).

**S5 is done** (2026-09-30; E1 ablation, Track B, H3 and G2; [design](sprints/SPRINT_S5_DESIGN.md) frozen at `432b39e`, [amendments](sprints/SPRINT_S5_AMENDMENTS.md) A1–A3, [report](sprints/SPRINT_S5_REPORT.md), [audit](sprints/SPRINT_S5_AUDIT.md)). Audit **PASS WITH FINDINGS**, 1 major and 3 minor, all resolved in prose and A3; no run or table changed. The published rules pipeline ranks below deployable BM25 under L1, tie-free (Q1 contradicted pooled and on `unit_conversion`): **H3 refuted on dev for the published method**. The oracle bound is not detected beating BM25 on pooled L1 (Q2 not supported) but does on `num_to_text` (9 concepts ‡). **G2 reads no**: S10 before S11 (D-046). Superseded runs archived via `utils/archived_runs.py` (D-047).

**S4 is done** (2026-09-30; E1 ablation, Track A). First audit FAIL, reopened, all nine resolved (A4). Re-audit **PASS WITH FINDINGS**, 1 major and 5 minor, all resolved (A5: columns only). No run changed ([design](sprints/SPRINT_S4_DESIGN.md), frozen `dd407c6`; [amendments](sprints/SPRINT_S4_AMENDMENTS.md) A1–A5, moved out under D-045; [report](sprints/SPRINT_S4_REPORT.md), [audit](sprints/SPRINT_S4_AUDIT.md)). 15 arms × 9 single types on dev, paired against identity: H1 supported on dev (the gap widens for both BM25 arms and ColBERT); H2 split, L1 and `reorder` as predicted, L3 not a coherent layer. Found P7 (one dev query renders a sibling's `texto`; 2 more on test), excluded at item level. Took in `OE_P7_test_exclusion.json` (S12) and `OE_single_l2_texto.json` (S6, 9 / 9 / 8 dev concepts), both unwired (D-043). **S91 is done** (2026-09-29; probe, coded vs decoded `resumen`, frozen at `09d11f7`) — first audit FAIL, reopened, all eight resolved; re-audit **PASS WITH FINDINGS**, all eight resolved (design A4); D-039 and D-037 amendments accepted by César ([design](sprints/SPRINT_S91_DESIGN.md), [report](sprints/SPRINT_S91_REPORT.md), [audit](sprints/SPRINT_S91_AUDIT.md)). The catalogue's parameter codes mislead `bm25_unigram` at concept level (P2 not supported for `bm25_unigram_params`), and decoding them lifts item-level accuracy for both BM25 arms (P1), and, exploratory, for ColBERT (0.0284 → 0.4826 on P). It answers D-039's open question: a catalogue-only decoder is viable in-sample (80.9 %). Ruled 2026-09-29: `resumen` results are reported coded **and** decoded (D-039, second amendment); `resumen`-identical siblings are excluded at item level (D-040, 9,348 dev leaves; not yet in the harness). D-041 (document-side expansion probe) declined; its two questions go to S9. **S3 is done** (2026-09-28) — first audit FAIL, reopened, re-audit **PASS WITH FINDINGS**, all nine resolved; a third audit **PASS WITH FINDINGS**, three minor, all resolved ([audit](sprints/SPRINT_S3_AUDIT.md), [report](sprints/SPRINT_S3_REPORT.md)). **S2 is done**
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
- **S3 2026-09-28** — ten arms' identity ceilings, the `resumen` replication, the 150-cell sweep,
  overlap. First audit **failed** (untraceable p-values); passed on re-audit.
- **S4 2026-09-30** — 15 arms × 9 single types, paired against identity. H1 supported on dev; H2
  split: L1 and `reorder` as predicted, L3 not a coherent layer. First audit **failed** (T4 mixed
  samples); passed on re-audit.
- **S5 2026-09-30** — Track B: the published rules pipeline under the nine single types. H3 refuted on
  dev for the published method; G2 reads no (D-046).
- **S6 2026-10-01** — L2w taken in and run; mixed models, overlap mediation, 21 registered tests. H1
  holds for seven arms; H5 restated (D-049 amended).
- **S7 2026-10-01** — 18 runs on the corrected stacked set. No arm keeps half its item accuracy; BM25 loses the
  concept (D-050); the sibling-density law is not established (D-051 amended after the audit).

## In flight

- **S3 closed** at `8353cf7` + amendments A1–A13. 177 of 177 runs resolve; 11 generated tables under
  [`results/S3/`](results/S3) regenerate byte-identically, all three generators under the prose
  guard; suite 984 passed, 1 xfailed. D-012 closed on the ten-method set.
- **All ten arms are indexed** over the full corpus (D-023), 70,242 docs each, every one
  `code_dirty: false`: `bm25_*` at `6336974`, `bge_m3_colbert` at `31bf1a1`, the other seven at
  `2dd653d`. The four **local dense** arms run on `transformers 4.57.6` / `sentence-transformers
  3.4.1`, not `requirements.txt`'s old pin, which cannot load GTE at all (**D-034**); the BM25 and
  BGE-M3 arms never touch it and keep their S2 stamps. GTE follows the config — `gte-multilingual-base`
  for both arms (**D-035**) — and their `embeddings.npy` are byte-identical, so they differ only at
  query time.
- **Runs in the sprint's own container, `bc3cat-s3`** — main checkout → `/work`, papermill and the
  pinned stack installed by hand, model cache in the bind-mounted `hf-cache/`; `logs/S3/` holds the
  executed notebooks and the build runner. It reports *unhealthy* because the image expects
  JupyterLab and we run `sleep infinity`. **`index/*/meta.json` does not stamp the ML stack**
  (defect H4), so those versions live only in the runner's captured output.
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

S9 work item 1 **done** (`25965f6`, `87a85b8`): 17 S9 query sets registered; `texto_u` / `resumen_u` written (2,691 dev leaves), paths proven; D-040 in `utils/exclusions.py`, its counts regenerated exactly (25,498 scored on dev); ollama client and prompts committed (SHA-256 hyde `ed5de490`, rewrite `6811f1a9`); regeneration 98 / 100 (HyDE), 99 / 100 (rewrite), recorded as A1. Work item 2: C done (`10578be`; identity on all 70,242 corpus texts, so Z2 holds by construction), canon sets written (`5e5d124`); HyDE/rewrite generating in `bc3cat-s3` (`logs/S9/generate.out`, resumable cache). Work item 3 done (`ad2f78f`): D-041 diagnostic in `utils/idf_diagnostic.py` (T5 prints it), `idf_cap_df` in both BM25 builders, two `__idfcap-1200__OE` indexes built clean; the cap reaches 468 of 682 / 770 of 1,017 vocabulary terms, not only the codes (run as frozen). Work item 4 code done (`1d27b40` unmodified checkout, `35a23a9` adaptation): `structured_pipeline_llm_valuenorm__OE` (phi4, `extract`, cached), pseudo-index built; its 100-query regeneration test waits for the GPU. Work item 5 batch A done 2026-10-02 (`logs/S9/run_s9_a.sh`, A2 hosts mapping): 35 C runs + 10 IDF-guard runs, all `code_dirty: false`, split dev, commit `7174392`, metrics present; `check_run_inputs.py` 325 of 325 OE runs resolve. Batches B1 (H, 35) and B2 (W, 35; extractor, 5) done by 2026-10-03 at `d24e7c7` / `58e950f`, all clean, metrics present: **work item 5 done, 120 runs**; `check_run_inputs.py` 400 of 400 OE runs resolve. Rewrite sets: 7 fallbacks, all A3 truncations; extractor regenerates 100/100 (A4), its cache in the manifest. Next: work item 6, `build_results_s9.py`. Ollama 0.17.7 answers from `bc3cat-s3` at `host.docker.internal:11434` (checked 2026-10-02). S10–S11 remain unblocked; S12 must register its X2 signed reference and whether X1 is read before it opens. Suite: 1459 passed, 2 skipped, 1 xfailed.

**BGE-M3 server from `bc3cat-s3`, 2026-10-01:** after the Docker restart `host.docker.internal` no longer reached it; S7's second pass mapped it to `172.17.0.1` in the container's `/etc/hosts` for that pass only (A3), since restored. The next BGE-M3 run will hit the same fault until Docker Desktop is fixed.

**Docker Desktop, 2026-09-30:** it failed at start on a stale socket (`%LOCALAPPDATA%\Docker\run\userAnalyticsOtlpHttp.sock`, an undeletable reparse point). The directory was renamed to `run.stale-20260930`, not deleted and not factory-reset; Docker recreated `run` and started. The renamed directory can be removed by hand.

## Latest results

**All of S3's tables are generated, regenerate byte-identically, and type no number into their
prose** — [`results/S3/e0/`](results/S3/e0) (ceiling, replication, transferability, provenance for
169 runs), [`results/S3/overlap/`](results/S3/overlap), [`results/S3/s2_rescored/`](results/S3/s2_rescored).
Every item-level figure carries its scored n; the oracle arms are marked in every table they appear in.
Read the [report](sprints/SPRINT_S3_REPORT.md) for the findings. Its short form:

- **Identity ceiling.** For a `texto`-only method the corpus permits at most 0.9863. The oracle arms
  resolve 776 and 676 of the 776 undecidable queries; the text-only arms at their ceiling land on
  292 / 293 / 293 against a chance expectation of 292. The one-query surplus is exact-score ties
  (FAISS or `np.argpartition`, neither stable). The oracle arms' own fields cap at 1.0000 / 0.9972.
- **Replication.** Tuned BM25 0.6394 on OE dev `resumen` (n = 34,646 scored) against 0.974 on OEB
  test: does not replicate *on OE*. The cause is **not** established. Tuning was not swept on
  `resumen`, and OE's lower lexical coverage (79.38 % against 94.10 % on OEB) is descriptive only
  (D-036, D-037 amended).
- **Operating point.** Both BM25 variants keep 0.60/0.35: unique argmax in 3 of 6 cells, an exact tie
  in a fourth, no detectable gain elsewhere (p = 0.8507, 0.4250), which is not equivalence.
- **Overlap.** Numeric coverage is blind to `num_to_text` and `unit_expansion`, and this survives
  excluding both D-004 artefacts per type (D-038 amended). H5 needs two covariates.
- **`bge_m3_sparse`** cannot read back its own document (0.0501 scored). Its vectors are unnormalised
  under a raw dot product; the gold's rank on a miss has a median of 18, not "2–6".
- **`dense_es_hiiamsid`** is perfect on the decidable identity population (1.0000) and falls to
  0.0093 on `resumen` (n = 34,646 scored).

### Earlier, from S2 and its re-score


Two directories, deliberately kept apart. **Every item-level figure is quoted with its scored n**
(D-033 note): the same run has one value on all queries and another on the duplicate-free
population, and both are correct about their own.

- [`results/S2/`](results/S2) — **what S2 reported.** Tuned BM25 falls under L1 (item Acc@1 0.608
  `unit_conversion`, 0.098 `num_to_text`, dev, all queries); the rules pipeline overtakes it in no contrast;
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
  exists to remove — hypothesis H4 is answered in S8, not here.

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
