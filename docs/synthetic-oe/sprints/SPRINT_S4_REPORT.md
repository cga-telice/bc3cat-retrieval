# Sprint S4 — E1 ablation, Track A · report

| Field | Value |
|---|---|
| **Design** | [`SPRINT_S4_DESIGN.md`](SPRINT_S4_DESIGN.md) · frozen at `dd407c6` · amendments A1–A4 |
| **Closed** | 2026-09-29 (report written). First audit **FAIL**, reopened; findings resolved in [Audit response](#audit-response). `done` waits for a fresh re-audit |
| **Code commit** | 17 new runs at `36bed7a`, all `code_dirty: false`. 13 reused runs at `31bf1a1`, `922ae53`, `2e49566`, `a5700a6`. Generator `src/utils/build_results_s4.py` |
| **Query-set digests** | `single_texto` `e5b79ae4` · `texto` `643f1a72` (ColBERT and `bge_m3_dense` read `OE_long_norm` `75477221`) |
| **Runs** | `runs/OE/{texto,single_texto}/<arm>` · split `dev` · 214 of 214 OE runs resolve (`check_run_inputs.py`, now following derived runs to their components) |
| **Results** | [`results/S4/`](../results/S4): T1–T7, generated, byte-identical on regeneration, under the prose guard |

## What ran

Fifteen arms × nine single types on OE dev, each query paired with the same arm's identity result on
its own gold (treatment effect on the treated). Every stamp is in
[`run_provenance.md`](../results/S4/run_provenance.md) (T7); none is repeated here.

| Block | What | Where |
|---|---|---|
| Harness | RRF and CE-blend as derived runs (`derived_runs.py`, `fuse_rrf.py`, `rerank_ce.py`); dirty-tree refusal in `provenance.py`; `check_run_inputs.py` resolves derived runs through their components; 21 tests | `36bed7a` |
| Check | Work item 4: one dev query is another leaf's `texto` → P7, excluded at item level (A2) | [`DATASET_DEFECTS.md`](../DATASET_DEFECTS.md) P7 |
| Runs | 7 base arms × `single_texto`; 2 RRF and 3 CE arms × {`texto`, `single_texto`} = 17 new; 13 reused, each with a computed retrieval-path diff showing no change to its retriever, `retrieve.ipynb` or config | T7 |
| Analysis | T1 derived ceilings · T2/T3 profile at both levels · T4 token distance · T5 ties · T6 predictions | [`results/S4/`](../results/S4) |
| Upstream | P7 and wider-L2 requests issued and answered; P7 test list and `OE_single_l2_texto.json` taken in, not wired | [`DELIVERIES.md`](../DELIVERIES.md), D-042, D-043 |

**Population.** 2,206 dev queries over 42 concepts. Item level scores 2,176: 29 D-033 golds and the one
P7 query are excluded. Parent level scores all 2,206. Every figure below is on that population,
from the table named. **L2 is thin.** Its three types and its pool cover **5 of the 42 concepts** (T2),
so every L2 figure below is a dev observation on those 5 concepts. The wider build (9 / 9 / 8, D-043) is
S6's.

## Findings

**1. A single referent-preserving edit costs every arm with headroom item-level accuracy. Only the
arms that contain BM25 lose the concept materially.** Pooled over the nine types, retention (P(hit | hit at identity), T2 `all`)
is 0.7791 for `bge_m3_colbert`, 0.7876 for `rrf`, 0.6341 for `bge_m3_dense`, 0.5928 for
`dense_es_hiiamsid` and 0.5391 for `bm25_unigram`. The oracle `bm25_unigram_params` retains 0.6226
beside its twin's 0.5391. At parent level ColBERT modified is 0.9995 against identity 1.0000 (T3).
BM25 and the arms built on it lose the concept (T3 parent δ):
- `bm25_unigram`: 0.9991 → 0.8001.
- Its oracle twin: −0.1201.
- `ce_bm25_unigram`: −0.0861.
- `rrf`: −0.0843 [−0.1029, −0.0405].

No arm without a BM25 component loses more than `bge_m3_dense`'s −0.0190.

**2. The collapse widens, and reaches the lexical family (H1).** The gap parent − item widens by
+0.2050 (`bm25_unigram`), +0.2546 (`bm25_unigram_params`) and +0.2201 (`bge_m3_colbert`); all three P1
tests are supported (T6). Conditional discrimination D = P(item | parent) falls from 0.9986 to 0.7784
for ColBERT and from 0.8951 to 0.6115 for `bm25_unigram`. The right-parent / wrong-item rate of the
oracle BM25, the arm the previous study led with, goes from 0.0028 to 0.2574 (T3).

**3. L1 is where lexical arms break (H2).** `bm25_unigram` retains 0.3036 under pooled L1, against
0.7832 under L2 (5 concepts) and 0.6989 under L3. Both P2 contrasts are supported for both BM25 arms
(T6). The L1-vs-L2 pair rests on 5 L2 clusters, which T6 marks ‡. A percentile interval under-covers at
that count, so this reading is weaker than its interval suggests. The L1-vs-L3 pair rests on 39 and 40. The
extreme is `num_to_text`: retention 0.1178 for `bm25_unigram` and 0.0958 for the oracle, against
0.7700 for ColBERT on the same leaves (T2; side by side, not a contrast).

**4. `reorder` behaves exactly as H2 says; L3 as a layer does not.** `reorder` item δ is +0.0000 for
all three lexical arms (P3 supported) and negative for the order-sensitive encoders: −0.1333 ColBERT,
−0.3400 `bge_m3_dense`, −0.1100 `dense_es_hiiamsid` (P4 supported). But `template_paraphrase`, the
other L3 type, costs every arm: retention 0.3864 for `bm25_unigram` and 0.2823 for `bge_m3_dense`. It
is not an order change. On the item-scored queries, its mean token distance to the gold is 0.3221,
against 0.0023 for `reorder` (T4).

**5. On L2's 5 concepts, BM25 leaves the concept and the encoders mostly do not.** Every figure here
rests on the 5 L2 concepts.
- **BM25.** Among `bm25_unigram`'s item losses, the share that also leaves the concept is higher under
  L2 than under L1 by +0.4010. P5 is supported, but on 5 L2 clusters (‡ in T6).
- **ColBERT.** P5 cannot hold: under L2 its parent level stays at 1.0000 while item δ is −0.1434
  (T3, T2), so P5 is not supported. Of the encoders, only ColBERT is hurt at item level alone.
- **Other encoders.** They lose a little of the concept under L2. Parent modified is 0.9963 for
  `bge_m3_dense`, 0.9945 for `dense_es_hiiamsid` and 0.9706 for `ce_bge_m3_colbert` (T3).

**6. Derived arms (reference, no contrast claimed).**
- **Identity ceilings (T1), side by side.** `rrf` 0.9547 and `ce_bge_m3_colbert` 0.9457 scored.
  ColBERT's is 0.9998 (S3 `ceiling.md`). No paired test compares them. Whether fusion or reranking
  lowers the ceiling is an arm-vs-arm contrast the design does not claim.
- **Under modification, side by side.** The CE blend over ColBERT retains 0.6700; ColBERT alone retains
  0.7791. On `num_to_text` the figures are 0.2919 and 0.7700.
- **RRF.** Deployable RRF retains 0.7876, and 0.8987 on `num_to_text`.
- **Status.** Whether any derived arm beats its base is not an S4 claim (design).

**7. Ties are common for BM25 under L1, and T5 detects no sort-order bias in them.** Under
`synonym_label`, `bm25_unigram`'s rank 1 is tied on 0.8182 of item-scored queries (0.0629 at identity)
(T5). That fits the rewritten token being out of vocabulary, so siblings differing only on that axis
score alike. No table tests that mechanism.
- **Does the sort favour the gold?** Where the gold is in the tied group (268 L1 queries), it wins 92,
  a share of 0.3433. A uniform draw would win 0.3005. The excess is +0.0428 [−0.0071, +0.0832]. The
  interval contains 0: a sort-order effect is not detected, which is not the same as shown absent.
- **What share of the hits are ties?** 92 of `bm25_unigram`'s 276 L1 item hits are tie-wins. About a
  third of its L1 hits come from a tie, not from discrimination.

**8. Floor arms.** `bge_m3_sparse` 0.0625, `dense_gte` 0.0951 and `dense_gte_instrQ` 0.1062 identity item
Acc@1 on the treated leaves; reported, excluded from every prediction. GTE's parent level stays below the
others (0.9665 modified), the H1 counterexample D-012 kept it for.

**9. Two carried caveats, counted (T4).**
- **The decimal artefact (DATASET_DEFECTS H1).** H1's reach is the design's set: queries carrying a
  `d.ddd` decimal at all. That is 9 `unit_conversion` and 4 `unit_expansion` queries, 32 over all
  types.
- **Where a miss is attributed to it.** Only 5 queries carry a decimal their gold lacks, all
  `unit_conversion` and all item-scored. Everywhere else, query and gold are mangled alike and still
  match. So a miss is attributed to the artefact only in those 5.
- **Four untreated `synonym_label` queries (P8, candidate).** They differ from their gold only in
  letter case, so for an arm reading normalised text they are the identity query. They are kept in.
  Without them, `synonym_label` item δ moves from −0.6434 to −0.6525 [−0.7090, −0.5141] for
  `bm25_unigram`, and from −0.3007 to −0.3050 for ColBERT. No reading changes.

## Hypotheses

| Hypothesis | Movement | Evidence |
|---|---|---|
| **H1** (widening collapse) | **supported** on dev for `bm25_unigram`, `bm25_unigram_params`, `bge_m3_colbert` (S4 reading; S6 resolves) | Finding 2; P1 ×3 supported |
| **H2** (layer specificity) | **L1 clause supported**, the **`reorder` clauses supported**; the **L2 clause supported for BM25 only, on 5 L2 concepts**; **L3 as a layer not supported descriptively**: `template_paraphrase` costs bag-of-words (not a registered test; S6 to test) | Findings 3–5; P2 ×4, P3 ×3, P4 ×3 supported (two P2 on 5 L2 clusters); P5 1 of 2, on 5 L2 clusters |
| **H3** (rank inversion) | **not addressed** | S5's; no arm-vs-arm contrast here |
| **H4** (super-additivity) | **not addressed** | S8 |
| **H5** (overlap mediation) | **not addressed** | T4 is descriptive; S6 |
| **H6** (crossover) | **not addressed** | S9 |

## What is now known to be wrong

1. **"L3 is near-free for bag-of-words."** True of `reorder` only. `template_paraphrase` is filed under
   L3 but rewrites tokens (d_tok 0.3221 on the item-scored queries), and bag-of-words pays for it
   (finding 4). The layer grouping
   in the branch contract predicts `reorder`, not L3.
2. **"Every BC3CAT-Syn query is referent-preserving by construction."** One dev query renders a sibling's
   TEXTO (P7), and upstream found 2 more on test from a related rule. The generator's own review had
   approved the rules. The equality test that found P7 cannot see the second kind.
3. **"Upstream's reachability counts are deliverable counts."** The first answer promised 9 / 9 / 8 L2
   concepts and the first build delivered 5: its check tested visibility, not renderability (D-043
   amended). It was caught because the build was checked before it was taken.
4. **"Components can be paired by query-set digest."** The frozen work item 2 would have refused every
   `texto` fusion: ColBERT and BM25 read different tables holding the same queries (A1a).
5. **"A tie table over all queries measures retriever ties."** Its first version counted the D-033
   golds, which tie by construction, and made every dense arm look tied equally under modification and
   identity (A3c).
6. **"The resume will re-run one arm."** My resume script re-ran all seven base arms (A2c). No figure
   moved, and none had been read.

## Exit criteria

| # | Met | Evidence |
|---|---|---|
| 1 | yes | `36bed7a`: modules, five configs naming components by method (A1b), `tests/test_derived_runs.py`; suite green including the OEB fixture |
| 2 | yes | Count 1, amendment A2 before any reading |
| 3 | yes | 17 runs clean at `36bed7a`; CE runs stamp their ML stack; T7 computes the reuse diffs |
| 4 | yes, after the audit | T1–T7 regenerate byte-identically. T1–T3 print n, n scored and n excluded per cell, and T4 per level (audit F2; first reported "yes" without them). Every δ has both CIs and its concept count. T4 no longer mixes populations (audit F1) |
| 5 | yes | 15 arms × 9 types × 2 levels plus three layer pools; no empty cell |
| 6 | yes | T6: 14 supported, 1 not supported, 0 contradicted |
| 7 | yes | `requests/WIDER_THIN_SLICES.md`; `RESEARCH_PLAN.md` §5 |
| 8 | yes | Hypotheses table above |

## Deviations from design

| Amendment | Deviation | Why |
|---|---|---|
| A1 | Component pairing by ordered keys, not digest; configs name components by method; RRF tie rule; CE fp32, raw `text`, score cache | Work item 2 as written refuses every `texto` fusion; the design left the rest open |
| A2 | P7 query excluded at item level; one dirty run archived to `runs/_archive/S4/`; base runs re-run by a faulty resume | Work item 4's own stop rule; operating rule 1 |
| A3 | P3 mirror rule and floor scope made explicit; T5 restricted to item-scored queries and extended with the decisive-tie table | T5 as first generated mixed a corpus property into a retriever measurement |
| A4 | After the first audit: T4 computed per level on that level's population; T1–T3 gain n / n scored / n excluded; T5 gains hits and an excess-over-uniform interval; T6 gains concept counts and a ‡ flag below 10 clusters; T4 gains the decimal-artefact reconciliation and the P8 sensitivity | Audit F1, F2, F3, F6, F7, F8. No run changed. Figures other than T4's item-level d_tok means and δ / d_tok ratios are unchanged |

Not an amendment, recorded for the auditor: the reorder upstream fix, the P7 test list, and
`OE_single_l2_texto.json` (D-043) arrived during S4 and touch no S4 run.

## What the next sprint inherits

- **S5 (structured, H3):** the 15-arm profile as the reference; `rrf` and the CE arms exist as runs.
- **S6:**
  - The paired frames and token distance (T4, d_tok fixed by the design, per level since audit F1).
  - L2 on 9 / 9 / 8 concepts. On S4's 5 dev concepts the encoders keep the concept under L2 and BM25
    does not (finding 5). Whether "L2 affects concept-level more than item-level" fails for the
    encoders is S6's to read, not S4's.
  - P8's four case-only `synonym_label` queries: keep or exclude (César's call).
  - `OE_single_l2_texto.json` to wire: 9 / 9 / 8 dev concepts, grammar ceiling 13 (D-043).
  - `template_paraphrase` to be analysed apart from `reorder` inside L3 (finding 4).
  - The D-004 sensitivity analysis.
