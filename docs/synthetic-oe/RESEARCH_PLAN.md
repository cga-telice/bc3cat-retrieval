# Research Plan — BC3CAT-Syn/OE

Sprint decomposition of `RESEARCH_PROPOSAL_1.md`. Companion document, not a replacement:
the proposal fixes *what is claimed and why*; this plan fixes *in what order it is
established, and what would falsify it early*.

| Field | Value |
|---|---|
| **Repo / branch** | `bc3cat-retrieval` @ `research/synthetic-oe` |
| **Upstream** | `bc3cat-dataset` @ `synthetic` (BC3CAT-Syn/OE release, commit `8998875`) |
| **Target** | *Automation in Construction* |
| **Effort** | ≈ 26 focused weeks; calendar depends on availability |
| **Sprints** | 14 (S0–S13), 4 decision gates |

---

## 0. Operating rules

These bind every sprint. They exist because the previous review cycle turned up three
distinct query samples reported as one, a numeric bonus that was dead code, and a hybrid
baseline taken from a different system — all provenance failures, none of them scientific.

1. **Provenance rule.** Every number that reaches a report or the manuscript carries a
   four-part stamp: `{run_id, config SHA, code commit, query-set SHA-256}`. A number
   without a stamp does not exist. Reports are generated from `runs/`, never typed.
2. **Split rule.** The dev/test split is declared and committed in S0, **before any run**,
   and is split **by concept**, not by leaf — otherwise Track D fine-tuning and any
   hyper-parameter sweep see siblings of the test items. No tuning, no model selection and
   no threshold setting ever touches the test split.
3. **One-shot test rule.** The frozen test evaluation runs once, in S12. Anything that
   requires re-running it invalidates the sprint that produced the change.
4. **Sprint report rule.** Every sprint closes with `docs/synthetic-oe/sprints/SPRINT_XX.md`
   stating: what ran, what the numbers are, which hypothesis moved, what is now known to be
   wrong, and what the next sprint inherits.
5. **Negative-result rule.** A sprint that falsifies a hypothesis closes successfully. The
   plan has contingency branches, not recovery plans.

---

## 1. Sprint map

| # | Sprint | Serves | Effort | Depends on |
|---|---|---|---|---|
| S0 | Reproducibility foundation and splits | all | 0.5 w | — |
| S1 | Harness adaptation to BC3CAT-Syn/OE | all | 2 w | S0 |
| **S2** | **Go/no-go probe** | **H3** | **1 w** | S1 |
| S3 | E0 controls, replication, overlap characterisation | H1, H5 | 2 w | S2 |
| S4 | E1 ablation — Track A (lexical + neural) | H1, H2 | 2 w | S3 |
| S5 | E1 ablation — Track B (structured) | H3 | 1.5 w | S4 |
| S6 | Statistical analysis and mediation | H1, H2, H5 | 2 w | S4, S5 |
| S7 | E2 stacked headline and stratifications | H1, H4 | 1 w | S6 |
| S8 | E3 balanced dose design | H4 | 1.5 w | S7 + upstream |
| S9 | Track C — query-side normalisation and rewriting | H6 | 2 w | S6 |
| S10 | Track D — learned representations | O4 | 3 w | S6 |
| S11 | Track E — two-stage architecture | O4 | 3 w | S6 |
| S12 | Frozen test evaluation and artefact release | O5 | 1 w | S8–S11 |
| S13 | Manuscript | — | 3 w | S12 |
| S✻ | Real-query anchor (parallel, gated) | validity | 2 w | external |

---

## 2. Sprints

### S0 — Reproducibility foundation and splits

**Goal.** Make every later number traceable and every later split defensible.

**Work.**
- SHA-256 manifest of the five OE files, committed; cross-checked against the digests
  recorded in `docs/synthetic-oe/INTAKE.md`.
- Concept-level dev/test split: 83 concepts partitioned stratified by subchapter and by
  family size, with the split written as an explicit concept-key list, seeded and committed.
  Development gets enough concepts to sweep on; test keeps the long tail of subchapters.
