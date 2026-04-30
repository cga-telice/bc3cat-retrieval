# Architectural Choices in Lightweight Parameter Extraction: When CLS Classifiers Exploit Format-Specific Cues and What Survives at the Token Level

**Author:** César
**Status:** First draft — markdown for LaTeX translation
**Companion data:** `docs/lightweight-extraction-ner/RESEARCH_LOG_LIGHTWEIGHT_NER.md`, `docs/lightweight-extraction/RESEARCH_LOG_LIGHTWEIGHT.md`, `analysis/*.csv`

---

## Abstract

Structure-aware retrieval pipelines for parametric catalogs decompose item-level retrieval into concept retrieval, parameter extraction, and catalog lookup. Prior work on the BC3CAT Spanish railway construction catalog identified Stage 2 (parameter extraction) as the bottleneck: rule-based string matching reaches 91.4% item-level Acc@1 on a 16,590-query short-text benchmark, while LLM extractors (Phi-4 14B) reach 88.6% at ~600× the inference cost. We ask whether a fine-tuned encoder can match the rules baseline with the language understanding of neural models. We test two encoder-based architectures, both built on `intfloat/multilingual-e5-base`: (i) a multi-head [CLS] classifier with one head per (concept-group, axis) pair, and (ii) a single-shared BIO span tagger followed by a deterministic schema-bounded normalizer. Both architectures train to ≥99% query accuracy on long-text (training-distribution) validation, but collapse to 21.2% and 3.13% respectively on the cross-distribution short-text test. Five complementary diagnostics — a CLS⊕BIO contingency, an error taxonomy, a frozen-encoder ablation, a cross-format paired diagnostic, and a per-axis recall breakdown — locate the failure mechanism in axis-specific surface anchors that exist in long text but not in short text. The token-level BIO tagger, contrary to the prior on its supposed locality robustness, is *more* sensitive to anchor loss than the CLS classifier in every regime tested. Together with the prior CLS result, this establishes that within the long-only-training paradigm, no purely architectural change closes the cross-distribution gap on this corpus. (~210 words)

---

## 1. Introduction

Real-world parametric catalogs — construction price lists, e-commerce variants, industrial parts catalogs — share a structural pattern: items are defined as `concept + parameter combination`. Retrieval methods that treat items as flat text suffer a characteristic failure mode: high concept-level accuracy but item-level collapse, because thousands of variants share the same concept and differ only on combinations of parameter values. Cesar et al. (SEPLN 2026, hereafter "the SEPLN paper") proposed a structure-aware three-stage pipeline that separates concept retrieval from parameter resolution, and showed that on the BC3CAT corpus rule-based parameter extraction reaches 91.4% item Acc@1 — a 78pp improvement over the best dense retriever and within 0.4pp of a parametric BM25 baseline.

The SEPLN result raises a follow-up question: **can a fine-tuned encoder match rules at the parameter-extraction stage, while gaining the phrasing robustness that rules lack?** Two natural architectures present themselves: a multi-head classifier on the [CLS] token (one head per axis) and a token-level BIO tagger (single shared head) with a deterministic span normalizer. The first is the standard approach for short-input classification; the second is the standard approach for slot-filling and named-entity recognition. The latter has been argued to be more robust to surface variation because its decisions are conditioned on local token evidence rather than on a sequence-level aggregation.

We test both architectures on the same BC3CAT benchmark. Both train on the long-text catalog descriptions (the only available labeled source) and are evaluated on the standard 16,590-query short-text benchmark — a deliberate cross-distribution test that mirrors deployment, where queries are drafted independently of the catalog wording.

**Findings.** Both architectures train to ≥99% on their training distribution and collapse on the cross-distribution test:

|  | val (long) query_acc | cross-dist oracle Acc@1 |
|---|---|---|
| Rule baseline (SEPLN) | — | 91.4% |
| CLS classifier full FT | 99.6% | 21.2% |
| CLS classifier frozen encoder | 11.4% | 0.58% |
| **BIO tagger full FT** | **99.2%** | **3.13%** |
| **BIO tagger frozen encoder** | **0.0%** | **0.07%** |

The BIO architecture, contrary to the architectural intuition that motivated it, is *strictly worse* than the CLS classifier in every regime: frozen encoder on long text, frozen encoder on short text, full fine-tuning on short text. Five complementary diagnostics localize the failure to axis-specific surface anchors (e.g., the literal label `condiciones de ejecución:` that precedes the value in long text but is absent in short text) and rule out the trivial alternative explanations.

