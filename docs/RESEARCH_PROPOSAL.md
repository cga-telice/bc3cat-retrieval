# Structure-Aware Retrieval for Parametric Catalogs Using LLM-Based Parameter Extraction

**Research Proposal — Congress Submission Draft (Revised)**

| Field        | Value                                              |
|--------------|----------------------------------------------------|
| **Author**   | César                                              |
| **Date**     | March 2026                                         |
| **Target**   | SEPLN Congress                                     |
| **Status**   | Revised draft — incorporates colleague feedback    |
| **Deadline** | End of March 2026                                  |

---

## 1. Context and Motivation

### 1.1 The General Problem: Structure-Blind Retrieval in Parametric Domains

Many real-world information retrieval scenarios involve **parametric catalogs** — collections where items share a common semantic concept but differ along discrete, structured parameter axes. Examples include:

- **Construction price catalogs** (e.g., BC3CAT): work items defined by concept + parameters such as material type, dimensions, execution conditions.
- **E-commerce product catalogs**: a laptop model configured by RAM, storage, screen size, CPU.
- **Industrial parts catalogs**: a bearing defined by bore diameter, outer diameter, width, seal type.
- **Configurable service products**: an insurance policy defined by coverage type, deductible, term, rider options.

In all these domains, the catalog structure follows a common pattern:

> **item = concept + parameter combination**

Standard retrieval methods — both lexical (BM25) and neural (dense embeddings, sparse learned, late interaction) — treat items as flat text. They are **structure-blind**: they ignore the internal decomposition into concept and parameters. This leads to a characteristic failure mode:

> **Semantic models achieve near-perfect concept-level retrieval but collapse parametric variants into near-identical representations, failing at the item level.**

This failure is not a limitation of any specific model architecture; it is a structural mismatch between the retrieval method and the data organization. We argue this constitutes a distinct and underexplored **retrieval failure mode in parametric domains**.

### 1.2 The BC3CAT Case: Empirical Evidence

We ground this work in the BC3CAT dataset, a Spanish-language construction price catalog used as a standard in the Spanish construction industry. The catalog contains work descriptions with associated unit prices, organized hierarchically: each item belongs to a concept group and is defined by a combination of parametric values (e.g., terrain type, number of tubes, execution conditions).

Previous work benchmarked BM25, dense embeddings (BGE-M3, E5, GTE), sparse learned models (BGE-M3 sparse), and ColBERT (late interaction) on this dataset. The results on the full dataset (16,590 queries) reveal the structural gap clearly:

| Method                        | Parent Acc@1 | Item Acc@1 | Gap         |
|-------------------------------|:------------:|:----------:|:-----------:|
| BM25 (param-aware tokens)     | 98.5%        | 97.4%      | **−1.1pp**  |
| BM25 (standard unigram)       | 97.3%        | 86.9%      | **−10.4pp** |
| BGE-M3 ColBERT                | 99.7%        | 44.8%      | **−54.9pp** |
| BGE-M3 Sparse                 | 99.4%        | 12.5%      | **−86.9pp** |
| BGE-M3 Dense                  | 96.0%        | 12.7%      | **−83.3pp** |
| Dense E5                      | 98.2%        | 13.4%      | **−84.8pp** |

Two findings stand out. First, all neural methods suffer a dramatic parent-to-item accuracy collapse: they achieve 96–99.7% at the concept level but only 12–45% at the item level. The root cause is the parametric structure: thousands of items share the same concept (e.g., "Hormigonated polyethylene tube canalization 110mm") but differ only in combinations of parameter values. The largest concept groups contain up to 6,336 parametric variants across 5 parameter axes. Semantic models collapse these variants into near-identical representations.

Second, BM25 with parameter-aware tokenization achieves 97.4% item-level Acc@1 — far above any neural method. However, this result must be interpreted carefully. The benchmark uses catalog-generated short descriptions (*resumen*) as queries against catalog-generated long descriptions (*texto*). Both are produced from the same underlying catalog structure, resulting in high lexical overlap between query and target. BM25's exact token matching exploits this overlap directly.

In real-world deployment scenarios — cost estimators mapping project specifications to catalog entries, field engineers reconciling daily reports with contractual line items — queries are drafted independently with company-specific wording, regional terminology, abbreviations, and implicit context. Under these conditions, the lexical overlap that BM25 depends on is substantially reduced. Standard BM25 without parameter-aware tokenization already drops to 86.9% even on the catalog-generated benchmark, and real-world phrasing variation would erode performance further.

Neural methods, by contrast, are designed to tolerate exactly this kind of phrasing variation — but they fail at the item level because they cannot disambiguate parametric variants. The proposed structure-aware pipeline addresses this by combining the semantic robustness of dense retrieval (for concept identification) with explicit parameter extraction (for variant disambiguation), aiming to achieve strong item-level accuracy that generalizes beyond catalog-generated queries.

