# DECISIONS — `research/synthetic-oe`

Append-only decision log. One entry per decision, numbered, never renumbered, never
deleted. Superseding a decision means adding a new entry and marking the old one
`Superseded by D-0XX` — not editing it.

Sprint designs and reports **reference** decision IDs instead of restating them. If you
find yourself re-explaining why something is the way it is, that is a missing entry.

Statuses: `Accepted` · `Proposed` (agreed in principle, not yet executed) · `Open` (not
decided) · `Superseded`.

---

### D-001 — Exclude `omission` and `new_param` from the benchmark
**Status:** Accepted · **Date:** 2026-08-31 · **Owner:** César
**Context.** The BC3CAT-Syn taxonomy has twelve modification types. Two do not preserve
informational content: `omission` removes signal, `new_param` invents it.
**Decision.** Exclude both. The benchmark is defined as *"the same item said differently"*.
Nine types remain.
**Consequence.** Every query is a referent-preserving alternative rendering, so the gold
item never moves and paired evaluation against the original leaf is always valid. Queries
that alter the referent are out of scope for this paper.

### D-002 — Ten generation conditions: nine `single_<type>` plus one `all_combined`
**Status:** Accepted · **Date:** 2026-08-31 · **Owner:** César
**Context.** The protocol originally defined intermediate `stacked_2…5+` conditions.
**Decision.** Drop them. Keep nine isolation conditions and one maximal condition.
**Consequence.** Clean per-type ablation and a headline number, but **no balanced dose
axis** — compositionality (H4) cannot be identified from this release. See D-009.

### D-003 — Cap of ≤20 uses per unique rewrite on thin types
**Status:** Accepted · **Date:** 2026-08-31 · **Owner:** César
**Context.** `unit_conversion`, `unit_expansion` and `num_to_text` have few approved
rewrites; hitting the target n would mean reusing a handful of rewrites heavily.
**Decision.** Cap reuse, accept the shortfall, and publish unique-rewrite counts alongside
every n.
**Consequence.** Statistical precision never exceeds real linguistic diversity. Thin slices
carry wider intervals and are reported as such.

### D-004 — Keep documented pantry artefacts as stress
**Status:** Accepted · **Date:** 2026-09-02 · **Owner:** César
**Context.** Generation produced token doubling ("tubos tubos", "mm mm") and one semantic
drift ("con topo" → "con topografía").
**Decision.** Keep them, documented and traceable per item through the modifications
sidecar, rather than regenerate.
**Consequence.** Sensitivity analyses excluding affected items are required before any
per-type claim.

### D-005 — De-duplication policy: drop cross-concept twins, remap intra-concept collapses
**Status:** Accepted · **Date:** 2026-09-08 · **Owner:** César
**Context.** Identical `(resumen, texto)` pairs appeared across concepts (OED170$/OED020$)
and within one concept (OEG010$).
**Decision.** Cross-concept twins: drop the twin's leaves and derived queries, so the
survivor is not over-represented. Intra-concept: keep one leaf, remap derived queries.
**Consequence.** Corpus 73,302 → 70,242 leaves. Every `(resumen, texto)` is unique, which
is what makes the identity control a meaningful ceiling rather than a tie-breaking lottery.

### D-006 — Reposition the work as a robustness study for AiC
**Status:** Accepted · **Date:** 2026-09-14 · **Owner:** César
**Context.** The AiC submission was rejected on alignment and novelty. Reviewers correctly
identified that queries and targets came from the same catalogue record (94.1 % lexical /
99.93 % numeric containment), so the reported ranking does not model professional search.
**Decision.** Do not resubmit a corrected version of the same study. Add the missing link:
measure retrieval under controlled rendering variation, and make *when BM25 stops winning*
the result.
**Consequence.** Defines this branch. See `RESEARCH_PROPOSAL.md`.

### D-007 — Dev/test split partitions by concept, not by leaf
**Status:** Proposed · **Date:** 2026-09-14 · **Executed in:** S0
**Context.** Siblings of a test leaf share nearly all of its text. A leaf-level split leaks
by construction into any tuning or fine-tuning.
**Decision.** Partition the 83 concepts, stratified by subchapter and family size, seeded
and committed as an explicit concept-key list before any run.
**Consequence.** Track D fine-tuning and the BM25 re-sweep are defensible. Costs some
statistical power in the small subchapters.

### D-008 — Run and index layout keyed by collection and query set
**Status:** Proposed · **Date:** 2026-09-14 · **Executed in:** S0/S1
**Context.** All 77 configs hard-code `collection: "OEB"` and write to flat paths; one
corpus here has four query sets.
**Decision.** `index/{collection}/{method}` and `runs/{collection}/{queryset}/{method}`.
**Consequence.** Touches every notebook that scans `/work/runs`. Also isolates parallel
agents working in separate worktrees.