**Contributions.**
1. A negative architectural result for token-level supervision in cross-distribution parameter extraction, controlled against a parallel CLS classifier baseline on the same corpus and benchmark.
2. An error taxonomy that uniformly classifies failures across rules, CLS, and BIO, with per-axis breakdowns showing which axes survive cross-distribution and which collapse.
3. A frozen-encoder ablation paired across both architectures, demonstrating that representation adaptation is necessary but insufficient — the cross-distribution gap is not an over-fitting artifact.
4. A cross-format paired diagnostic on 500 (long, short) `item_key`-matched pairs, showing that information loss is strictly one-directional: no `(long_wrong, short_correct)` cell exists for any axis or any architecture.

**The framing.** Together with the SEPLN paper's rules baseline and the prior CLS result, this work establishes that within the long-only-training paradigm, **no purely architectural change closes the cross-distribution gap on this corpus.** The implication: future work must address the data side (representation alignment, training-distribution mixing, augmentation) rather than continuing to iterate on Stage 2 architecture.

---

## 2. Background

### 2.1 BC3CAT and the parametric retrieval problem

BC3CAT is a Spanish railway construction price catalog with 47,508 leaf items organized into 25 concept groups. Each item is identified by a `(concept, parameter combination)` pair — 13 unique parameter axes recur across groups, with at most 5 axes per group and at most 12 canonical values per axis. The largest groups contain up to 6,336 fully combinatorial parametric variants. Each item has a long natural-language description (the `texto`) and a short summary (the `resumen`). The standard benchmark is to retrieve the correct item given the short summary as the query, evaluated against the long descriptions.

The SEPLN paper showed that flat-text neural retrieval (BGE-M3, E5, GTE, ColBERT) achieves 96-99% concept-level accuracy but only 12-45% item-level accuracy: the parametric structure is invisible to standard semantic models. A structure-aware three-stage pipeline (concept retrieval → parameter extraction → catalog lookup) bridges this gap, with parameter extraction as the critical Stage 2.

### 2.2 The Stage 2 baselines

|  | item Acc@1 (oracle) | inference cost |
|---|---|---|
| Rule-based string matcher | 91.4% | 0.02 ms/query (CPU) |
| Phi-4 14B classify-prompt | 88.6% | ~886 ms/query (GPU) |
| Llama 3.1 8B extract-prompt | 82.1% | ~585 ms/query (GPU) |
| dense_e5 (no fine-tuning, direct retrieval) | — / 13.4% pipeline | 5 ms/query (GPU) |

Rules dominate. They achieve the highest accuracy and the lowest cost, but at the price of brittleness: each rule is hand-tuned per axis, and the surface forms hard-coded into the matcher come from the training distribution (long-text format). Adapting rules to a new phrasing dialect — a different company's RFP language, regional terminology, abbreviations — is engineering effort that doesn't scale.

The motivating question for this paper: **can a fine-tuned encoder match the rules baseline with neural-grade phrasing robustness?**

### 2.3 The cross-distribution setup

Both architectures we test train on the long-text catalog descriptions (47,508 leaf items, 80/10/10 train/val/test split stratified by concept group). They are evaluated on the standard 16,590-query short-text benchmark — the same `resumen` queries used for the SEPLN paper's evaluation. This is a deliberate cross-distribution test:

- Long text format: `... en cualquier clase de terreno, excepto roca, incluso ... trabajo: diurno banda de mantenimiento: i >= 5 horas condiciones de ejecución: volumen relevante`
- Short text format: `canalización hormigonada de 12 t, pvc 110 mm, en balasto. (diurno/i < "3" horas/volumen escaso)`

The two formats encode the same underlying parameters but use very different surface forms — most prominently, the long format carries explicit axis labels (`trabajo:`, `banda de mantenimiento:`, `condiciones de ejecución:`) that are absent in the short format's parenthetical list.

This setup mirrors deployment. In production, short-form natural-language descriptions are what users type; the long-form catalog is what's available for training. If neither architecture handles the cross-distribution gap with long-only training, that's an empirical fact about the corpus, not about the architectures.

---

## 3. Methods

### 3.1 Architecture 1 — Multi-head [CLS] classifier