- **S12:** `OE_P7_test_exclusion.json` (`96fe3854`), applied at item level only there (D-043).
- **Debt:**
  - H4 (index stamps omit the ML stack) is still open for indexed arms; CE runs stamp theirs.
  - A stable tie-break is still missing. T5 now shows it does not bias BM25's δ, but it decides a
    visible share of L1 hits.
  - CE on `texto` costs up to about 37 minutes per base (T7 `elapsed` in `run_meta.json`).

## Decisions raised

| ID | Status | What |
|---|---|---|
| D-042 | **Accepted** | The CE model is the one the code ran; the manuscript's is a reporting defect |
| D-043 | **Accepted**, amended, note | P7 on both splits (S12 list); L2 via upstream engine fix, delivered at 9 / 9 / 8 |
| D-028 | note proposed | Ties measured for every family (T5). For BM25, no sort-order bias is detected: the excess over a uniform draw has an interval containing 0. A third of its L1 hits are tie-wins |
| — | proposed for S6 | H2 is read per type inside L3: `reorder` and `template_paraphrase` are different operations |

## Audit response

`/audit S4` ran in a fresh session on 2026-09-29 and returned **FAIL**
([`SPRINT_S4_AUDIT.md`](SPRINT_S4_AUDIT.md), verbatim). It recomputed every headline figure from
`runs/` and found all of them exact. It also found the seven tables byte-identical on regeneration and
the design unedited after freeze except the amendments. The sprint was reopened. No run was re-made.
The generator changed (design A4). T1–T3, T5 and T6 only gained columns. T4 was restructured, and only
its item-level d_tok means and δ / d_tok ratios moved. Disposition:

