# Sprint LWN-05 — Phase E (Comparative Error Taxonomy + Paper Draft)

**Tasks from backlog:** E1 (comparative error taxonomy across rules / CLS / BIO), E2 (paper draft)
**Prerequisites:** Sprint LWN-04 complete (all C/D diagnostics done)

---

## Context

Sprints LWN-01 → LWN-04 have produced the full evidence base for a paper:
- LWN-03: BIO oracle 3.13% / pipeline 3.10% on 16,590 short-text queries
- LWN-04: five mechanistic diagnostics (CLS⊕BIO contingency, error taxonomy, typo tracer, speed benchmark, cross-format diagnostic, frozen-encoder ablation)
- LW-06/07 (parent branch): CLS oracle 21.2%, frozen CLS 0.58%
- SEPLN baselines: rules 91.4%, Phi-4 88.6%

This sprint takes the next step on the protocol roadmap (§6 Phase E):
1. **E1 — Comparative error taxonomy.** Same categories as the SEPLN paper (E1-WRONG_CONCEPT, E2-PARTIAL_EXTRACT, E2-WRONG_VALUE) plus new BIO-specific categories (E3-TAGGER_MISS, E3-NORMALIZER_MISS). Apply uniformly across rules, CLS classifier, and BIO tagger so the dominant failure mode of each method is explicitly comparable.
2. **E2 — Paper draft.** A structured markdown draft (sections, tables, key claims, references) that can be translated to LaTeX for whichever venue. Title candidates from protocol §6 E2: "Architectural choices in lightweight parameter extraction: when CLS classifiers exploit format-specific cues and what survives at the token level."

**D2 (query perturbation) remains deferred** to a follow-up sprint if the paper needs additional robustness data; this sprint focuses on the writeup since the existing diagnostics already establish the central claim.

Read these for full context:
- `docs/structured-retrieval/RESEARCH_PROPOSAL.md` — the SEPLN paper proposal (parent paper this extends)
- `docs/structured-retrieval/RESEARCH_LOG.md` — the SEPLN paper's error analysis
- `docs/lightweight-extraction/RESEARCH_LOG_LIGHTWEIGHT.md` — CLS classifier results (LW-03 through LW-07)
- `docs/lightweight-extraction-ner/RESEARCH_LOG_LIGHTWEIGHT_NER.md` — this branch's results (LWN-01 through LWN-04)
- All `analysis/` CSV outputs from LWN-03 and LWN-04

**Do not modify any existing files.** This sprint adds analysis + paper draft only.

---

## Objectives

### E1 — Comparative error taxonomy

Apply a uniform error category scheme across all three Stage 2 methods on the SAME 16,590-query short-text test:

| Category | What it means |
|---|---|
| E1-WRONG_CONCEPT | Stage 1 retrieved the wrong parent_key (only relevant for non-oracle conditions) |
| E2-PARTIAL_EXTRACT | Stage 2 extracted some axes correctly but missed others |
| E2-WRONG_VALUE | Stage 2 extracted a value but it's the wrong canonical value |
| E2-NULL_EXTRACT | Stage 2 returned None for a required axis |
| E3-TAGGER_MISS | (BIO-specific) Tagger emitted no span for a required axis |
| E3-NORMALIZER_MISS | (BIO-specific) Tagger emitted a span but normalizer rejected it |

For each method (rules, CLS, BIO) on the same 16,590-query oracle eval:
- Count missed queries by category
- Per-axis breakdown of dominant errors
- Output: `analysis/comparative_error_taxonomy.csv`, `analysis/comparative_error_taxonomy.md` (formatted table)

The point of this comparison: the rules baseline succeeds at 91.4% but fails on a different distribution of errors than the neural methods. Knowing which queries each method gets wrong, and which ones get rescued by Stage 3 catalog lookup, is what makes the paper's argument that "the gap isn't an architectural choice, it's a corpus property" defensible.

### E2 — Paper draft

Draft `docs/lightweight-extraction-ner/PAPER_DRAFT.md` with:

1. **Abstract** (~200 words)
2. **Introduction** — situated against SEPLN paper; the question this extends
3. **Background** — BC3CAT structure, prior baselines, the Stage-2-bottleneck framing
4. **Methods**
   - Architecture overview (rules, CLS classifier, BIO tagger)
   - Training regime (long-only training; deliberate cross-distribution test)
   - Span normalizer and surface-form override mechanics
5. **Experiments**
   - Cross-distribution test (16,590 queries; rules / CLS / BIO; full FT and frozen)
   - Per-axis recall breakdown
   - Cross-format paired diagnostic (D1)
   - CLS ⊕ BIO contingency (C3.a)
   - Speed benchmark (C4)
6. **Results**
   - Headline table (rules vs CLS vs BIO oracle/pipeline; full FT and frozen)
   - Mechanistic per-axis story (CONDICIONES collapses; TRABAJO survives)
   - Frozen ablations (representation adaptation is necessary AND insufficient)
7. **Discussion**
   - Why token-level supervision *increases* anchor-dependence (counter-intuitive finding)
   - Implications for parametric retrieval beyond BC3CAT
   - Limits of the long-only-training paradigm; data-side directions
8. **Related work** — span tagging in IE, parametric retrieval, structure-aware QA
9. **Conclusion** — the negative-architecture claim and what it means
10. **References**

Format: markdown with key tables and claim-by-claim source pointers (e.g., "(LWN-03 §C2 result table)") so the LaTeX translation later is mechanical.

