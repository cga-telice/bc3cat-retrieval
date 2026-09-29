# CLAUDE.md — branch `research/synthetic-oe`

Branch-specific contract. Read after the root [`CLAUDE.md`](../../CLAUDE.md), together with
[`STATE.md`](STATE.md) and the active sprint's design document. That is the complete
start-of-session context; target under 45 KB combined (raised from 25 KB on 2026-09-27, with
the Plan budget in the root contract; the four together stood at 41 KB when S3 opened).

## Session preamble — do this first, every time

Before reading anything else or touching a file, print and check:

```bash
git rev-parse --show-toplevel     # must be the main checkout, with no .claude/worktrees/ in the path
git branch --show-current         # must be research/synthetic-oe
ls data/processed/OE_*.json       # five files must be present
```

**If you are in a worktree, stop and say so.** Work on this branch happens in the main
checkout, which is what `docker-compose` mounts as `/work`. A worktree created without NTFS
junctions to `data/`, `index/`, `runs/`, `logs/` and `hf-cache/` cannot reach the corpus, and
a session opened there also misses uncommitted work in the main checkout — it will report
files as absent that are simply elsewhere. Do not create a worktree for this branch, and
decline if offered one. See D-018; a parallel worktree for S9–S11 is created deliberately,
with its junctions, and recorded in `STATE.md` while it lives.

## What this branch does

It runs the retrieval harness on the ADIF **OE** chapter (OBRA CIVIL, subchapters OEA–OEG)
using **BC3CAT-Syn/OE** synthetic query sets, to measure how much retrieval accuracy
survives when the query is a different *rendering* of the same catalogue item rather than
the item's own summary.

The scientific frame is in [`RESEARCH_PROPOSAL.md`](RESEARCH_PROPOSAL.md); the sprint
decomposition in [`RESEARCH_PLAN.md`](RESEARCH_PLAN.md). Read them when you need the *why*;
this file is the *how*.

**The one-sentence bet.** The previous study's headline — tuned BM25 at 0.974 item-level
Acc@1 — rests on near-verbatim containment (the target holds 94.1 % of query tokens and
99.93 % of its numbers). This branch tests whether that advantage survives rendering
variation, and expects it not to.

## Operating rules

Binding on every sprint. They exist because the previous review cycle found three distinct
query samples reported as one, a numeric bonus that was dead code, and a hybrid baseline
taken from a different system. None of those were scientific errors; all were provenance
failures.

1. **Provenance.** Every number in a report or the manuscript carries
   `{run_id, config SHA, code commit, query-set SHA-256}`. Reports are generated from
   `runs/`, never typed. A number without a stamp does not exist.
2. **Splits.** The dev/test split is declared in `SPLITS.md` before any run, and partitions
   **by concept**, not by leaf — otherwise fine-tuning and hyper-parameter sweeps see
   siblings of test items. No tuning, model selection or threshold setting ever touches
   test.
3. **One-shot test.** The frozen test evaluation runs once (sprint S12). Anything requiring
   a re-run invalidates the sprint that caused it and is reported as such.
4. **Sprint reports.** Every sprint closes with `sprints/SPRINT_XX_REPORT.md`: what ran,
   the numbers, which hypothesis moved, what is now known to be wrong, what the next sprint
   inherits.
5. **Negative results close successfully.** A falsified hypothesis is an outcome, not a
   failure. The plan has contingency branches, not recovery plans.

## Data

Under `data/processed/`, alongside the existing `OEB_*` files, with `COLLECTION = "OE"`.

| File | Role |
|---|---|
| `OE_texto.json` | document corpus — original TEXTO, deduplicated (retrieval **targets**) |
| `OE_resumen.json` | original RESUMEN of the same leaves (baseline queries) |
| `OE_single_texto.json` | synthetic queries, **one** modification each |
| `OE_stacked_texto.json` | synthetic queries, **all** applicable modifications stacked |
| `OE_concept_schema.json` | per concept: name, axes, item_keys, num_items |

Corpus: **70,242 unique leaves over 83 concepts**, after cross-concept twin de-duplication
(OED170$→OED020$) and intra-concept collapse (OEG010$). Mean family ≈846 leaves; OEB alone
is 67.6 % of the corpus, OEF 0.1 %.

Query sets: single **4,439** over 2,917 leaves across 9 modification types; stacked
**4,998**, `modification_count` 2–8 (mode 5).

Provenance: `bc3cat-dataset` branch `synthetic`, `scripts/package_for_retrieval.py`, commit
`8998875`. Generation is deterministic and LLM-free at corpus time; an offline LLM authored
only the frozen, human-audited rewrite menus. Digests are recorded in [`INTAKE.md`](INTAKE.md).

## Schema differences from OEB — the things that break

Query records differ from corpus records in two ways that break the existing harness:

```json
{"item_key": "OEA010aaba_syn_3348c2069a08",
 "parent_key": "OEA010$",            // gold at concept level
 "gold_item_key": "OEA010aaba",      // gold at item level
 "parameters": {"A": "3x1.5 cm", "B": "Diurno", "F": null},   // FLAT, values rewritten
 "text": "...",                       // modified TEXTO
 "modification_types": [...], "modification_count": 5}
```

1. **Gold is decoupled from `item_key`.** `retrieve.ipynb` and `metrics.ipynb` assume
   `gold == query key`. Synthetic queries would be silently dropped. A query whose gold key
   is absent from the corpus must **fail loud**.