- Query-ID files per condition, versioned.
- Run/index layout decision: `index/{collection}/{method}`,
  `runs/{collection}/{queryset}/{method}` — and the migration of the 77 existing YAMLs off
  the hard-coded `collection: "OEB"`.
- **Cross-repo request issued now** for the E3 balanced dose set (S8), because it has
  external lead time.

**Exit.** `docs/synthetic-oe/SPLITS.md` + manifest + repo tag. No run has happened yet.

---

### S1 — Harness adaptation

**Goal.** Run the existing pipeline unchanged in method, changed in plumbing.

**Work.** The five breakpoints recorded in `INTAKE.md §4`:
1. gold decoupled from `item_key` → `gold_item_key` (item) and `parent_key` (concept)
   in `retrieve.ipynb` and `metrics.ipynb`; a query whose key is absent from the corpus
   must **fail loud**, never be silently dropped.
2. flat query `parameters` → `normalize_parameters_field` / `build_param_tokens` accept both
   shapes; axis labels rebuilt from `OE_concept_schema.json`.
3. three query sets per collection → loader keyed on `(collection, queryset)`, extra columns
   (`gold_item_key`, `modification_types`, `modification_count`) preserved through the
   projection.
4. path collisions with OEB → the S0 layout.
5. slices → per condition, per modification type, per `modification_count`, per subchapter,
   per family-size decile, plus the existing `has_numbers`.

**Exit.** One BM25 config runs end-to-end on all four query sets; a golden-fixture test
reproduces known OEB metrics bit-for-bit, proving the plumbing change did not move the
numbers; regression tests for the fail-loud path.

**Risk.** This is the sprint most likely to overrun. It is plumbing, and it is boring, and
everything downstream is blocked on it.

---

### S2 — Go/no-go probe ⚑

**Goal.** Answer the paper's central bet in one week, before committing three months to it.

The thesis is H3: BM25's advantage is an artefact of verbatim containment and inverts under
L1 variation. That is a bet. It is testable with three methods and four conditions.

**Work.** Three methods — tuned `bm25_unigram_params`, `BGE-M3-ColBERT`,
`structured_pipeline_rules` — on four conditions: identity, `single_unit_conversion`,
`single_num_to_text`, `all_combined`. Development split only.

**Exit.** A one-page memo answering: (i) does the identity control hit ≈1.0 for all three,
validating the harness? (ii) how far does BM25 fall under L1? (iii) does the structured
pipeline overtake it anywhere?

**Gate G1.**
- *Inversion observed, or BM25 below ≈0.85 under L1* → the plan proceeds as written.
- *BM25 holds above ≈0.95 under every condition* → the thesis is wrong in its strong form.
  Reframe before spending S3–S7: the paper becomes *"parameter-aware lexical retrieval is
  robust to rendering variation — here is why, and here is the regime where it finally
  breaks"*, which is still publishable but is a different paper. Re-scope O4 accordingly.
- *Identity control below ≈0.98* → stop. The harness or the corpus is wrong, not the
  hypothesis. Return to S1.

---

### S3 — E0 controls, replication and overlap characterisation

**Goal.** Establish the ceiling, replicate the previous study at 1.5× scale, and measure
the covariate that explains everything else.

**Work.**
- Identity `texto→texto` over the full corpus for the whole Track A set: the per-method
  ceiling, verified rather than assumed.
- `resumen→texto` over all 70,242 leaves: replication of the previous protocol on OE,
  across seven subchapters instead of one.
- BM25 `k1`/`b` re-sweep on the development split at the new query length (~74–78 tokens
  vs ~14): does the OEB operating point (0.60 / 0.35) transfer?
- **Overlap characterisation**: per-query lexical coverage and numeric coverage against the
  target, for every query set and every condition, computed exactly as in the review
  analysis (94.1 % / 99.93 % in the verbatim regime).

**Exit.** Ceiling table, replication table, transferability verdict, and the overlap
distribution per condition. That last table is on its own the quantitative answer to the
reviewers' central objection, and it is the x-axis of H5 and H6.

