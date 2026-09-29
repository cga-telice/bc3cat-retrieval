# Sprint S4 — E1 ablation, Track A · report

| Field | Value |
|---|---|
| **Design** | [`SPRINT_S4_DESIGN.md`](SPRINT_S4_DESIGN.md) · frozen at `dd407c6` · amendments A1–A3 |
| **Closed** | 2026-09-29 (report written; `done` waits for `/audit S4` in a fresh session) |
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
from the table named.

## Findings

**1. A single referent-preserving edit costs every arm with headroom item-level accuracy, and almost
none of them the concept.** Pooled over the nine types, retention (P(hit | hit at identity), T2 `all`)
is 0.7791 for `bge_m3_colbert`, 0.7876 for `rrf`, 0.6341 for `bge_m3_dense`, 0.5928 for
`dense_es_hiiamsid` and 0.5391 for `bm25_unigram`. The oracle `bm25_unigram_params` retains 0.6226
beside its twin's 0.5391. At parent level ColBERT modified is 0.9995 against identity 1.0000 (T3).
`bm25_unigram` is the only family that loses the concept materially: 0.9991 → 0.8001.

**2. The collapse widens, and reaches the lexical family (H1).** The gap parent − item widens by
+0.2050 (`bm25_unigram`), +0.2546 (`bm25_unigram_params`) and +0.2201 (`bge_m3_colbert`); all three P1
tests are supported (T6). Conditional discrimination D = P(item | parent) falls from 0.9986 to 0.7784
for ColBERT and from 0.8951 to 0.6115 for `bm25_unigram`. The right-parent / wrong-item rate of the
oracle BM25, the arm the previous study led with, goes from 0.0028 to 0.2574 (T3).

**3. L1 is where lexical arms break (H2).** `bm25_unigram` retains 0.3036 under pooled L1, against
0.7832 under L2 and 0.6989 under L3; both P2 contrasts are supported for both BM25 arms (T6). The
extreme is `num_to_text`: retention 0.1178 for `bm25_unigram` and 0.0958 for the oracle, against
0.7700 for ColBERT on the same leaves (T2; side by side, not a contrast).

**4. `reorder` behaves exactly as H2 says; L3 as a layer does not.** `reorder` item δ is +0.0000 for
all three lexical arms (P3 supported) and negative for the order-sensitive encoders: −0.1333 ColBERT,
−0.3400 `bge_m3_dense`, −0.1100 `dense_es_hiiamsid` (P4 supported). But `template_paraphrase`, the
other L3 type, costs every arm: retention 0.3864 for `bm25_unigram` and 0.2823 for `bge_m3_dense`. It
is not an order change. Its mean token distance to the gold is 0.3206, against 0.0053 for `reorder`
(T4).

**5. L2 attacks the concept only for BM25.** Among `bm25_unigram`'s item losses, the share that also
leaves the concept is higher under L2 than under L1 by +0.4010 (P5 supported). For ColBERT it cannot be:
under L2 its parent level stays at 1.0000 while item δ is −0.1434 (T3, T2), so P5 is not supported.
L2 hurts the encoders at item level only.

**6. Derived arms (reference, no contrast claimed).**
- **Identity ceilings (T1).** Fusion and reranking lower the identity ceiling: `rrf` 0.9547 and
  `ce_bge_m3_colbert` 0.9457 scored, against ColBERT's 0.9998 (S3 `ceiling.md`).
- **Under modification.** The CE blend over ColBERT retains 0.6700 against ColBERT's own 0.7791; on
  `num_to_text` it retains 0.2919 against 0.7700.
- **RRF.** Deployable RRF retains 0.7876, and 0.8987 on `num_to_text`.
- **Status.** Whether any derived arm beats its base is not an S4 claim (design).

**7. Ties do not bias the BM25 figures, but they are common.** Under `synonym_label`, `bm25_unigram`'s
rank 1 is tied on 0.8182 of item-scored queries (0.0629 at identity), because the rewritten token is out
of vocabulary and siblings differing only on that axis score alike (T5). Where the gold is in the tied
group (268 L1 queries), it wins 0.3433 of the time against 0.3005 for a uniform draw. The sort neither
hands BM25 its hits nor takes them away, but those hits are draws, not discrimination.