2. **`parameters` is flat.** `normalize_parameters_field` / `build_param_tokens` expect
   nested blocks and raise on a flat string. This affects `param_tokens`,
   `text_word_params`, `param_phrases` — i.e. the inputs of `bm25_unigram_params` and the
   `tfidf_unigram_phrases_*` family.
3. **Three query sets per collection.** The loader is keyed on `COLLECTION` alone, and its
   fixed record projection drops `gold_item_key` and `modification_*`.
4. **Path collisions with OEB.** See the root CLAUDE.md defect list.
5. **Slices.** `metrics.ipynb` knows only `has_numbers`. Needed: per condition, per
   modification type, per `modification_count`, per subchapter, per family-size decile.

## Modification taxonomy

Nine types over three grammar layers, all **referent-preserving**. The layer is not
cosmetic: it predicts which method family should break.

| Layer | Types | Why it matters |
|---|---|---|
| **L1 `param_value`** | `synonym_label`, `num_to_text`, `unit_expansion`, `unit_conversion` | Rewrites the literal that discriminates siblings. Expected to be the dominant source of item-level damage for parameter-aware lexical methods. |
| **L2 `text_variable`** | `paraphrase`, `compression`, `expansion` | Rewrites non-discriminating prose. Expected to affect concept-level more than item-level. |
| **L3 `template`** | `reorder`, `template_paraphrase` | Changes order and structure. Expected near-free for bag-of-words, costly for order-sensitive representations. |

Condition is derived, not stored: `single_<type>` if `modification_count == 1`, else
`all_combined`.

## Known caveats to carry into every analysis

- **Applicability is item-dependent.** Only items with convertible numeric parameters can
  receive `unit_conversion`. Raw Acc@1 comparisons across types confound the modification
  with the population that admits it. Always report **paired deltas against the identity
  rendering of the same leaves** — treatment-effect-on-the-treated.
- **The stacked set is not a balanced crossing.** `reorder` never co-occurs;
  `template_paraphrase` is in 100 % of stacked items. It gives the headline; it cannot
  identify interactions.
- **Thin slices.** `paraphrase` n=211 and `expansion` n=206. Report with their intervals or
  pool at layer level; do not over-read.
- **Pantry artefacts.** Token doubling ("tubos tubos", "mm mm") and one documented semantic
  drift ("con topo" → "con topografía") were kept as documented stress. They are traceable
  per item through the modifications sidecar; run sensitivity analyses excluding them.

## Layout on this branch

```
index/{collection}/{method}
runs/{collection}/{queryset}/{method}
docs/synthetic-oe/
  CLAUDE.md STATE.md SPLITS.md INTAKE.md                # contracts
  DECISIONS.md                                          # record — append-only, searched
  DELIVERIES.md                                         # record — one section per upstream
                                                        #   delivery; split out of INTAKE.md on
                                                        #   2026-09-27 when it passed 12 KB
  DATASET_DEFECTS.md                                    # record — what is wrong with the corpus,
                                                        #   classified P (upstream) / H (harness) /
                                                        #   C (property of the catalogue)
  archive/                                              # record — dated snapshots
  RESEARCH_PROPOSAL.md RESEARCH_PLAN.md SPRINTS.md      # plans
  sprints/SPRINT_XX_DESIGN.md                           # plan, frozen at sprint start
  sprints/SPRINT_XX_AMENDMENTS.md                       # record — changes to the frozen design,
                                                        #   append-only (D-045; from S5, and S4)
  sprints/SPRINT_XX_REPORT.md                           # record
  sprints/SPRINT_XX_AUDIT.md                            # record, written by the auditor
  results/                                              # derived — generated, never edited
```

`DECISIONS.md` is a **record, not a contract**. It declares itself append-only — entries are
never renumbered and never deleted — so it can only grow, and a bounded budget would force
either deletion or a split that its own rules forbid. Search it by decision ID; do not read
it wholesale. Reclassified 2026-09-15, when it passed 12 KB.

## Roles

Three roles, distinguished by context and permissions, not by seniority.

- **Implementer** — the main session. Writes harness code, runs experiments, produces
  `runs/` and the sprint report.
- **`results-analyst`** (subagent) — reads `runs/`, does the statistics, produces tables and
  figures under `results/`. Isolated mainly for token economy. Does not modify retrieval
  code while analysing it.
- **`sprint-auditor`** (subagent, fresh context) — receives only the sprint report and the
  `runs/` directory, and verifies that every number is stamped and reproducible. Its value
  comes entirely from *not* having seen the implementer's reasoning, so it is never run in
  the session that produced the work. It cannot write to code or reports.

Commands: `/sprint-open <id>`, `/sprint-close <id>`, `/audit <id>`.

## Sprint model

Sprints are objects with identity, not positions in a list. IDs are **never reordered or
reused**, and gaps are normal. Two types:

- **Backbone** — the paper's claims depend on it. Changing one changes what the paper
  asserts, and requires updating `RESEARCH_PLAN.md`.
- **Probe** — exploratory, may be abandoned. **Must declare its stopping criterion in
  advance**: a time budget, or the result that would make it pointless. A probe without a
  declared stop is how three weeks disappear.

Registry and status: [`SPRINTS.md`](SPRINTS.md). Design precedes execution; the design
document is frozen when the sprint goes active, and changes afterwards are recorded as
dated amendments in `SPRINT_XX_AMENDMENTS.md` (D-045), never as in-place edits.
