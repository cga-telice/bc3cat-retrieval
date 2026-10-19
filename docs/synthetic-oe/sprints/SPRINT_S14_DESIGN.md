# Sprint S14 — External rendering: back-translated queries · design

> **Status: frozen 2026-10-19** (drafted 2026-10-18; César's ruling of 2026-10-19, relayed by the
> `bc3cat-dataset` session: **backbone S14**, not a probe; **the oracle arms — the readers of `parameters` — are
> out of every test of this sprint and of S12's BT reading**, printed only as bounds with a note that BT's
> `parameters` hold the gold's values; no BT regenerated with variant `parameters` is requested). Nothing in it had
> run at the freeze. From the freeze commit, which carries this header and `SPRINT_S14_AMENDMENTS.md` (its SHA is
> recorded there and in `SPRINTS.md`), changes go in the amendments file (D-045), dated and justified. The
> stopping-criterion section below is void for a backbone and is kept as written.

| Field | Value |
|---|---|
| **ID / type** | `S14` · backbone (César, 2026-10-19) |
| **Status** | active (frozen 2026-10-19) |
| **Serves** | Validity of the whole robustness profile (proposal §9, threat 1); O4 (the method contribution, S11) on an independent rendering; H1 on a non-menu rendering |
| **Depends on** | the 2026-10-16 intake (`bt_texto`, STACKED-P filter, v2; `DELIVERIES.md`); S7 A8 (the `stacked_texto_v2` runs and `results/S7/v2/stacked_p/`); S11 A7 (K2, R2, F1 on v2; the ColBERT family cache machinery) |
| **Decisions applied** | D-010, D-028, D-030, D-033, D-045, D-059, D-060 (H8), D-061 |
| **Effort** | 1 week (runs one day; analysis, report and audit the rest) |
| **Predecessor / successor** | S11 (method), the v2 amendments / S12 (the test-side BT, 2,339 queries, is evaluated once there) |

## Goal

Every query set this branch has measured was rendered by one generator: the BC3CAT-Syn grammar with its
frozen, LLM-authored, human-audited rewrite menus. The robustness profile (S4–S8), the overlap law (S6, S9) and
the method contribution (S11) are therefore statements about *that* generator's renderings. At the end of this
sprint we will know, **paired leaf for leaf on the same 2,331 dev leaves**, whether the ordering of the arms
measured on STACKED-P is reproduced when the same leaves are rendered by a second, independent generator —
sentence-level back-translation through English, French, Italian and German with OPUS-MT, no LLM, no rewrite
menu beyond audited value variants and trade-term synonyms (`DELIVERIES.md`, 2026-10-16). If it is, the profile
is a property of the catalogue's items under rendering variation, not of the menu; if it is not, the manuscript
says which readings depend on the generator. The sprint also gives the method contribution its first reading on
a rendering no LLM saw and no menu shaped.

## Entry state

Each item is checked in the tree, not taken from the registry (the checks are in `tests/test_intake_20261016.py`
unless stated):

- **`bt_texto` is taken in and registered**: `OE_bt_texto.json` `421b3ca3…`, 4,670 records, one per STACKED-P
  leaf, `item_key` = gold + `_btorigv_en`, `source_text_sha256` equal to this tree's corpus text for all 4,670;
  tables `OE_bt_texto_{norm,feats}.parquet` on the proven synthetic path, with `condition` and `source_item_key`
  in the projection. 79 concepts, 40 dev / 39 test; 2,331 dev queries over 40 concepts.
- **STACKED-P is a filter** (`exclusions.stacked_p`, 324 keys); its dev side is 2,332 queries, one per leaf, and
  2,331 of those leaves carry a BT query (`OEB160a` does not). Pairing: BT gold = STACKED-P gold.
- **Item-level exclusions on dev BT:** 55 D-033 golds (the same 55 as STACKED-P's), so item level scores
  **2,276** of 2,331; parent level scores all. No P7 / P8 key is in `bt_texto`.
- **What BT is, measured here:** mean fraction of translated sentences 0.48 — on dev 522 queries below 0.5,
  1,511 at exactly 0.5, 298 above; `value_back_translation` in 1,855 dev queries, `glossary_synonym` in 1,438,
  both in 1,140, neither (pure BT) in 178; the axis label precedes a value variant in 97. Rough lexical coverage
  of the gold (word types shared ÷ query types) has a dev median near 0.79 against 0.69 for STACKED-P v2:
  **BT is the gentler rendering.** Chains per dev query: `en-fr` in most, `en` in most, `en-it` / `en-de` rare.
- **F-BT-1 (closed upstream):** 1,498 of the 2,331 dev queries say «de hormigón» where the gold says
  «hormigonada»; the referent is unchanged, the token is.
- **BT's `parameters` are the gold's own values, not the variants its text carries** (measured 2026-10-18,
  `DELIVERIES.md`): for every `value_back_translation` modification the record's `parameters` holds the
  *original* value (5,268 of 5,268 located; 0 hold the variant), while STACKED's `parameters` hold the rewritten
  values. The oracle arms (D-010: `bm25_unigram_params`, `tfidf_phrases_replace`, `oracleparams_valuenorm`)
  therefore read a strictly stronger oracle on BT than on STACKED-P. **They are printed on BT as upper bounds with
  this asymmetry in every header, and they enter no registered test of this sprint, nor S12's BT reading**
  (César, 2026-10-19; proposed as my call in the draft).
- **The reference runs exist:** every arm below has a dev run on `stacked_texto_v2` (S7 A8, S11 A7) and on
  `texto` (identity), and `results/S7/v2/stacked_p/` has been generated. Checked by `check_run_inputs.py` before
  the freeze. **Sequencing:** the sprint freezes only after the S7 A8 and S11 A7 runs are made and their tables
  generated; the 21 BT runs may be *made* before that (they read nothing of STACKED-P) but no BT result is read,
  and P (below) is computed and listed, before the freeze. If an A8 / A7 audit re-makes a reference run, P is
  recomputed and the amendments file says so with both run ids.
- **The LLM arms stamp model digest and prompt SHA-256 in `run_meta.json`** (S11 exit criterion 3, S12's
  requirement): the harness change lands before the S11 A7 v2 runs, so the v2 and the BT runs carry one
  convention.

## Work

1. **Intake tests for the sprint's population** (`tests/test_intake_s14.py`): the pairing above; the 55
   exclusions; no dev BT query equals a leaf's `texto` or another dev query's text (S4 work item 4's test); the
   coverage, fraction and flag counts quoted in this design, re-derived.
2. **The within-family ColBERT cache for `bt_texto`** (`build_colbert_family_cache.py --base bt_texto`, after
   the `bge_m3_colbert` and `dense_e5` runs of item 3), with A2's exact check; and `phi4` extraction for the
   2,331 dev BT queries (the cache is keyed on the prompt, so every BT query generates), with the S11 regeneration
   check on 100 seeded BT queries (`logs/S14/determinism_extract.json`).
3. **Runs, first-time only, dev split, every parameter as frozen in S4 / S5 / S11:** on `bt_texto`, the 15 S4
   arms (10 indexed, 2 RRF, 3 CE blend, components first), the 3 S5 structured arms, and S11's **K2**, **R2** and
   **F1** (K0 and K1 are stages of K2 and are not re-run) — **21 runs**, each followed by `metrics.ipynb`
   (`logs/S14/run_s14.sh`, the S8 / A8 procedure). The LLM arms' `run_meta.json` stamps model digest and prompt
   SHA (S11 EC3, as S12 requires).
4. **Analysis**, `build_results_s14.py` → `results/S14/`, generated, never typed, prose guard, two generations
   byte-identical. **Stage P first** (`--fix-pairs`, run before any BT run exists or is read): the 10 non-oracle
   contrasts on dev STACKED-P v2 restricted to the paired leaves, with intervals, Holm within the 10, and the
   resulting P, written to `pairs_stacked_p.md` and copied into the amendments file at the freeze. Then: T1 profile (every arm, item and parent, tie-free and as run, on BT, with the identity ceiling
   and the STACKED-P v2 figure of the same arm on the same leaves beside); T2 the pairwise arm contrasts (B1);
   T3 the method contrast (B2); T4 H1 on BT (B3); T5 BT against STACKED-P per leaf (B4); T6–T9 the secondary
   strata; T10 the F-BT-1 and D-004 sensitivity; T11 provenance; Fig. 9 (item Acc@1 on BT against STACKED-P v2,
   one point per arm).
5. **Report, audit in a fresh session, `done` only after the audit passes** (`/sprint-close S14`, `/audit S14`).

## Design constraints

- **Population.** Dev only. BT: 2,331 queries, 40 concepts; item level 2,276 scored (D-033), parent level
  2,331. The paired reference is **STACKED-P v2** on the same 2,331 leaves (`results/S7/v2/stacked_p/`), and the
  identity is each arm's own `texto` run on the same golds (treatment effect on the treated, as everywhere).
  Test BT (2,339 queries, 39 concepts) is never read before S12.
- **Reading.** Tie-free Acc@1 is the reading (D-028 note); as run beside it. Concept-clustered percentile
  intervals (D-030), B = 10,000, S2's seeds and labels; the query-level interval printed, never read. ‡ marks
  fewer than 10 concepts behind a cell.
- **Hypotheses, registered now, read by S4's rule** (supported: interval above 0 and Holm p < α within the
  family; contradicted in the mirror case; not supported otherwise). One Holm family per reading (tie-free, as
  run, F-BT-1-free), as S7 A1 d.
  - **B1 — the ordering is preserved (primary).** The contrast between two arms a and b on a rendering is
    **the paired difference of their tie-free item Acc@1 on the same item-scored queries**, Acc(a) − Acc(b)
    (not a difference of δ against identity, which would rank an arm by its identity ceiling: `dense_e5` starts
    at 0.51 where the others start near 1.00; my call). Let P be the set of ordered pairs (a, b) among the
    **five non-oracle base arms** (`bm25_unigram`, `bge_m3_colbert`, `bge_m3_dense`, `dense_e5`,
    `dense_es_hiiamsid`; 10 pairs) whose contrast on dev STACKED-P v2, **on the 2,331 leaves BT pairs** (2,276
    item-scored), is *supported*: interval above 0 and Holm p < α within the 10 pairs. **P is computed by this
    sprint's own generator in a P-fixing stage from the S7 A8 runs** (`results/S14/pairs_stacked_p.md`,
    generated, with every stamp) **before any BT run is read, and listed in the amendments file with its date and
    the run ids it rests on.** For each pair in P the test is Acc(a) − Acc(b) > 0 on BT, paired on the same
    2,276 leaves. **Rule:** the ordering is *preserved* if every pair in P has a positive point estimate on BT
    and at least half are supported; *contradicted* if any pair is contradicted; *partly preserved* otherwise.
    All 10 contrasts are printed on both renderings, descriptively, whatever P holds. The oracle arms are
    printed beside, never in P (the asymmetry above).
  - **B2 — the method contribution holds on a rendering no LLM saw.** K2 − `bge_m3_colbert` > 0 on BT, item
    level, paired (the S11 A1 contrast). Descriptive beside it, not tested: R2 − `bm25_unigram`, F1 − ColBERT,
    and K2 − ColBERT per `bt_sentences.fraction` bin.
  - **B3 — H1 on BT.** For each of the five non-oracle base arms, W1 (the gap parent − item widens, BT −
    identity > 0) and W2 (discrimination falls more than concept identification) as S7 defines them.
  - **B4 — BT is gentler than STACKED-P (calibration, registered so that it cannot be read either way after the
    fact).** For each of the five non-oracle base arms, item δ_BT − δ_STACKED-P > 0 per leaf (δ = rendering −
    identity). A *not supported* B4 does not touch B1–B3; it says the two renderings are of similar strength.
  - **One Holm family per reading** (tie-free; as run; F-BT-1-free), over **all** registered tests of this
    sprint — |P| B1 contrasts, B2, the 10 B3 tests, the 5 B4 tests — as S7 A1 d forms its family. "Supported"
    everywhere above means within that family.
  - Floor arms (identity item Acc@1 on the BT leaves below 0.20, S4) are printed and not tested, as everywhere.
    The oracle arms† are printed in every table as upper bounds, with the `parameters` asymmetry stated, and
    take part in no test.
- **Secondary strata, descriptive, no Holm, no reading:** δ_BT by `bt_sentences.fraction` bin (< 0.5, = 0.5,
  > 0.5); by `value_back_translation` × `glossary_synonym` (2 × 2) and by `label_added`; by subchapter; by S9's
  lexical-coverage bins (B1–B4 of the untransformed query), which places BT on the overlap axis S9 measured;
  retention P(hit BT | hit identity) beside each.
- **Sensitivity.** Every B-reading recomputed (a) without the 1,498 F-BT-1 queries and (b) without S3's D-004
  flags, if the detector flags any BT query; a reading that changes category is *not robust*, the full
  population's reading stands.
- **Caveats carried in, stated in every table's header where they bite:** (i) BT is gentler (0.48 of sentences
  translated; label sentences return identical), so a smaller δ is expected and B4 says so in advance; (ii) half
  of its variation is list-driven again (value variants, glossary synonyms: audited lists, not the menus of
  BC3CAT-Syn, but lists), so independence from a menu is partial — the pure-BT subset (178 dev queries) is
  printed, thin; (iii) OPUS-MT is not an LLM: BT is blind for K2 / R2's `phi4` prompt and for S9's rewriters;
  (iv) 79 of 83 concepts, 40 of 42 dev; 15 dev concepts carry fewer than 10 BT queries; (v) H8: ColBERT and the
  arms built on it encode BT in their own batches, and the family cache is built from BT's own ColBERT run; (vi)
  the S11 LLM arms carry their OEB `resumen` prompt exposure, as in S11.