The draft should be self-contained — a colleague reading only the paper draft (without the research log) should understand the full argument and verify each claim against the cited diagnostic.

---

## Acceptance Criteria

- [x] `analysis/comparative_error_taxonomy.csv` + `analysis/comparative_error_taxonomy_per_axis.csv` cover all three methods on the same 16,590 queries
- [x] `docs/lightweight-extraction-ner/PAPER_DRAFT.md` exists with all 10 sections filled in
- [x] Every numerical claim in the paper has a source pointer (see §10 of the draft)
- [x] Headline table includes all conditions (rules pipeline + oracle, Phi-4 pipeline + oracle, CLS full FT pipeline + oracle, CLS frozen pipeline + oracle, BIO full FT pipeline + oracle, BIO frozen oracle, dense_e5 baseline, BM25 param-aware)
- [x] `RESEARCH_LOG_LIGHTWEIGHT_NER.md` updated with sprint summary
- [x] `CLAUDE_LIGHTWEIGHT_NER.md` Sprint History updated

---

## Out of Scope

- LaTeX submission-ready formatting (deferred until venue is chosen)
- Bibliography file (cite by author-year in the markdown; convert to BibTeX after)
- D2 query perturbation (deferred; the paper has enough diagnostic depth without it)
- Camera-ready figures (the markdown's tables are sufficient; figure generation comes later)

---

## E1 / E2 Result Report

**Date:** 2026-04-30

### E1 — Comparative error taxonomy

Same 16,590 short-text queries, oracle conditions, uniform categorization across all three Stage 2 methods:

| Method | ALL_CORRECT | PARTIAL | WRONG_VALUE | ALL_NULL |
|---|---|---|---|---|
| Rules | **93.51%** | 6.49% | 0.00% | 0.00% |
| CLS classifier (full FT) | 21.57% | 78.37% | 0.05% | 0.00% |
| BIO tagger (full FT) | **0.51%** | 97.44% | 0.00% | 2.04% |

Per-axis NULL vs WRONG counts on missed queries:

| Axis | Rules NULL | Rules WRONG | CLS NULL | CLS WRONG | BIO NULL | BIO WRONG |
|---|---|---|---|---|---|---|
| TRABAJO | **1,017** | 0 | 0 | **7,777** | 1,346 | 5 |
| BANDA DE MANTENIMIENTO | 28 | 0 | 0 | **6,382** | **7,310** | 0 |
| TIPO DE TERRENO | 0 | 0 | 0 | **4,718** | **5,310** | 0 |
| CONDICIONES DE EJECUCIÓN | 34 | 0 | 3 | 748 | **16,439** | 0 |
| Nº TUBOS | 0 | 0 | 0 | 0 | **13,837** | 0 |
| PROFUNDIDAD | 0 | 0 | 0 | 0 | 128 | 0 |

**Three distinct failure profiles emerge:**

- **Rules** — high accuracy on the limited set of patterns it hand-encodes; failures are NULL extractions on out-of-template surface forms (TRABAJO 1,017). When rules return a value, it's correct.
- **CLS** — confident-wrong: the softmax forces a commit, so failures are WRONG values rather than nulls (TRABAJO 7,777, BANDA 6,382, TIPO DE TERRENO 4,718).
- **BIO** — conservative-null: the per-token decision returns no canonical when the span is uninterpretable (Nº TUBOS 13,837, CONDICIONES 16,439).

Stage 3 catalog lookup amplifies the asymmetry: NULLs are ignored (partial-match recovery still works); WRONGs actively exclude the correct item. This explains why BIO reaches 3.13% Acc@1 from 0.51% all-axes-correct (catalog lookup tolerates NULLs) while CLS reaches 21.2% from 21.6% all-axes-correct (lookup is unforgiving of WRONGs). Per-axis correctness rate is what drives the headline number; the soft-commit error mode is recoverable through Stage 3 only some of the time.

Saved: `analysis/comparative_error_taxonomy.csv`, `analysis/comparative_error_taxonomy_per_axis.csv`.

### E2 — Paper draft

`docs/lightweight-extraction-ner/PAPER_DRAFT.md` — 10 sections, ~7 pages of markdown, all numerical claims source-pointed to LWN-01 through LWN-05 and the analysis CSVs. Title: *Architectural Choices in Lightweight Parameter Extraction: When CLS Classifiers Exploit Format-Specific Cues and What Survives at the Token Level.*

Section structure:
1. Abstract (~210 words)
2. Introduction — situated against SEPLN; the question, the headline result, the contributions
3. Background — BC3CAT, the Stage-2-bottleneck framing, the cross-distribution setup
4. Methods — both architectures, the deterministic normalizer, the training data alignment, frozen ablations
5. Experiments — table of 7 diagnostics with sources
6. Results — headline table, CLS⊕BIO contingency, cross-format paired diagnostic, per-axis recall, error taxonomy, comparative error structure (E1), speed benchmark
7. Discussion — CLS-vs-BIO confident-wrong/conservative-null asymmetry; why BIO is worse; cross-distribution gap is corpus-fundamental; frozen ablations rule out the trivial alternative; implications for parametric retrieval; limitations
8. Related work
9. Conclusion
10. References + source-pointer table

The draft is self-contained: a colleague reading only it (without the research log) can verify each numerical claim against the cited sprint or analysis CSV.
