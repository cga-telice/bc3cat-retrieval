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

## Amendment 2026-10-18 — render with the repaired menus; stay disjoint from the BT lists too

The 2026-10-16 delivery repaired 163 approved `template_paraphrase` entries that put a value in a slot that is
not its own, or presented it as a reference document (our `DATASET_DEFECTS.md` P10), and shipped v2 of the four
evaluation sets. D-061 (proposed) makes v2 the reference for S12 and for the re-run amendments. The request above
is amended so that training and evaluation do not straddle the repair:

7. **Render the training set with the repaired menus** — the `template_paraphrase` menu as repaired for v2
   (`data/synthetic/broken_OE/OE_template_paraphrase_repairs.json`, 163 entries), never a v1 broken entry. A model
   trained on a broken paraphrase would learn a value in the wrong slot and be evaluated on the repaired one; a
   model trained on the repaired one and evaluated on v1 would be penalised for the defect. Condition 2
   (disjointness) is unchanged and now reads over the **v2** files as well as v1: no menu entry used in any query
   of `OE_single_texto{,_v2}`, `OE_stacked_texto{,_v2}`, `OE_single_l2_texto`, `OE_dose_texto{,_v2}` or
   `OE_isolated_texto{,_v2}` is used in a training item. Since v2 changed only `text` and only through the
   repaired paraphrases, the entries in use are the v1 entries plus the 163 repaired ones.
8. **Stay disjoint from the back-translation lists.** `bt_texto` (delivered 2026-10-16) replaces values by
   entries of `data/synthetic/bt_OE/OE_bt_value_approved.json` and trade terms by entries of
   `data/synthetic/bt_OE/OE_glossary_approved.json`. Those entries are evaluation material now (S14 on dev, S12
   on test): no training item uses an entry of either list, and the sidecar's menu-entry IDs cover them so we can
   verify it. If that empties a type, tell us the count, as in condition 3.
9. **No BT in training.** Back-translation of training leaves is not requested; if upstream wants to offer it, it
   must use chains and models disjoint from `bt_texto`'s (`OE_bt_provenance.json`) and be delivered as a separate
   file, so that it can be declined without touching the rest.

Everything else stands. The intake will verify 7–9 from the sidecar before any training run, as it verifies 2.

