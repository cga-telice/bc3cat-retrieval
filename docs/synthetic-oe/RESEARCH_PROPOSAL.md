# Research Proposal — BC3CAT-Syn/OE

**Working title (option A).** *When does lexical retrieval stop winning? Robustness of
retrieval methods to rendering variation in parametric construction catalogues.*

**Option B.** *From verbatim containment to realistic phrasing: a layer-resolved
robustness study of retrieval on parametric construction price catalogues.*

**Option C.** *Parametric collapse under rendering variation: diagnosing and repairing
item-level retrieval in construction catalogues.*

**Branch.** `research/synthetic-oe` (`bc3cat-retrieval`), consuming the BC3CAT-Syn/OE
release produced by `bc3cat-dataset` (branch `synthetic`).

**Target venue.** *Automation in Construction* (primary); *Advanced Engineering
Informatics* / *Journal of Computing in Civil Engineering* (fallback).

---

## 1. Background

Parametric price catalogues (BC3/FIEBDC) describe construction work items through a
generation grammar rather than through free text: a *concept* (parent) is rendered into
hundreds or thousands of *leaves* (items) by resolving a set of parameter axes. In ADIF's
price base, a single concept routinely expands into several hundred sibling items whose
descriptions are lexically near-identical and differ only in parameter values. Retrieval
over such a catalogue is therefore not a topical matching problem but a *fine-grained
discrimination* problem within a family of hard negatives.

Our previous study systematically compared ~100 retrieval configurations — lexical
(BM25, TF-IDF variants), dense (E5, GTE, BGE-M3, Spanish sentence encoders), sparse-neural,
late-interaction (BGE-M3 ColBERT), hybrid (RRF), pseudo-relevance feedback and
cross-encoder reranking — on the OEB chapter, under a dual-target protocol that scores both
*item-level* and *parent-level* accuracy. Two findings define the starting point of this
proposal:

1. **Parametric collapse.** Every method family localises the correct *concept* almost
   perfectly, yet item-level accuracy falls by an order of magnitude for single-vector
   encoders: E5-large 0.134 item vs **0.982** parent Acc@1; BGE-M3-dense 0.127 vs 0.960;
   BGE-M3-sparse 0.125 vs 0.994; GTE-large 0.013 vs 0.837. Late interaction mitigates but
   does not solve it — BGE-M3-ColBERT, the best neural configuration, reaches 0.448 item
   vs **0.997** parent. The near-perfect parent-level scores are what make this a
   *discrimination* failure rather than a semantic one: the signal separating siblings is
   carried by parameter values, and neural representations do not preserve it. The locus
   is numeric — stratified by query type, E5-large scores 0.875 on queries without numeric
   parameters against 0.133 on numeric ones, and BGE-M3-ColBERT 1.000 against 0.447, a
   pattern holding across all neural families. The error profile agrees: 54.3 % of
   ColBERT's rank-1 errors are right-parent/wrong-item, against 10.4 % for BM25.
2. **Lexical dominance.** BM25 with parameter-aware tokenisation and tuned
   `k1`/`b` reaches 0.974 item-level Acc@1 — a 52.6-point margin over the best neural
   configuration at item level, a margin that vanishes entirely at parent level —
   outperforming every neural and hybrid configuration, and also outperforming rule-based structured-matching pipelines
   built on extracted attributes (0.903, 0.914 with oracle extraction).

Peer review of that study identified — correctly — the condition under which those numbers
hold. Queries were the catalogue's own `resumen` field and targets the `texto` field of the
*same record*: measured over 20,000 aligned pairs, the target contains on average **94.1 %
of the query's tokens and 99.93 % of its numeric values, verbatim**. The task, as posed, is
largely near-verbatim lexical containment over hard negatives. It is a legitimate and
difficult benchmark, but it is **not** a model of how a cost estimator or a site engineer
phrases a query, and the reported ranking of methods cannot be assumed to transfer.

## 2. Gap and rationale