### D-009 — Compositionality requires a balanced dose set from upstream
**Status:** Proposed · **Date:** 2026-09-14 · **Executed in:** S8
**Context.** Consequence of D-002: the stacked set has no `reorder` and has
`template_paraphrase` in 100 % of items, so it cannot identify interactions.
**Decision.** Request a balanced compositional set (counts 1–5, randomised type mixes,
`reorder` admitted) from `bc3cat-dataset` at the start of the project, given its lead time.
**Fallback.** If it does not arrive, H4 drops to an exploratory regression on the existing
stacked set, with the confounding stated in the limitations.

### D-010 — Parameter availability reported as a pair of bounds
**Status:** Proposed · **Date:** 2026-09-14
**Context.** Synthetic query records carry a parsed `parameters` dict. A real query does not.
**Decision.** Methods consuming it are reported as **oracle upper bounds**; their text-only
counterparts are the deployable condition. Both always reported together.
**Consequence.** Prevents an oracle result from being read as a deployable one.

### D-011 — Two documents per sprint: design, then report
**Status:** Accepted · **Date:** 2026-09-14 · **Owner:** César
**Context.** A single file with two sections was considered. It reads better, but it loses
the cheap immutability guarantee of a separate design file.
**Decision.** Keep them separate. The design document is frozen when the sprint goes active;
`git log -- SPRINT_XX_DESIGN.md` after that date is a one-command check against
hypothesising after results are known.
**Consequence.** Design changes mid-sprint are recorded as dated amendments appended to the
design document, never as in-place edits. The auditor checks this.

### D-012 — Method scope on OE
**Status:** Open
Canonical set from the previous paper, with or without a full BM25 `k1`/`b` grid re-sweep
at the new query length (~74–78 tokens vs ~14). Gates S3.

### D-013 — Branch hygiene: does `research/synthetic-oe` ever merge to `main`?
**Status:** Open
Like `research/structured-retrieval`, this is a parallel branch. Undecided.

### D-014 — Real-query anchor
**Status:** Open
Whether 200–500 Telice estimator queries can be obtained within the timeline. It is the
strongest available answer to the practical-impact objection, and it depends on people
rather than compute.

### D-015 — Scope of Track D
**Status:** Open
How far reinforcement-learning-style optimisation is pursued relative to contrastive
fine-tuning with sibling hard negatives. Gated by G2 (after S5).

### D-016 — Config↔module integrity is a precondition for the OE run set
**Status:** Proposed · **Date:** 2026-09-14 · **Executed in:** S1
**Context.** An inventory of the 77 configs against `src/` (2026-09-14) found three gaps:
`dense_colbert128` names index-builder and retriever modules that do not exist;
`tfidf_char_3_5` and `tfidf_unigram_nostop` declare no `retriever` block, so their behaviour
comes from a notebook default rather than from the config; and
`src/retrievers/tfidf_unigram_phrases.py` is referenced by no config.
**Decision.** Before any OE run, every config in the active method set must resolve to
existing modules and declare its retriever explicitly — restating a default is fine, relying
on one is not. Unreferenced modules are confirmed and removed, or documented as reachable
by some other path.
**Consequence.** Enforces the reproducibility contract: a run is reproducible from
`(config, code commit, query-set digest)` and nothing else. Without this, a config is a
partial description of an experiment.

### D-017 — `dense_colbert128`: implement or remove
**Status:** Open · **Raised:** 2026-09-14 · **Decide by:** S1
The config is unrunnable and appears nowhere in `docs/reviews/paper_28.tex`, so no published
number depends on it. Two options: implement the modules and admit it to the method set, or
delete the config. Leaving it in place is not one — an unrunnable config in `configs/` reads
as an evaluated method to anyone auditing the repo later.

### D-018 — Work happens in the main checkout; parallel worktrees need explicit data access
**Status:** Proposed · **Date:** 2026-09-14 · **Executed in:** S0
**Context.** The branch is checked out in the main checkout, which is what `docker-compose`
mounts as `/work`. A worktree created without NTFS junctions to `data/`, `index/`, `runs/`,
`logs/` and `hf-cache/` cannot reach the corpus, and a session opened there sees neither the
data nor uncommitted scaffolding.
**Decision.** Single-agent work happens in the main checkout. A worktree used for parallel
sprint work must have the junctions created explicitly at creation time, and is recorded in
`STATE.md` while it is live.
**Consequence.** Sharpens the parallelism question that S9–S11 raise: with junctions, several
agents write into one `runs/` tree, so the `runs/{collection}/{queryset}/{method}` layout
(D-008) is what keeps them from colliding. If that isolation proves insufficient, the
alternative is a per-worktree `runs/` consolidated at sprint close — decide before S9, not
during it.