---

## 2. Dataset Structure

Each BC3CAT catalog item is a JSON object with the following fields:

- **item_key** — unique item identifier (e.g., `OEB030aaa`)
- **parent_key** — identifier of the concept group (e.g., `OEB030$`)
- **concept** — human-readable name of the concept group, shared by all variants
- **parameters** — dictionary of parameter axes, each with a label and a set of discrete values
- **text** — full natural-language description of the item (generated from concept + parameters)

The dataset contains 47,508 leaf items organized into 25 concept groups. Group sizes range from 3 to 6,336 variants, with the largest groups having 5 parameter axes (each with 3–8 discrete values), yielding fully combinatorial item spaces.

---

## 3. Proposed Approach: Structure-Aware Three-Stage Retrieval

### 3.1 Core Insight

The problem is not a single hard retrieval problem. It decomposes into two much easier sub-problems separated by a clean interface:

1. **Concept retrieval** — already solved by existing dense models (96–99.7% Acc@1).
2. **Parameter resolution** — the actual bottleneck, currently unaddressed.

A structure-aware pipeline explicitly targets this decomposition.

### 3.2 Pipeline Architecture

```
Query
  │
  ▼
[Stage 1] Dense concept retrieval (E5)
  │  → candidate set: all items in the retrieved concept group
  ▼
[Stage 2] LLM parameter extraction (slot-filling via local LLM)
  │  → extracted: {param_axis: value, ...}
  ▼
[Stage 3] Deterministic catalog lookup
  │  → exact match on extracted parameters
  ▼
Result (single item or ranked sub-group on partial extraction)
```

| Stage | Name                   | Method                              | Expected Performance                    |
|:-----:|------------------------|-------------------------------------|-----------------------------------------|
| **1** | Concept retrieval      | Dense embedding (E5)                | ~98.2% Acc@1 (already benchmarked)      |
| **2** | Parameter extraction   | LLM-based slot-filling from query   | Ablated across model sizes              |
| **3** | Exact catalog lookup   | Deterministic match on parameters   | Lossless given correct extraction       |

**Stage 1 — Concept Retrieval.** A dense embedding model (E5) retrieves the most relevant concept group for the natural language query. E5 is chosen as the Stage 1 model because it is the lightest among the benchmarked dense models while maintaining strong parent-level performance (98.2% Acc@1). The query is matched against concept-level representations, not item-level ones. The output is a shortlist of all variants belonging to the retrieved concept group.

**Stage 2 — LLM Parameter Extraction.** A local LLM receives the original query and the parameter schema for the retrieved concept group (axis labels and their discrete value sets). Its task is structured slot-filling: for each parameter axis, identify which value the query refers to.

*Example:* given the query *"canalización nocturna de 3 tubos bajo vías, volumen relevante"* and the schema for `OEB030$`, the LLM extracts:
```json
{
  "Nº TUBOS": 3,
  "TIPO DE TERRENO": "Bajo vías",
  "TRABAJO": "Nocturno",
  "CONDICIONES DE EJECUCIÓN": "Volumen relevante"
}
```

The LLM generalizes across phrasing variants ("triple" → 3, "nocturnal" → "Nocturno") without task-specific training, reasoning over the parameter schema rather than matching patterns.

**Stage 3 — Deterministic Catalog Lookup.** Extracted parameter values are matched against the catalog. The parameter space is fully enumerated; given correct extraction, the match is exact and lossless. If a value cannot be resolved, the stage returns a ranked shortlist of candidates differing only on the unresolved axis.

### 3.3 Why This Approach

- **Exploits problem structure.** The parent–item accuracy gap proves concept retrieval is solved. The pipeline targets the actual bottleneck: parameter disambiguation.
- **Extraction, not ranking.** The LLM performs structured slot-filling over a small constrained output space, not ranking over thousands of near-identical candidates.
- **Zero-shot, no training required.** Stage 1 reuses existing dense models. Stage 2 is zero-shot prompting. Stage 3 is deterministic. Evaluation uses existing labeled query–item pairs.
- **Practical and self-contained.** Stage 2 uses a local open-source LLM (e.g., Llama 3.1 8B, Qwen 2.5 7B via Ollama), deployable without external APIs.
- **Directly comparable to baselines.** Same benchmark, query set, and metrics as prior work.

---

## 4. Evaluation Plan

### 4.1 Metrics and Benchmark

The pipeline is evaluated on the existing BC3CAT benchmark using the same methodology as prior work. Primary metric: **item-level Acc@1**. Additional metrics: Recall@10, MRR, nDCG@10.

### 4.2 Stage 2 Ablations

