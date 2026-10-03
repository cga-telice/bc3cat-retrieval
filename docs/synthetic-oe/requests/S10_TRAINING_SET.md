# Request to `bc3cat-dataset` — a training set for S10, disjoint from the evaluation rewrites

**Requested by:** `bc3cat-retrieval`, branch `research/synthetic-oe`, sprint S10 (Track D, learned representations)
**Drafted:** 2026-10-04 · **Issued:** 2026-10-04 (D-058) · **Needed by:** S10, which cannot train until it lands. Nothing else waits on it.
**Plan of record:** `RESEARCH_PLAN.md` §2 S10, §5 cross-repo dependencies.

## Why

S10 fine-tunes two retrieval encoders (`multilingual-e5-base` and BGE-M3 ColBERT) so they rank an item's
`texto` above its siblings when the query is a rewritten rendering. Training uses dev concepts only. Each
example is a query, its gold `texto`, and sibling `texto`s as hard negatives.

We cannot train on the delivered query sets. The rewrite menus are shared across concepts, so a concept-level
split does not separate them. Of the applied single-query rewrites on **test** concepts, these also occur on
**dev** concepts:

| Type | Test rewrites also in dev |
|---|---|
| `synonym_label` | 73 of 89 (original → new pairs) |
| `num_to_text` | 33 of 37 pairs |
| `compression` | 38 of 38 rewritten strings |
| `expansion` / `paraphrase` | 46 of 56 / 47 of 62 strings |
| `unit_expansion` / `unit_conversion` | 9 of 75 / 4 of 159 pairs |
| `reorder` / `template_paraphrase` | 3 of 70 / 0 of 166 |

A model trained on dev queries would memorise menu entries that reappear verbatim at test. The held-out score
would then partly measure recall of the generator, not robustness. The same holds inside dev, where we evaluate
by concept-level cross-fitting.

## What is requested

A **training** query set over the same OE corpus already delivered (digests in our `MANIFEST.md`), so every
`gold_item_key` resolves against it.

1. **Leaves: dev concepts only.** The 42 concepts listed under "dev" in our `SPLITS.md` (we send the list). No
   leaf of a test concept appears, as gold or otherwise.
2. **Menu entries disjoint from every delivered query.** No menu entry (rewrite pair, rewritten string, template)
   used in any query of `OE_single_texto`, `OE_stacked_texto`, `OE_single_l2_texto`, or the E3 `dose` /
   `isolated` sets, on either side of the split, is used in a training item. Entries upstream never delivered are
   admissible.
3. **If the disjoint menu is too thin for a type,** please tell us how many entries remain per type, and either:
   (a) author new entries for it under the same offline, human-audited procedure as the frozen menus, kept out of
   every evaluation set; or (b) deliver the type as it is and we report it as thin. `synonym_label` is the type we
   expect to be thinnest. Your call on (a) against its cost; we would rather know the number than wait.
4. **Composition.** All nine types (D-001 / D-002), as `single` (one modification) and `stacked` (2–5, mixed at
   random, `reorder` admitted, `template_paraphrase` not forced). This is the E3 rule, not the published stacked
   rule.
5. **Volume.** Breadth first: every dev concept a type can reach. Then depth: up to about 50 leaves per concept
   and type, several renderings per leaf where the menu allows. A total of about 20,000–50,000 items is useful.
   Fewer is fine if the disjoint menu is the limit.
6. **Format.** A new file, e.g. `OE_train_texto.json`, with the same record schema as `OE_single_texto.json`.
   Include a modifications sidecar that also carries a **stable menu-entry ID** per modification, so we can
   verify disjointness ourselves rather than trust it. Generation must be deterministic, with a commit and
   SHA-256 digests, as for the earlier deliveries. The D-004 artefact flags, the P7 / P8 fixes and the P9 axis
   names (`DATASET_DEFECTS.md`) apply as in the current engine.

## What we will do with it

Train on it mixed with the catalogue's decoded `resumen` of the same dev leaves (`OE_resumen_decoded.json`,
already in our tree). We will then verify, from the sidecar IDs, that no training entry occurs in any evaluation
query, and fail the intake if one does. The delivery and its digests go into `DELIVERIES.md` and `MANIFEST.md`
before any training run.