**8. Floor arms.** `bge_m3_sparse` 0.0625, `dense_gte` 0.0951 and `dense_gte_instrQ` 0.1062 identity item
Acc@1 on the treated leaves; reported, excluded from every prediction. GTE's parent level stays below the
others (0.9665 modified), the H1 counterexample D-012 kept it for.

## Hypotheses

| Hypothesis | Movement | Evidence |
|---|---|---|
| **H1** (widening collapse) | **supported** on dev for `bm25_unigram`, `bm25_unigram_params`, `bge_m3_colbert` (S4 reading; S6 resolves) | Finding 2; P1 ×3 supported |
| **H2** (layer specificity) | **L1 clause supported**, the **`reorder` clauses supported**; the **L2 clause supported for BM25 only**; **L3 as a layer refuted** descriptively by `template_paraphrase` (not a registered test) | Findings 3–5; P2 ×4, P3 ×3, P4 ×3 supported; P5 1 of 2 |
| **H3** (rank inversion) | **not addressed** | S5's; no arm-vs-arm contrast here |
| **H4** (super-additivity) | **not addressed** | S8 |
| **H5** (overlap mediation) | **not addressed** | T4 is descriptive; S6 |
| **H6** (crossover) | **not addressed** | S9 |

## What is now known to be wrong

1. **"L3 is near-free for bag-of-words."** True of `reorder` only. `template_paraphrase` is filed under
   L3 but rewrites tokens (d_tok 0.3206), and bag-of-words pays for it (finding 4). The layer grouping
   in the branch contract predicts `reorder`, not L3.
2. **"L2 affects concept-level more than item-level."** For the encoders it affects item level only;
   ColBERT never leaves the concept under L2 (finding 5). The clause holds for BM25.
3. **"Every BC3CAT-Syn query is referent-preserving by construction."** One dev query renders a sibling's
   TEXTO (P7), and upstream found 2 more on test from a related rule. The generator's own review had
   approved the rules. The equality test that found P7 cannot see the second kind.
4. **"Upstream's reachability counts are deliverable counts."** The first answer promised 9 / 9 / 8 L2
   concepts and the first build delivered 5: its check tested visibility, not renderability (D-043
   amended). It was caught because the build was checked before it was taken.
5. **"Components can be paired by query-set digest."** The frozen work item 2 would have refused every
   `texto` fusion: ColBERT and BM25 read different tables holding the same queries (A1a).
6. **"A tie table over all queries measures retriever ties."** Its first version counted the D-033
   golds, which tie by construction, and made every dense arm look tied equally under modification and
   identity (A3c).
7. **"The resume will re-run one arm."** My resume script re-ran all seven base arms (A2c). No figure
   moved, and none had been read.

## Exit criteria

| # | Met | Evidence |
|---|---|---|
| 1 | yes | `36bed7a`: modules, five configs naming components by method (A1b), `tests/test_derived_runs.py`; suite green including the OEB fixture |
| 2 | yes | Count 1, amendment A2 before any reading |
| 3 | yes | 17 runs clean at `36bed7a`; CE runs stamp their ML stack; T7 computes the reuse diffs |
| 4 | yes | T1–T7 regenerate byte-identically; every item figure carries n scored and n excluded; every δ has both CIs and its concept count |
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

Not an amendment, recorded for the auditor: the reorder upstream fix, the P7 test list, and
`OE_single_l2_texto.json` (D-043) arrived during S4 and touch no S4 run.

## What the next sprint inherits

- **S5 (structured, H3):** the 15-arm profile as the reference; `rrf` and the CE arms exist as runs.
- **S6:**
  - The paired frames and token distance (T4, d_tok fixed by the design).
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
| D-028 | note proposed | Ties measured for every family (T5); for BM25 the gold wins a tie at about the uniform rate, so no bias, but the hits are draws |
| — | proposed for S6 | H2 is read per type inside L3: `reorder` and `template_paraphrase` are different operations |