| Finding | Disposition |
|---|---|
| F1 — T4 mixes samples | **Fixed.** T4 computes d_tok and Δ numbers per level, on that level's scored population, and δ / d_tok divides by the same level's mean. Finding 4 and known-wrong 1 are re-quoted on the item-scored queries: `template_paraphrase` 0.3221, `reorder` 0.0023 |
| F2 — EC4 reported met without n excluded | **Fixed.** T2 and T3 print n, n scored and n excluded per cell, as the design's T2 spec lists; H1's collapse table prints n scored and n excluded. T1 prints n excluded at item level and n at parent level, and says "item, all" is reference only. EC4 now reads "yes, after the audit" and says it was first reported without them |
| F3 — L2 conclusions rest on 5 concepts, unstated | **Fixed.** The population paragraph states the 5-of-42 reach. Findings 3 and 5 and the H2 row name it in every L2 sentence. T6 gains a concepts column with ‡ below 10 clusters: P2 L1-vs-L2 ×2 and P5 ×2 carry it. The reading rule is unchanged. Known-wrong 2 is withdrawn and restated as a dev observation under S6's inheritance, pending the 9 / 9 / 8 build |
| F4 — "`bm25_unigram` is the only family that loses the concept" | **Fixed.** Finding 1 now says "BM25 and the arms built on it", with `rrf`, `ce_bm25_unigram` and the oracle twin's parent δ. Finding 5 says "item level alone" only of ColBERT, and gives the other encoders' L2 parent level |
| F5 — arm-vs-arm claim in finding 6 | **Fixed.** Finding 6 sets the ceilings and retentions side by side, and says that no paired test compares them and that the design claims no such contrast |
| F6 — finding 7 asserts a null without an interval | **Fixed.** T5 gains, per arm and scope, the modified hits and the mean excess of gold wins over a uniform draw with its concept-clustered interval. For `bm25_unigram` L1 it is +0.0428 [−0.0071, +0.0832]. Finding 7 says a sort-order effect is not detected, not that it is absent. It replaces "those hits are draws" with the count: 92 of 276 L1 hits are tie-wins. The out-of-vocabulary mechanism is marked untested |
| F7 — decimal-artefact counts under two definitions | **Fixed.** T4 prints both. "In query" is H1's set and reproduces the design's 9 `unit_conversion` + 4 `unit_expansion`. "Absent from gold" is the 5 where a miss is attributable. Finding 9 states which set a miss is attributed to |
| F8 — four case-only `synonym_label` queries | **Recorded and measured.** `DATASET_DEFECTS.md` P8 (candidate). T4 lists them and prints each arm's `synonym_label` item δ with and without them, with a clustered CI. No reading changes. They stay in: the design has no rule excluding them, and the figures had been read. Excluding them in S6 is César's call |
| F9 — "L3 as a layer refuted" | **Fixed.** The H2 row reads "not supported descriptively … S6 to test" |

The auditor's unverifiable items stand as it listed them. The full suite was re-run for this response
(see the commit).