- **No tuning.** Nothing is swept, selected or thresholded on BT.

## Exit criteria

1. Item 1's tests committed and passing; the entry-state counts re-derived.
2. 21 clean runs on `bt_texto` (`code_dirty: false`, split `dev`, `OE_bt_texto_feats.parquet` `ee8c1d21…`
   stamped), the family cache with 0 mismatched, the extraction regeneration logged; every live OE run resolves
   under `check_run_inputs.py`.
3. T1–T11 and Fig. 9 generated, byte-identical across two generations, prose guard passing; n scored, n excluded,
   concepts and both intervals on every contrast.
4. P computed from the S7 A8 runs on the paired leaves (`pairs_stacked_p.md`) and listed in the amendments file
   with its date and run ids before the first BT run was read; B1–B4 read tie-free, as run and F-BT-1-free, in
   one Holm family per reading, with the rule stated beside each.
5. The report states: the B1 verdict; B2; B3; B4; the strata; and, for the manuscript, which readings of
   S4–S11 the BT rendering reproduces and which it does not.
6. Full suite and the OEB fixture pass; audit in a fresh session passes; `done` withheld until then.

## Stopping criterion — if César rules it a probe (S92)

*Void: César ruled it a backbone on 2026-10-19. Kept as drafted.* Five working days from the freeze. The probe is pointless, and stops with a one-page note, if (a) P is empty
(STACKED-P v2 supports no pairwise ordering, so there is nothing to preserve), or (b) on BT every base arm's
item δ interval contains 0 (the rendering is too gentle to order the arms). As a backbone neither case stops it:
(a) is reported as the manuscript's own limitation and (b) as a result.