The open question is not whether BM25 wins on catalogue-derived queries — it does — but
**how much of that advantage survives when the query is a different rendering of the same
item**, and **which kinds of rendering variation destroy it**. This matters because the
mechanism behind lexical dominance (verbatim containment of parameter literals) is exactly
the mechanism that realistic phrasing breaks: a professional writes *3×1.5 cm* where the
catalogue writes *30x15 mm*, *dos* where the catalogue writes *2*, *milímetros* where the
catalogue writes *mm*, and reorders and paraphrases the surrounding prose freely.

No published work quantifies retrieval robustness on parametric construction catalogues
under controlled, attributable linguistic variation, and none isolates *where in the
generation grammar* the variation must occur for a given method family to fail.

## 3. Objectives

**O1.** Quantify the degradation of item-level and parent-level retrieval accuracy on a
large parametric catalogue chapter when queries are referent-preserving alternative
renderings of catalogue items rather than the items' own summaries.

**O2.** Attribute that degradation to specific, individually applied modification types and
to the grammar layer at which they act, producing a *robustness profile* per method family.

**O3.** Determine whether the degradation of composed (stacked) modifications is additive,
sub-additive or super-additive with respect to the isolated effects.

**O4.** Propose and evaluate retrieval methods that are robust to rendering variation,
using the layer-resolved diagnosis of O2 to target the failure mechanism rather than to
tune aggregate scores. This objective is deliberately open as to which methods; §7 fixes
the tracks and the inclusion criteria, not the list.

**O5.** Release the evaluation resource (corpus, query sets, per-condition ground truth,
harness and results) so that the robustness profile is reproducible and extensible.

## 4. Research questions and hypotheses

**RQ1.** How large is the item-level degradation under referent-preserving rendering
variation, and does the parametric collapse widen or narrow?

> **H1 (widening collapse).** Parent-level accuracy stays near its present ceiling
> (0.96–0.997 for neural families) across all conditions, while item-level accuracy falls
> further; the collapse gap Δ = Acc@1(parent) − Acc@1(item) widens and the conditional
> discrimination D = P(item correct | parent correct) degrades far more than concept
> identification does. Rendering variation attacks discrimination, not topic — and it
> should therefore extend the collapse to the lexical family, currently the only one not
> exhibiting it.

**RQ2.** Which modification types and which grammar layers drive the degradation, and is
the pattern method-family specific?

> **H2 (layer specificity).** Damage is governed by the layer at which the variation is
> introduced, and the pattern is family-dependent:
> `param_value` (L1) variation is the dominant source of item-level damage for
> parameter-aware lexical methods, because it rewrites precisely the literal that
> discriminates siblings — the same numeric locus the previous study's numeric /
> non-numeric stratification already isolated; `template` (L3) variation (reordering,
> template paraphrase) is
> near-free for bag-of-words scoring but costly for order- and context-sensitive
> representations; `text_variable` (L2) variation affects concept-level retrieval more
> than item-level, since it rewrites non-discriminating prose.

**RQ3.** Does the method ranking established on catalogue-derived queries survive?

> **H3 (rank inversion).** The lexical advantage is conditional, not general. Under L1
> variation — in particular `unit_conversion` and `num_to_text` — the ordering of method
> families inverts, and approaches that normalise parameter surfaces before matching
> (structured extraction pipelines, parameter-normalising lexical variants) overtake
> tuned BM25. Equivalently: the 0.974 / 0.903 gap between BM25 and rule-based structured
> matching reported previously is an artefact of verbatim containment and should close
> or reverse.

**RQ4.** How do composed modifications behave relative to isolated ones?

> **H4 (super-additivity).** Stacked modifications degrade accuracy more than the sum of
> the isolated per-type effects, because independent surface rewrites jointly exhaust the
> redundancy the scorer relies on.

**RQ5.** What explains the damage — the *amount* of surface change or its *kind*?

> **H5 (overlap mediation).** Per-query lexical and numeric overlap with the target
> mediates most of the lexical methods' degradation: once overlap is controlled, residual
> per-type effects are small for lexical scorers and large for dense encoders. Damage per
> unit of surface change (ΔAcc@1 normalised by token edit distance) is an order of
> magnitude higher for L1 than for L3 modifications.

**RQ6.** Do query-side interventions that are harmful in the verbatim regime become
beneficial as overlap decreases?

