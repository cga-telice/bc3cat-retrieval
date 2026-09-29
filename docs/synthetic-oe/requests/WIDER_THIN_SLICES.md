# Request to `bc3cat-dataset` — wider L2 slices (`paraphrase`, `expansion`, `compression`)

**Requested by:** `bc3cat-retrieval`, branch `research/synthetic-oe`, sprint S4 (work item 7)
**Drafted and issued:** 2026-09-29 · **Needed by:** S6 (statistical analysis). S4 does not wait for it.
**Plan of record:** `RESEARCH_PLAN.md` §5, cross-repo dependencies.

## Why

S4 measures each modification type's effect paired against the identity rendering of the same leaves,
with intervals that resample **concepts** (siblings are not independent draws). On the dev split the
three L2 (`text_variable`) types are thin in two ways, and the second is the binding one:

- **Queries:** `paraphrase` 108 and `expansion` 130 dev queries (211 / 206 over both splits).
- **Concepts:** all three L2 types on dev, `compression` included, reach only **5 concepts**
  (`results/S4/profile_item.md`, column `concepts`). A concept-clustered interval on five clusters is
  wide whatever n is, and the L2 layer's pooled effect is effectively a five-family estimate.

L1 and L3 types each reach 9 to 40 dev concepts.

## What is requested

Additional `single` queries of types `paraphrase`, `expansion` and `compression`, on the **same OE
corpus already delivered**, so every `gold_item_key` resolves against it:

1. **Breadth first.** As many distinct concepts as the rewrite menus admit, on both sides of our
   split (we send the concept lists; you need not read which side is which). A target of ≥ 15 dev
   concepts per type would make the concept-clustered interval informative.
2. **Depth second.** Up to about 20 leaves per concept and type.
3. **A new file** (e.g. `OE_single_l2_texto.json`), not a re-delivery of `OE_single_texto.json`: that
   file's digest stamps every run made on it.
4. The same record schema and the modifications sidecar, with the `reorder`-validator fix from
   `REORDER_LOOKUP_ARGUMENTS.md` in place, though it does not touch L2.

If the menus are the limit (L2 rewrites need concept-specific prose), please tell us how many concepts
are reachable, so S6 can state the limitation instead of waiting for data that cannot exist.