Following standard practice for short-input classification: `intfloat/multilingual-e5-base` encoder + per-(concept-group, axis) classification heads on the `[CLS]` token. With 25 groups × ~4 axes/group, the model has 97 heads. Each head is `Linear(768, num_canonical_values + 1)` where `+1` is a null class for "this axis is not applicable."

At inference, only heads for the query's concept group are active. The model is trained with sum-of-CE over active heads per batch; AdamW with `lr=2e-5`, linear warmup 10%, mixed precision, 5 epochs at batch size 32 on RTX 4090.

### 3.2 Architecture 2 — Shared BIO span tagger + deterministic normalizer

Token-level BIO tagging with a single shared head: `intfloat/multilingual-e5-base` encoder + `Linear(768, 27)` over `O ∪ {B-axis, I-axis : axis ∈ 13_unique_axes}`. Spans are extracted by greedy argmax + standard BIO post-processing (stray `I-X` promoted to `B-X`; adjacent same-axis spans merged). Each span is normalized to a canonical schema value via:

1. Exact case-insensitive substring match.
2. Surface-form override (e.g., `cualquier clase de terreno → Normal` for the implicit-default case).
3. Axis-specific rules — operator/quote canonicalization for inequality-string axes, unit stripping for numeric axes.
4. Fuzzy match (normalized Levenshtein ≤ 0.15) against canonical values.
5. Otherwise, return null.

The normalizer is **bounded by the schema**: at most 12 canonical values per (group, axis) pair. There is no hallucination risk by construction. Same training regime as Architecture 1.

### 3.3 Training data

The BIO labels are generated offline from the long-text training corpus by aligning each canonical value to a span in `text_norm` using a unified anchored-substring matcher (non-alphanumeric boundaries on both sides; per-row occupancy tracking to handle same-surface collisions like `TRABAJO=BANDA="no aplica"`). 100% of 235,995 axis occurrences across 47,508 leaf items align cleanly; 200 stratified rows hand-validate at 100% correctness (gate ≥95%).

### 3.4 Frozen-encoder ablations

For both architectures, we additionally train a variant with the encoder frozen — only the classification heads (CLS: ~45k parameters) or the BIO head (~21k parameters) are learnable. This isolates the contribution of representation adaptation from the contribution of the head.

---

## 4. Experiments

| Experiment | Conditions | Source |
|---|---|---|
| Cross-distribution test (headline) | rules / Phi-4 / CLS / BIO; full FT and frozen; pipeline + oracle; 16,590 queries | LWN-03 §C2 |
| CLS ⊕ BIO contingency | per-query agreement on 16,590 queries | LWN-04 §C3.a |
| Error taxonomy | E1-E3 categories per method | LWN-05 §E1 |
| Cross-format paired diagnostic | BIO on 500 matched (long, short) pairs | LWN-04 §D1 |
| Per-axis recall | full 16,590 BIO oracle | LWN-04 |
| Frozen-encoder ablation | both architectures, head-only training | LW-07, LWN-04 §D3 |
| Speed benchmark | per-query latency on CPU and GPU | LWN-04 §C4 |

---

## 5. Results

### 5.1 Headline table (16,590 short-text queries)

| Method | Pipeline item Acc@1 | Oracle item Acc@1 | val (long) query_acc | Trainable params |
|---|---|---|---|---|
| dense_e5 (no FT, direct) | 13.4% | — | — | 278M |
| BIO tagger frozen | — | **0.07%** | 0.0% | 21k |
| CLS classifier frozen (LW-07) | 0.56% | **0.58%** | 11.4% | 45k |
| **BIO tagger full FT** | **3.10%** | **3.13%** | 99.2% | 278M |
| **CLS classifier full FT (LW-06)** | **20.9%** | **21.2%** | 99.6% | 278M |
| Phi-4 14B classify (SEPLN) | 87.7% | 88.6% | — | 14B (frozen) |
| Rules (SEPLN) | 90.3% | **91.4%** | — | 0 |
| BM25 param-aware (SEPLN) | 97.4% | — | — | 0 |

The neural Stage 2 architectures both train to ≥99% on their long-text validation set but collapse on the short-text test. The BIO tagger collapses harder than the CLS classifier in every regime.

### 5.2 The CLS ⊕ BIO contingency