## Out of scope

- The test-side BT (2,339 queries): S12, once, with everything else.
- Training on BT (S10) and any BT of SINGLE or the E3 ladder (not delivered).
- Repeating the drift audit on v2 (César, 2026-10-16) and any BT re-generation, including a BT whose
  `parameters` carry the variant values (the oracle arms are out of this sprint's tests instead).
- A real-query anchor (S90): BT is a second synthetic rendering, not real queries; the threats row says both.

## Risks

| Risk | Handling |
|---|---|
| P is small (few supported pairs on STACKED-P v2), so B1 rests on 2–4 contrasts | Stated in the report with P's size; the per-pair table prints all 10 contrasts on both renderings, descriptively |
| The oracle arms read the gold's values on BT (the `parameters` asymmetry) | Out of every test; printed as upper bounds with the asymmetry stated; a BT with variant `parameters` is not requested in this sprint (out of scope) |
| BT is too gentle: most arms near their identity ceiling | B4 says so in advance; the F-BT-1 subset and the fraction bins show where damage concentrates |
| `phi4` extraction on BT values («Volumen importante» for «Volumen relevante») misreads the audited variants | That is what B2 measures; the stage decomposition (`s11_stages`) prints the axes misread, as S11 T3 |
| 55 D-033 duplicates among the BT golds | Excluded at item level as everywhere; n excluded printed |
| The 1,498 F-BT-1 queries dominate the lexical arms' loss | Every reading given with and without them (sensitivity); the manuscript quotes the full population |
| ColBERT batch dependence (H8) moves near-ties | Family cache from BT's own run with the exact check; comparisons across runs state it |
| Container, servers | `host.docker.internal` reaches BGE-M3 and ollama from `bc3cat-s3` again (checked 2026-10-18); re-checked before the runs |

## Amendments

In `SPRINT_S14_AMENDMENTS.md`, append-only (D-045), from the freeze.
