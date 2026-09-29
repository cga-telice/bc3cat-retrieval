# Note to `bc3cat-dataset` — `reorder` permutes lookup arguments

**From:** `bc3cat-retrieval`, branch `research/synthetic-oe`, sprint S4
**Drafted and issued:** 2026-09-29 · **Recorded as:** `DATASET_DEFECTS.md` P7
**Asks for:** a fix for future deliveries and two checks on your side. **Not** a re-delivery of
`OE_single_texto.json`: a new file would change its digest and invalidate every run already made on it.

## What we found

`OEC140$`'s TEXTO template is `$T(%A,%B,%C)`, a lookup into a 2×2×2 table of whole sentences. An
approved `reorder` rule rewrote it to `$T(%C,%A,%B)`. For query `OEC140baa_syn_74d5dd2c9da3` (gold
`OEC140baa`, A=b, B=a, C=a) the renderer then evaluated `T[a][b][a]`, the cell of `OEC140aba`. The
query's text is that sibling's TEXTO verbatim ("Reparación de cámara de registro de hormigón…"), while
its `parameters` and `gold_item_key` are still the gold's. It is not a referent-preserving rendering.

Where it comes from, on `synthetic` (main checkout):
- `data/synthetic/processed_OE_ablation_single/BC3CAT_Syn_modifications.jsonl` logs the rewrite.
- `src/synthetic/variant_proposer.py:302`: `_PLACEHOLDER_RE = \$[A-Za-z0-9]+(?:\(%[A-Z]\))?` matches at
  most one argument, so `$T(%A,%B,%C)` reduces to `$T`, and `_require_placeholders_preserved` (`:315`)
  accepts every argument permutation.
- `data/synthetic/menus_OE/verdicts/reorder.jsonl` approves all three permutations of `$T`, and all
  three of the RESUMEN's `$U`, as `preserves_meaning: true`.

## Scope we measured — dev concepts only

We do not read test-split queries before our final evaluation, so we have not looked there.

| File | Affected dev queries |
|---|---|
| `OE_single_texto.json` | 1 of 2,206 (the one above; 1 of 306 `reorder`) |
| `OE_stacked_texto.json` | 0 of 2,521 |
| `OE_dose_texto.json` | 0 of 1,640 |
| `OE_isolated_texto.json` | 0 of 2,952 |

`OEC140$` is the only dev concept whose TEXTO uses a multi-argument lookup.

## What we ask

1. **Fix the validator** so the placeholder check compares whole calls with their argument order,
   e.g. `\$\w+\(%[A-Z](?:\s*,\s*%[A-Z])*\)`, and add a test on a multi-argument call. Withdraw the
   argument-permuting reorder rules (`$T`, `$U`).
2. **Check the test-split concepts on your side** with the same test (a query whose text equals a
   non-gold leaf's TEXTO), and tell us only **whether** any test query is affected and how many. We
   will handle it at scoring time, as for this one.
3. **Check whether any artefact was rendered from the approved `$U` permutations** (the RESUMEN side).
   We have not measured it.

## How we handle it here

The query is excluded from item-level scoring from S4 on and kept at parent level, where the text
still names the right concept (S4 design, amendment A2). No run is redone.