> **H6 (crossover).** Generative query expansion (HyDE-style) and query rewriting degrade
> accuracy in the near-verbatim regime — where generated text dilutes exact matching —
> but improve it below a measurable overlap threshold. The crossover point is itself a
> practical result: it tells a practitioner when expansion is worth its cost.

## 5. Materials

### 5.1 Corpus

ADIF price base, chapter **OE — OBRA CIVIL** (subchapters OEA–OEG), rendered by the BC3CAT
deterministic pipeline: **70,242 unique leaves over 83 concepts** after cross-concept twin
de-duplication (OED170$→OED020$) and intra-concept collapse (OEG010$). Mean family size is
≈846 sibling items per concept, with a strongly skewed distribution (OEB alone accounts for
67.6 % of leaves; OEF for 0.1 %). Retrieval targets are the long-form `texto` field; the
matching `resumen` field is retained to replicate the previous study's setting at this
larger scale. This is ~1.5× the size of the corpus used in the previous study and, unlike
it, spans seven subchapters, enabling a cross-subchapter generalisation check.

### 5.2 Query sets (BC3CAT-Syn/OE)

Queries are produced by `bc3cat-dataset` at the **generation-rule level**: a modification is
applied to the concept's grammar (parameter values, conditional text variables, output
templates) and the item is then re-rendered by the *same unmodified* BC3CAT engine. A
synthetic query is therefore a *plausible alternative rendering of the same item*, not
post-hoc string noise. Generation is deterministic and LLM-free at corpus time (an offline
LLM authored only the frozen, human-audited rewrite menus), and two full runs are
byte-identical.

| Set | n | Role |
|---|---|---|
| `OE_texto` (identity) | 70,242 | control: ceiling condition, query = target |
| `OE_resumen` | 70,242 | replication of the previous study's setting on OE |
| `OE_single_texto` | 4,439 over 2,917 leaves | one modification per query, 9 types |
| `OE_stacked_texto` | 4,998 | all applicable modifications, count 2–8 (mode 5) |

Ground truth is decoupled from the query key: `gold_item_key` (item target) and
`parent_key` (concept target); every gold key is verified present in the corpus.

### 5.3 Modification taxonomy

Nine types over three layers, all **referent-preserving** (`omission` and `new_param`,
which do not preserve informational content, are excluded from this release):

| Layer | Type | n (single) | mean token distance |
|---|---|---|---|
| L1 `param_value` | `synonym_label` | 588 | 4.6 |
| L1 | `num_to_text` | 600 | 5.9 |
| L1 | `unit_expansion` | 542 | 8.1 |
| L1 | `unit_conversion` | 549 | 10.9 |
| L2 `text_variable` | `paraphrase` | 211 | 7.3 |
| L2 | `compression` | 548 | 7.7 |
| L2 | `expansion` | 206 | 15.6 |
| L3 `template` | `reorder` | 595 | 22.8 |
| L3 | `template_paraphrase` | 600 | 40.2 |

The token-distance column is central to the analysis: it decouples *how much* surface
changed from *what kind* of change it was, and makes H5 testable.

## 6. Experimental design

**E0 — Controls and replication.**
(a) identity condition `texto→texto`, establishing the per-method ceiling (expected ≈1.0)
and validating the harness; (b) `resumen→texto` on all 70,242 leaves, replicating the
previous study's protocol at 1.5× scale and across seven subchapters. E0(b) also tests
whether the previously tuned BM25 operating point (`k1`=0.60, `b`=0.35) transfers, given
that query length changes ~5× between `resumen` (~14 tokens) and modified `texto`
(~74–78 tokens); a re-sweep on a held-out split is budgeted.

**E1 — Single-modification ablation (O2).** Each method is evaluated on the nine
`single_<type>` conditions. Effects are estimated as **paired deltas against the identity
rendering of the same leaves**, never as raw cross-type Acc@1 comparisons: applicability is
item-dependent (only items with convertible numeric parameters can receive
`unit_conversion`), so a raw comparison across types confounds the modification with the
population of items that admits it. This is a treatment-effect-on-the-treated design.