---

### S4 — E1 ablation, Track A

**Goal.** The robustness profile: method family × modification type, at both levels.

**Work.** Canonical Track A set (tuned BM25 variants, best TF-IDF, E5, GTE, BGE-M3
dense/sparse/ColBERT, RRF hybrids, PRF, cross-encoder reranking) over the nine
`single_<type>` conditions.

**Design constraint.** Effects are **paired deltas against the identity rendering of the
same leaves**. Raw Acc@1 comparisons across types are not reported, because applicability is
item-dependent: only items with convertible numeric parameters can receive
`unit_conversion`, so a cross-type comparison confounds the modification with the population
that admits it. Treatment-effect-on-the-treated throughout.

**Exit.** The profile matrix, δ and δ/token-distance per cell, plus the right-parent /
wrong-item error rate per cell — the metric that operationalises collapse.

---

### S5 — E1 ablation, Track B (structured)

**Goal.** Test H3 properly, not by probe.

**Work.** The three-phase extraction pipeline and the rule-based structured-matching
baselines, in realistic and oracle-extraction variants, over all conditions. Also the
parameter-availability factor: `parameters`-consuming variants are reported as oracle upper
bounds, their text-only counterparts as the deployable condition.

**Exit.** H3 verdict with effect sizes. The claim to be established or refuted: the
0.974 / 0.903 gap reported previously closes or reverses under L1 variation.

**Gate G2.** If H3 holds, S11 (two-stage architecture) becomes the method contribution and
gets priority over S10. If it fails, the method contribution must come from Track D
(learned representations) and S10 gets the budget instead.

---

### S6 — Statistical analysis and mediation

**Goal.** Turn the profile into inference.

**Work.**
- Paired bootstrap (10,000 resamples), Holm–Bonferroni and Benjamini–Hochberg.
- Mixed-effects model: random intercepts for concept and leaf; fixed effects for
  modification type, count and token distance — separating the modification's effect from
  the item family's intrinsic difficulty.
- Mediation of δ by lexical and numeric overlap (H5): how much of the lexical degradation
  survives once overlap is controlled?
- Normalised sensitivity δ / mean token distance, per layer.
- Thin types (`paraphrase` n=211, `expansion` n=206) reported with their wider intervals or
  pooled at layer level; a power note stating what those n can and cannot detect.

*Added 2026-09-29 (D-043, from S4):*
- **Intake of `OE_single_l2_texto.json`** if it has landed: the three L2 types over at most 9 / 9 / 8
  dev concepts instead of 5, after upstream's engine fix and a byte-identical regression check on the
  delivered sets (D-043 amended). If it has not landed, state 5 dev concepts as the L2 limit. Either
  way, state the grammar's ceiling (13 dev / 12 test concepts can carry an L2 rewrite at all).

**Exit.** H1, H2, H5 resolved. Figures 1–3 of the paper drafted.

---

### S7 — E2 stacked headline and stratifications

**Goal.** The realistic-regime number, and the sibling-density law.

**Work.** `all_combined` (n=4,998, counts 2–8, mode 5) across all Track A–B methods;
stratification by subchapter (OEA–OEG) and by family-size decile.

**Carried caveat.** The stacked set is not a balanced crossing: `reorder` never co-occurs,
`template_paraphrase` is in 100 % of items. E2 gives the headline; it cannot identify
interactions. This must be stated in the sprint report so it cannot quietly become an
interaction claim in the manuscript.

**Exit.** Headline table; the test of whether the collapse scales with sibling density.

---

### S8 — E3 balanced dose design

**Goal.** H4 (super-additivity), which E2 cannot answer.

**Work.** Consume the balanced compositional set requested in S0: modification counts 1–5,
randomised type mixes, `reorder` admitted. Fit degradation as a function of count, with
per-type indicators, and compare against the additive prediction from S4's isolated effects.