| Configuration                       | Model Size   | Notes                                                        |
|-------------------------------------|:------------:|--------------------------------------------------------------|
| Rule-based extraction (regex)       | —            | No LLM; establishes the *floor* — how much is solvable with trivial token/number matching alone |
| LLM slot-filling — small            | ~3B params   | E.g., Qwen 2.5 3B; minimal compute                          |
| LLM slot-filling — medium           | ~8B params   | E.g., Llama 3.1 8B or Qwen 2.5 7B                           |
| LLM slot-filling — large            | ~70B or API  | Performance ceiling; practical upper bound                    |

The gap between the rule-based floor and LLM conditions quantifies the value added by language understanding over simple pattern matching.

### 4.3 Oracle Conditions

A **Stage 1 oracle** condition (the correct concept group is given as ground truth, bypassing E5 retrieval) isolates Stage 2+3 performance and enables diagnostic interpretation:

- If the oracle condition yields substantially higher Acc@1 than the full pipeline, the dominant error source is Stage 1 (E5 retrieves the wrong concept). Improving the concept retriever would be the priority.
- If oracle and full pipeline perform similarly, Stage 1 is not the bottleneck — errors come from Stage 2 (extraction) or Stage 3 (ambiguous queries).

Additionally, combining the oracle with the rule-based Stage 2 variant (`oracle + regex`) establishes the *ceiling* for extraction without any LLM — the maximum achievable by trivial pattern matching when concept retrieval is perfect.

### 4.4 Error Analysis

Characterize failure modes:
- (a) Stage 1 retrieves the wrong concept group.
- (b) Stage 2 extracts incorrect parameter values.
- (c) The correct item is unreachable (truly ambiguous queries).

---

## 5. Expected Contributions

1. **Identification of a retrieval failure mode in parametric domains.** We demonstrate that standard retrieval methods — lexical and neural — systematically fail when items share semantic content and differ only along structured parameter axes. This is grounded in benchmark results showing 96–99% parent-level vs. 13–45% item-level accuracy.

2. **A structure-aware retrieval architecture.** The three-stage pipeline separates concept retrieval from parameter resolution, matching the natural structure of parametric catalogs.

3. **Empirical evaluation of LLM-based parameter extraction.** We ablate across model sizes to determine the minimum model capacity for effective slot-filling, informing practical deployment.

4. **Results on a real-world Spanish-language dataset (BC3CAT).** All baselines and the proposed pipeline are evaluated on the same benchmark with identical metrics.

---

## 6. Future Work and Extensions

The following directions are identified for subsequent publications:

- **Lightweight alternatives to LLM extraction.** The parameter extraction task (Stage 2) is essentially multi-head classification over small discrete label sets. A lightweight BERT-based model with per-axis classification heads, or a NER-based approach, could achieve comparable accuracy at a fraction of the computational cost. This is a natural follow-up: the current work establishes the pipeline and the LLM baseline; a second study can investigate efficient alternatives.

- **Cross-domain generalization.** The structure-aware retrieval framework is domain-agnostic. Evaluation on additional parametric datasets (e-commerce product catalogs, industrial parts databases, configurable service products) would validate the generality of the approach and the failure mode identification.

- **Formal problem definition.** A formal mathematical framing of structure-aware retrieval — defining the concept space, parameter space, and the decomposition — would strengthen the theoretical contribution and enable comparison with related structured prediction methods.

---

## 7. Open Questions (Pre-Implementation)

These decisions should be resolved before Sprint 1:

1. **Stage 1 retrieval unit:** Retrieve against concept-level text or aggregated item text? Concept text is shorter and more discriminative; item text may encode parameter information.

2. **Stage 2 prompt design:** How much of the parameter schema to show the LLM? Full value lists vs. axis labels only vs. few examples. Affects prompt length for large groups.

3. **Handling partial extraction:** If Stage 2 fails to resolve one axis (query is silent on a parameter), should Stage 3 return the full sub-group or apply a prior (e.g., most frequent value)?

4. **Evaluation scope:** Include only queries with unique item-level ground truth, or also concept-level-only queries? Existing labels should be audited.

5. **Prompt language:** Spanish (matching the catalog), English, or mixed-language? Multilingual models may perform differently depending on prompt language.

---

## 8. Changelog

| Version | Date       | Changes                                                                 |
|---------|------------|-------------------------------------------------------------------------|
| v0.1    | March 2026 | Initial draft                                                           |
| v0.2    | March 2026 | Incorporated colleague feedback: generalized framing, LLM-vs-lightweight discussion, title update |
| v0.3    | March 2026 | Added pipeline flow diagram, E5 rationale for Stage 1, expanded oracle/ablation logic from RP |
| v0.4    | March 2026 | Added BM25 baselines from repo; reframed with catalog-generated query caveat from prior paper context |

---

*End of proposal — this document serves as persistent context for all subsequent implementation sprints.*