**E2 — Stacked condition (O1, headline).** The `all_combined` set is the realistic-regime
headline number. Two documented caveats must be carried into the analysis: `reorder` never
co-occurs in stacked items (full-template rewrites collide per field), and
`template_paraphrase` is present in 100 % of them — so E2 is *not* a balanced crossing of
the nine types and cannot by itself identify interaction effects.

**E3 — Dose–response and additivity (O3).** Because of the E2 caveat, testing H4 requires a
balanced compositional design: queries at modification counts 1–5 with randomised type
mixes, generated on request from `bc3cat-dataset`. This is the one data extension the
proposal depends on; without it, H4 is reported as an exploratory regression on the
existing stacked set, with its confounding stated.

**E4 — Method development (O4).** Candidate methods are evaluated on the same conditions,
with development restricted to a held-out split and a frozen test split declared before
any run (a defect explicitly flagged in the previous review cycle).

**E5 — Cross-subchapter generalisation.** All headline results reported both pooled and
stratified by subchapter, and by family size (sibling-count decile), to test whether the
collapse scales with sibling density as predicted.

## 7. Method space

The method space is deliberately open. Admission is governed by criteria, not by a closed
list: a candidate must (i) run against the shared index and query sets, (ii) be reported
under the full protocol of §8 including all conditions, (iii) declare its training data and
its parameter-availability assumptions, and (iv) be reproducible from a versioned config.

**Track A — Carried-over baselines.** The canonical set from the previous study: tuned
BM25 with parameter-aware tokenisation, the best TF-IDF variants, the best dense encoders,
BGE-M3 sparse and ColBERT, RRF hybrids, PRF and cross-encoder reranking.

**Track B — Structured retrieval.** The three-phase extraction pipeline
(`research/structured-retrieval`) and the rule-based structured-matching baselines, in both
realistic and oracle-extraction variants. H3 makes this track a prediction, not a baseline.

**Track C — Query-side normalisation and rewriting.** Unit/number canonicalisation before
matching; parameter slot-filling from free-text queries; HyDE-style expansion and LLM query
rewriting (H6). Note that parameter availability is itself an experimental factor: the
synthetic query records carry a parsed `parameters` dict, but a real query does not — so
methods consuming it are reported as **oracle upper bounds**, and their text-only
counterparts as the deployable condition.

**Track D — Learned representations.** Contrastive fine-tuning with **hard negatives mined
from sibling sets** — the intervention most directly targeted at the collapse mechanism —
and, exploratorily, reinforcement-learning-style optimisation of a retrieval policy against
the item-level objective. Training uses only the held-out concepts; the test split stays
frozen.

**Track E — Two-stage architectures.** Concept retrieval followed by within-family
parameter resolution (constrained reranking, cross-encoder over siblings, or explicit
attribute matching). H1 makes this architecture the natural response to the diagnosis:
concept retrieval is not the bottleneck, so effort belongs downstream of it.

Cost and latency are reported for every admitted method: a contractor-scale deployment is
the practical frame of the paper, and a method that needs an LLM call per query must be
justified against BM25's throughput.

## 8. Metrics and analysis plan

**Primary.** Acc@1 at item level and at parent level (dual-target protocol, `ranx`);
collapse gap Δ = Acc@1(parent) − Acc@1(item); conditional discrimination
D = P(item correct | parent correct).

**Robustness.** Paired degradation δ = Acc@1(identity) − Acc@1(condition) per method and
condition; normalised sensitivity δ / (mean token edit distance), i.e. damage per unit of
surface change.

**Secondary.** Recall@5/@10, MRR, nDCG@10; rank of the gold item; distribution of the
rank-1 error (sibling of the correct concept vs different concept) — the error taxonomy
that operationalises "collapse".

**Explanatory covariates.** Per-query lexical coverage and numeric coverage against the
target, computed exactly as in the review analysis (94.1 % / 99.93 % in the verbatim
regime), reported per condition. These are the mediators of H5 and the quantitative answer
to the reviewers' central objection.

**Inference.** Paired bootstrap (10,000 resamples) with Holm–Bonferroni and
Benjamini–Hochberg correction, consistent with the existing harness. For per-type effects, a
mixed-effects model with random intercepts for concept and for leaf, and fixed effects for
modification type, count and token distance, separating the effect of the modification from
the intrinsic difficulty of the item family. Effect sizes with confidence intervals
throughout; `paraphrase` and `expansion` (n ≈ 206–211) are reported with their wider
intervals, or pooled at layer level, rather than over-read.