*Added 2026-10-01 (S8 opening; D-052, D-053):*
- **The additive reference is the E3 isolated set on the same 328 dev leaves**, not S4's isolated effects, which
  are a different population and are printed only. The isolated edits are a different rewrite draw from the
  ladder's (89 of 328 rung-1 queries match), so H4 compares edit types on the same leaves, not identical edits.
- H4 is tested against the sum of isolated effects clipped to [0, 1], since item hit is binary.
- The dev ladder has 4 concepts; readings use a concept-stratified leaf bootstrap and a 3-of-4 sign rule
  (D-053), scoped to those concepts. G3 has been answered: the set arrived; H4 is identifiable within leaf for 34 of 36 type pairs.

**Gate G3.** If the upstream set is not delivered in time, H4 drops to an exploratory
regression on the existing stacked set, with its confounding stated in the limitations, and
the sprint closes at half size. It does not block S12.

---

### S9 — Track C: query-side normalisation and rewriting

**Goal.** H6, and the practical decision rule.

**Work.** Unit and number canonicalisation before matching (the cheap, deterministic
intervention that directly targets L1 damage); parameter slot-filling from free-text
queries; HyDE-style expansion; LLM query rewriting. Each evaluated across the overlap range
measured in S3.

*Added 2026-09-29 (D-041, from S91):*
- **The S91 decoder.** It maps the catalogue's `resumen` parameter codes to values using only the code
  and its position (`build_resumen_renderings.py`). It is a normalisation step to evaluate beside the
  rewrites above, on the coded and decoded `resumen` sets that stay in the tree. Its dev fit is
  in-sample; its coverage on held-out concepts is unmeasured.
- **Protection against rare tokens.** Near-absent query tokens can hijack IDF weighting; S91 measured
  it on BM25 with the codes (`results/S91/rare_codes.md`). Candidate guards: an IDF cap or a minimum
  token length, tested on the synthetic sets as well as `resumen`, since the risk is general.
  First establish why TF-IDF, with the same tokenizer, barely shows the pattern (D-041).
- **Whether real queries carry codes** is read from S90's anchor if it arrives. Its absence does not
  block S9.

*Added 2026-09-30 (from the S5 opening):*
- **LLM parameter extraction.** The structured branch's LLM extractor (`param_extractor.py`, Phi-4 /
  Llama prompts, `research/structured-retrieval@85c3359`) was explored there on ≤ 50 queries and never
  published. It is a slot-filling candidate here, compared with normalisation and rewriting, not a
  Track B baseline. Its prompts were chosen on OEB `resumen` queries, whose concepts sit on both sides
  of OE's split: state that exposure.

**Exit.** The crossover curve: accuracy delta of expansion as a function of query-target
overlap, and the threshold below which expansion pays. A prediction to be tested, not
assumed: expansion *hurts* in the near-verbatim regime.

---

### S10 — Track D: learned representations

**Goal.** Close the collapse by training, not by architecture.

**Work.** Contrastive fine-tuning with hard negatives mined from sibling sets — the
intervention most directly aimed at the diagnosed mechanism. Development concepts only.
Reinforcement-learning-style optimisation against the item-level objective is exploratory
and time-boxed: it enters the paper only if it beats the contrastive baseline.

**Exit.** Does fine-tuning recover item-level discrimination, and does it stay robust under
L1? Cost and latency reported alongside.

---

### S11 — Track E: two-stage architecture

**Goal.** Close the collapse by architecture.

**Work.** Concept retrieval (which every family already does at 0.96–0.997) followed by
within-family parameter resolution: constrained reranking over siblings, cross-encoder over
the family, or explicit attribute matching. The diagnosis says concept retrieval is not the
bottleneck, so the effort belongs downstream of it.

**Exit.** The method contribution: accuracy, robustness profile, cost and latency against
BM25's throughput.

---

### S12 — Frozen test evaluation and artefact release

**Goal.** One evaluation, no tuning, full provenance.

**Work.** Every admitted method — Tracks A–E — evaluated once on the frozen test split.
Release: query sets with digests, split files, configs, run artefacts, analysis scripts,
code tag, DOI. MIT / CC-BY 4.0 dual licence, AI-assistance disclosure.