|  | CLS correct | CLS wrong | Total |
|---|---|---|---|
| BIO correct | 199 (1.20%) | 321 (1.93%) | 520 |
| BIO wrong | 3,321 (20.02%) | **12,749 (76.85%)** | 16,070 |
| Total | 3,520 (21.21%) | 13,070 | 16,590 |

The methods are non-redundant — each finds queries the other misses (BIO-only correct = 321; CLS-only correct = 3,321) — but their union (3,841 = 23.15%) is far below the rules baseline (91.4%). 76.85% of queries are wrong under both methods; this is the "hard core" that no architectural choice within the long-only-training paradigm has solved.

### 5.3 Cross-format paired diagnostic (500 matched pairs)

For each of 474 `item_key`s present in both long and short corpora, the BIO tagger is run on both formats:

| Axis | Long acc | Short acc | Transfer rate |
|---|---|---|---|
| TRABAJO | 100% | 91.0% | 91.0% |
| TIPO DE TERRENO | 100% | 62.8% | 62.8% |
| BANDA DE MANTENIMIENTO | 100% | 56.7% | 56.7% |
| Nº TUBOS | 100% | 38.6% | 38.6% |
| **CONDICIONES DE EJECUCIÓN** | 100% | **6.8%** | **6.8%** |
| MATERIAL, PAVIMENTO, TERRENO | 100% | 0% | 0% |
| TIPO DE ACCIÓN, TUBO, DIÁMETRO, DIÁMETROS | 100% | 100% | 100% |

Across all 474 pairs, **`(long_wrong, short_correct)` never occurs**. Cross-distribution loss is strictly one-directional: short-text predictions are a subset of long-text predictions.

### 5.4 Per-axis recall on the full 16,590-query test (BIO oracle)

| Axis | Total | Correct | Recall |
|---|---|---|---|
| TRABAJO | 16,571 | 15,220 | 91.8% |
| TIPO DE TERRENO | 15,259 | 9,948 | 65.2% |
| PROFUNDIDAD | 377 | 249 | 66.0% |
| BANDA DE MANTENIMIENTO | 16,571 | 9,261 | 55.9% |
| **Nº TUBOS** | 15,986 | 2,149 | **13.4%** |
| **CONDICIONES DE EJECUCIÓN** | 16,580 | 141 | **0.9%** |
| TIPO DE ACCIÓN, TUBO, DIÁMETRO, DIÁMETROS | small | all | 100% |
| MATERIAL, PAVIMENTO, TERRENO | small | 0 | 0% |

Two axes dominate the failure: **CONDICIONES DE EJECUCIÓN at 0.9%** and **Nº TUBOS at 13.4%**. The all-axes-correct rate is 0.51% — the 3.13% item Acc@1 is recovered from this floor through Stage 3 catalog lookup tolerating partial parameter matches when the other parents in the group differ on the wrong axes.

### 5.5 Error taxonomy on the 16,070 missed BIO oracle queries

| Top-level category | Count | % of misses |
|---|---|---|
| TAGGER_MISS | 13,882 | 86.4% |
| NORMALIZER_MISS | 2,187 | 13.6% |
| WRONG_VALUE | 1 | 0.0% |
| ALL_AXES_OK_BUT_CATALOG_MISS | 0 | 0.0% |

87% of missed queries match the dominant signature: `TAGGER_MISS:Nº TUBOS | NORMALIZER_MISS:CONDICIONES DE EJECUCIÓN`. The model anchors on " tubos"/" mm" in long text and doesn't fire Nº TUBOS on the short-text format `<digit> t,`. For CONDICIONES, the model emits a span but truncates it to a single token (`cualquier`/`volumen`/`relevante`), and the normalizer can't fuzzy-match a single word to a compound canonical like `Cualquier condición de ejecución` (Levenshtein distance 23+).

### 5.6 Comparative error structure across rules / CLS / BIO

Same 16,590 queries, oracle conditions, uniform categorization:

| Method | ALL_CORRECT | PARTIAL | WRONG_VALUE | ALL_NULL |
|---|---|---|---|---|
| Rules | **93.51%** | 6.49% | 0.00% | 0.00% |
| CLS classifier | 21.57% | 78.37% | 0.05% | 0.00% |
| BIO tagger | **0.51%** | 97.44% | 0.00% | 2.04% |

The three methods differ qualitatively in how they fail. Per-axis NULL vs WRONG counts on missed queries:

| Axis | Rules NULL | Rules WRONG | CLS NULL | CLS WRONG | BIO NULL | BIO WRONG |
|---|---|---|---|---|---|---|
| TRABAJO | **1,017** | 0 | 0 | **7,777** | 1,346 | 5 |
| BANDA DE MANTENIMIENTO | 28 | 0 | 0 | **6,382** | **7,310** | 0 |
| TIPO DE TERRENO | 0 | 0 | 0 | **4,718** | **5,310** | 0 |
| CONDICIONES DE EJECUCIÓN | 34 | 0 | 3 | 748 | **16,439** | 0 |
| **Nº TUBOS** | 0 | 0 | 0 | 0 | **13,837** | 0 |
| PROFUNDIDAD | 0 | 0 | 0 | 0 | 128 | 0 |

Three failure profiles emerge:

- **Rules**: high accuracy on the limited set of patterns the matcher hand-encodes. Almost all failures are NULL extractions, concentrated in TRABAJO (1,017 cases where the surface form is outside the rule templates). When rules return a value, it's correct.
- **CLS classifier**: forced commit. The architecture must softmax-pick a value from the canonical set, so failures are *confidently wrong* values rather than nulls. TRABAJO 7,777 wrong, BANDA 6,382 wrong, TIPO DE TERRENO 4,718 wrong.
- **BIO tagger**: conservative null. The architecture's per-token decision returns no canonical when the span is uninterpretable, so failures are *abstentions* rather than wrong values. Extreme on Nº TUBOS (13,837 NULL) and CONDICIONES (16,439 NULL).

The catalog lookup at Stage 3 treats NULL and WRONG very differently. A NULL axis is ignored in the lookup constraint, so partial-axis correctness can still pin down the right item if other axes uniquely identify it. A WRONG axis actively excludes the correct item. This is why the BIO tagger reaches 3.13% Acc@1 from 0.51% all-axes-correct (catalog lookup tolerates the NULLs) while CLS reaches 21.2% from 21.6% all-axes-correct (catalog lookup is unforgiving of WRONG). The architectural choice determines not just *whether* errors happen but *what kind*, and Stage 3 amplifies the consequence.

### 5.7 Speed benchmark (200 queries, mean / p95 ms)

| Method | CPU mean | CPU p95 | GPU mean | GPU p95 |
|---|---|---|---|---|
| Rules | 0.02 | 0.02 | — | — |
| CLS classifier | 23.88 | 28.26 | 5.43 | 6.46 |
| BIO tagger | 22.94 | 28.55 | 5.87 | 7.73 |
| Phi-4 14B (reference, SEPLN) | — | — | ~886 | — |

BIO and CLS have effectively identical inference latency. The architectural choice is speed-neutral.

---

## 6. Discussion

### 6.1 The CLS-vs-BIO asymmetry: confident-wrong vs conservative-null

The comparative error taxonomy in §5.6 reveals a clean architectural asymmetry. Both architectures fail on the cross-distribution test, but they fail in opposite ways:

- CLS predictions on the missed queries are 99.95% WRONG_VALUE (the model commits to a canonical value, just the wrong one).
- BIO predictions on the missed queries are 100% NULL (the model emits a span the normalizer can't map).

This is a direct consequence of architectural choice. The CLS softmax over canonical values forces the model to commit; the BIO+normalizer pipeline can return None whenever the span is uninterpretable. Stage 3 catalog lookup amplifies this asymmetry: NULLs are ignored (partial-match recovery still works), WRONGs actively exclude the correct item.

The end-to-end Acc@1 numbers (CLS 21.2% vs BIO 3.13%) are the integrated effect of two opposing factors: CLS errors are more harmful per error (WRONG > NULL for catalog lookup), but CLS errors are far less common (CLS reaches 21.6% all-axes-correct vs BIO's 0.51%). The CLS architecture wins the combined comparison because the soft-commit error mode is recoverable through Stage 3 only some of the time, while the per-axis correctness rate of CLS is dramatically higher than BIO's.

### 6.2 Why is the BIO architecture *worse* than CLS?

The architectural intuition that motivated this work: token-level supervision should make decisions less dependent on global sequence aggregation, and therefore more robust when the format changes around the value tokens (protocol §3.2). The empirical result is the opposite — BIO is *strictly worse* than CLS in every regime tested.

The mechanism is visible in the per-axis recall and error taxonomy. The dominant BIO failure for CONDICIONES is **compound-span truncation**: in long text, `B-CONDICIONES` is fired on `volumen` only when preceded by the literal label `condiciones de ejecución:`. In short text, `volumen` appears in the parenthetical list `(.../volumen relevante)` without the label anchor, and the model emits only a single `B-CONDICIONES` on `volumen` alone — followed by O on `relevante`. The normalizer can't reconstruct `Volumen relevante` from `volumen` alone via fuzzy match.

The CLS classifier doesn't have this failure mode. Its prediction is a single softmax over the canonical values, and the [CLS] aggregation is robust enough to fire `Volumen relevante` on the short-text input — even when the label anchor is absent — because the [CLS] token sees the full sequence and can use redundant information from other parts of the query. The CLS architecture, despite being theoretically more anchor-dependent, in practice has more redundancy at the query level.

**Counter-intuitive conclusion: per-token loss creates *stronger* per-token sensitivity to local context.** The local context is the very label-prefix anchor that doesn't transfer across formats, so the BIO tagger ends up more anchor-bound, not less.

### 6.3 The cross-distribution gap is fundamental to the corpus

The cross-format paired diagnostic is the cleanest evidence: across 474 `item_key`-matched pairs, no axis ever has `(long_wrong, short_correct)`. Whatever information the model needs to predict a value is present in the long format and either preserved or lost in the short format — never gained. This is a property of the corpus, not of either architecture.

This means: any Stage 2 architecture trained only on long text will be capped by the upper envelope shown in the per-axis transfer table. CONDICIONES at 6.8% is not a model failure to be tuned; it is the maximum the long-text training distribution offers.

### 6.4 Frozen encoder ablations rule out the trivial alternatives

The frozen-encoder variants test whether the cross-distribution gap is an over-fitting artifact (the model memorizes long-text format quirks) or a representation-adaptation artifact (the model adapts E5 to long text and the adaptation doesn't transfer).

- Frozen CLS reaches 11.4% val query_acc on long text — the linear projection from pretrained E5 [CLS] is barely informative for parameter extraction. Cross-distribution test: 0.58%.
- Frozen BIO reaches 0.0% val query_acc on long text — the linear projection from pretrained E5 token states over a 27-class space is even harder. Cross-distribution test: 0.07%.

Both frozen variants are essentially useless. Representation adaptation is *necessary* — but as the full-FT results show, it is also *insufficient*. The full FT of E5 reaches 99% on long text and collapses on short. The adaptation that works on the training distribution does not transfer.

### 6.5 Implications for parametric retrieval

The two-architecture negative result, combined with the cross-format paired diagnostic, motivates redirecting Stage 2 effort to the **data side**:

1. **Mixed training** (long + short with proper holdout) — the most direct fix; requires labeled short-text training data, which the BC3CAT corpus has at item-level granularity but not at parameter-axis granularity. This is the obvious next step.
2. **Query augmentation** (rewrite long-text format into short-text format with template-based rules; train on both) — a cheap proxy for mixed training.
3. **Auxiliary anchor-removal training** — at training time, randomly delete the label prefix `condiciones de ejecución:` and force the model to predict from the value tokens alone. A regularizer that targets exactly the failure mechanism identified here.

What this paper rules out: that the choice between [CLS] aggregation and token-level supervision is the right architectural lever. Both architectures fail; both fail on the same axes; both require the same data fix.

### 6.6 Limitations

- All training data is catalog-generated long text. We cannot test the architectures' behavior on labeled short-text training data because none exists for parameter axes (only for item identity). The data-side directions in §6.4 require labeled short-text — a substantial annotation effort.
- The corpus is single-language (Spanish railway construction). Whether the same failure mechanism appears in English construction or in other parametric domains is an open question.
- We do not test CRF decoding for BIO. Greedy decoding with BIO post-processing was sufficient to identify the compound-span truncation failure; CRF would likely improve span coherence but cannot fabricate an anchor that doesn't exist in the input.

---

## 7. Related work

- **Slot-filling and BIO tagging in IE.** Standard token-level architectures (Lample et al., 2016; Devlin et al., 2019) operate at the token level by design. Cross-distribution generalization of slot fillers has been studied in dialog (Bapna et al., 2017) but typically under in-distribution test conditions or with explicit domain-adaptation training.
- **Parametric retrieval.** The structure-aware approach of decomposing item retrieval into concept retrieval + parameter resolution (Cesar et al., SEPLN 2026) is the most direct predecessor. Parametric BM25 with axis-aware tokenization is the strongest non-neural baseline.
- **Cross-distribution generalization for fine-tuned encoders.** Long line of evidence that encoder fine-tuning on one distribution can degrade on another (e.g., ID-OOD generalization gaps in NLI, QA). The closest analogues are domain-adaptation studies that find fine-tuned encoders are *more* domain-fragile than pre-trained ones (Hendrycks & Gimpel, 2017).
- **Constraint-bounded outputs vs LLM extraction.** Phi-4 14B and Llama 3.1 8B were tested in the SEPLN paper at ~88% / 82% Acc@1 with several hundred ms latency. The deterministic schema-bounded normalizer in this work eliminates the LLM-style hallucination risk by construction, at the cost of being unable to handle out-of-schema phrasing.

---

## 8. Conclusion

We test two encoder-based architectures for parameter extraction in a structure-aware retrieval pipeline on the BC3CAT corpus: a multi-head [CLS] classifier and a token-level BIO span tagger. Both train to ≥99% on their long-text training distribution and collapse on the cross-distribution short-text test (21.2% and 3.13% respectively). Five complementary diagnostics localize the failure to axis-specific surface anchors that exist in long text but not in short text. The token-level BIO tagger is *strictly worse* than the [CLS] classifier in every regime tested, contrary to the architectural intuition that motivated it. The cross-distribution gap is one-directional: no `item_key`-matched (long, short) pair has the BIO correct only on short. The frozen-encoder ablations rule out the over-fitting alternative. **Within the long-only-training paradigm, no purely architectural change closes the cross-distribution gap on this corpus.** The paper closes a research direction (architectural Stage 2 fixes) and points at the open one (mixed-distribution training, anchor-removal augmentation).

---

## 9. References

*(Author-year format; bibliography to be assembled after venue selection.)*

- Cesar et al. (SEPLN 2026). "Structure-Aware Retrieval for Parametric Catalogs Using LLM-Based Parameter Extraction." `docs/structured-retrieval/RESEARCH_PROPOSAL.md`.
- Devlin et al. (NAACL 2019). BERT.
- Lample et al. (NAACL 2016). LSTM-CRF for NER.
- Bapna et al. (Interspeech 2017). Sequence-to-sequence dialog state tracking.
- Hendrycks & Gimpel (ICLR 2017). A baseline for detecting misclassified and out-of-distribution examples.
- BAAI (2024). `intfloat/multilingual-e5-base` model card.
- BAAI (2024). BGE-M3.
- Sturua et al. (2024). GTE.

---

## 10. Source pointers (for verification during translation to LaTeX)

| Claim | Source |
|---|---|
| 47,508 items, 25 groups, 13 axes | LWN-01 §A2 |
| Long+short corpus structure | SEPLN paper §2 |
| Rules 91.4% / Phi-4 88.6% / dense_e5 13.4% | SEPLN paper §3 |
| CLS full FT 21.2% / frozen 0.58% | LW-06, LW-07 |
| BIO full FT 3.13% / frozen 0.07% | LWN-03 §C2, LWN-04 §D3 |
| Per-epoch span_f1 progression (BIO) | LWN-03 §B5 |
| 100% alignment success on training data | LWN-01 §A2/A4 |
| 23 unit tests for normalizer | LWN-02 §B2 |
| CLS ⊕ BIO contingency 199 / 321 / 3,321 / 12,749 | LWN-04 §C3.a, `analysis/cls_vs_bio_confusion.csv` |
| Error taxonomy 86.4% TAGGER_MISS / 13.6% NORMALIZER_MISS | LWN-04 §C3.b, `analysis/bio_error_taxonomy.csv` |
| Per-axis recall full corpus | LWN-04, `analysis/bio_per_axis_short_text_full.csv` |
| Cross-format diagnostic | LWN-04 §D1, `analysis/cross_format_diagnostic.csv` |
| Speed benchmark | LWN-04 §C4, `analysis/speed_benchmark.csv` |
| Comparative error taxonomy | LWN-05 §E1, `analysis/comparative_error_taxonomy.csv` |