## 9. Threats to validity

| Threat | Mitigation |
|---|---|
| Synthetic queries are not real professional queries | Framed explicitly as *rendering variation*, not as user-query simulation. Modifications act on the generation grammar, so every query is a legitimate alternative rendering of the item. A real-query validation anchor (200–500 estimator queries from Telice) is the highest-value extension and is scoped as future work, or as a late addition if the data can be obtained in time. |
| Rewrite-menu artefacts | Known pantry artefacts (token doubling, one documented semantic drift) are catalogued and traceable per item through the modifications sidecar; sensitivity analysis excluding affected items. |
| Unbalanced per-type n and applicability | Paired within-leaf design (E1), mixed model with concept random effects, layer-level pooling for thin types. |
| Stacked set is not a balanced crossing | E3 balanced dose design; otherwise H4 reported as exploratory with confounding stated. |
| Development/test contamination | Splits declared and versioned before any run; tuning (including any BM25 re-sweep) on the development split only. |
| Generator/evaluator contamination | Generation is LLM-free at corpus time; rewrite menus were authored offline and human-audited, independently of any model evaluated. |
| Ceiling artefacts in the identity control | Corpus de-duplicated so that every `(resumen, texto)` pair is unique; the control verifies rather than assumes the ceiling. |

## 10. Expected contributions

1. **A layer-resolved robustness profile** of retrieval methods on parametric construction
   catalogues: the first quantification of *which* linguistic variation breaks *which*
   method family, at item and concept level.
2. **A conditional reading of lexical dominance.** Establishing the regime boundary —
   the overlap level at which tuned BM25 stops winning — converts a benchmark result into
   an engineering decision rule.
3. **A method contribution** (O4/Track D–E) targeted at the diagnosed mechanism rather
   than at aggregate scores.
4. **An open, reproducible resource**: BC3CAT-Syn/OE query sets with per-condition ground
   truth and traceable modification logs, plus the evaluation harness and results.
5. **Practical guidance for construction cost workflows**: what a BoQ-to-catalogue matching
   component should do, at what accuracy, cost and latency, and where a human must stay in
   the loop.

## 11. Work plan

| Phase | Work | Output |
|---|---|---|
| P1 | Harness adaptation: decoupled gold keys, flat query `parameters`, per-query-set index/run layout, per-condition and per-count slices | Runnable pipeline on OE |
| P2 | E0 controls and replication; operating-point re-sweep on the development split | Ceiling + baseline tables; transferability of `k1`/`b` |
| P3 | E1 single-modification ablation over Tracks A–B; overlap covariates | Robustness profile; H1–H2, H5 |
| P4 | E2 stacked headline; E5 stratifications | Realistic-regime headline; H3 |
| P5 | E3 balanced dose design (requires data extension) | H4 |
| P6 | E4 method development (Tracks C–E), frozen test evaluation | H6; method contribution |
| P7 | Analysis, figures, manuscript, artefact release | Submission |

## 12. Reproducibility

Frozen query sets with recorded SHA-256 digests; versioned split files; one YAML config per
method variant; run artefacts under `runs/{collection}/{queryset}/{method}`; statistical
tests scripted end-to-end; code and data released under the existing MIT / CC-BY 4.0 dual
licence, with an AI-assistance disclosure consistent with the parent release.

## 13. Open decisions

1. **Method scope on OE** — canonical set from the previous paper, with or without a full
   BM25 grid re-sweep at the new query length.
2. **Query-side parameters** — whether synthetic-query `parameters` are rebuilt into
   parameter tokens (oracle) or queries are treated as text-only (deployable). Proposed:
   both, reported as bounds.
3. **E3 balanced dose design** — whether `bc3cat-dataset` generates it; H4 depends on it.
4. **Real-query anchor** — whether 200–500 Telice estimator queries can be obtained within
   the timeline; it is the single strongest answer to the practical-impact objection.
5. **Scope of Track D** — how far reinforcement learning is pursued relative to contrastive
   fine-tuning with sibling hard negatives.