**Gate G4.** The split freezes here. Any later change to a method requires a documented
re-run of the whole test evaluation, reported as such.

---

### S13 — Manuscript

Figures, tables, writing, internal review, submission. Budgeted at three weeks because the
previous cycle showed that manuscript-level consistency (counts, model names, table
provenance) is where this project loses points, and it is cheaper to spend the time here
than to spend a review round on it.

---

### S✻ — Real-query anchor (parallel, gated)

**Goal.** The strongest available answer to the practical-impact objection.

**Work.** 200–500 real estimator queries from Telice, manually matched to catalogue items,
used as a validation anchor: does the method ranking measured on synthetic renderings
predict the ranking on real queries?

**Scheduling.** Starts as early as the data can be requested — it depends on people, not on
compute, so its lead time is not under the project's control. If it lands before S12 it
becomes a results section; if it lands after, it is future work; if it does not land, the
proposal's framing (rendering variation, not user-query simulation) already covers the gap.

---

## 3. Decision gates

| Gate | After | Question | If no |
|---|---|---|---|
| **G1** | S2 | Does BM25 fall under L1 variation? | Reframe the paper before S3; O4 re-scoped |
| **G2** | S5 | Does the structured/lexical ranking invert? | Method contribution shifts from S11 to S10 |
| **G3** | S8 | Did the balanced dose set arrive? | H4 becomes exploratory; sprint halves |
| **G4** | S12 | Test split frozen | Any reopening is documented and re-run whole |

## 4. Critical path and parallelism

The critical path is **S0 → S1 → S2 → S3 → S4 → S6 → S12 → S13** (≈ 14 weeks).

Off the critical path, and parallelisable given compute:

- S5 can overlap S4 once the harness is stable (different method family, same conditions).
- S9, S10 and S11 are independent of one another and all depend only on S6. If time is
  short, G2 decides which of S10/S11 gets the budget; the paper needs one method
  contribution, not three.
- S7 and S8 are analysis sprints over runs that already exist by then.
- S✻ runs entirely outside the path.

## 5. Cross-repo dependencies

| Need | From | Requested in | Consumed in |
|---|---|---|---|
| OE release digests confirmed | `bc3cat-dataset` | S0 | S0 |
| Balanced dose set (counts 1–5, randomised mixes, `reorder` admitted) | `bc3cat-dataset` | S0 | S8 |
| Per-item modification sidecar for artefact sensitivity analysis | `bc3cat-dataset` | S1 | S6 |
| Wider `paraphrase` / `expansion` slices (n≈206–211 today) — issued 2026-09-29 as [`requests/WIDER_THIN_SLICES.md`](requests/WIDER_THIN_SLICES.md), widened to all three L2 types, which reach 5 dev concepts; answered the same day, build approved, then corrected: waits for an upstream engine fix, at most 9 / 9 / 8 dev concepts (D-043 amended) | `bc3cat-dataset` | S4 | S6 |

## 6. Risk register

| Risk | Sprint | Handling |
|---|---|---|
| Harness adaptation overruns and blocks everything | S1 | Golden-fixture test as the exit criterion; timebox and cut slices, not correctness |
| The central thesis does not hold | S2 | G1 reframes at week 4, not month 4 |
| Thin-type slices cannot support per-type claims | S4, S6 | Layer-level pooling; explicit power note; upstream request for wider slices |
| Stacked set confounding leaks into an interaction claim | S7 | Caveat carried in the sprint report, not only in the manuscript |
| Rewrite-menu artefacts (token doubling, one documented semantic drift) bias a slice | S6 | Sensitivity analysis excluding affected items, traceable via the sidecar |
| Track D/E produce no gain over tuned BM25 | S10, S11 | A negative result, honestly reported, is still the method section — but G2 should have chosen the more promising track by then |
| Test-split contamination through tuning | all | Split rule, one-shot test rule, provenance stamp |
