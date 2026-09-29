# Note to `bc3cat-dataset` — `synonym_label` offered a case variant as a synonym

**From:** `bc3cat-retrieval`, branch `research/synthetic-oe`, sprint S4
**Drafted:** 2026-09-29 · **Issued:** when César sends it · **Recorded as:** `DATASET_DEFECTS.md` P8, D-044
**For information, plus one check on your side.** **Not** a re-delivery of `OE_single_texto.json`: a new
file would change its digest and invalidate every run already made on it.

## What we found

Four dev `single_texto` queries labelled `synonym_label` differ from their gold TEXTO in one token only,
and only in letter case: `semi-rocoso` → `Semi-Rocoso`.

| Query | Gold |
|---|---|
| `OED010bkabc_syn_85a4f552cd1b` | `OED010bkabc` |
| `OED030babca_syn_609ea3a72274` | `OED030babca` |
| `OED050bcbdc_syn_c59e212d9862` | `OED050bcbdc` |
| `OED080bhbda_syn_7575e67f784b` | `OED080bhbda` |

Our retrievers lower-case text before matching, so for most of them these queries are the original TEXTO.
They are labelled as modified but are not modified. It looks as if the synonym menu for that label
contains a case variant of the label itself.

## Scope we measured — dev only

4 of 291 dev `synonym_label` queries in `OE_single_texto.json`; no other type is affected. We do not read
test-split queries before our final evaluation.

## What we ask

1. **For future builds:** reject a synonym that equals the original label after lower-casing, and
   remove this one from the frozen menu.
2. **Check the test split on your side**, with the same test (a query equal to its gold TEXTO after
   lower-casing). Tell us only **whether** any test query is affected, how many, and their keys.

## How we handle it here

We keep the four queries (D-044). Every table that uses them also shows the result without them. At the
final test evaluation (S12) we will do the same with any test cases you report.
