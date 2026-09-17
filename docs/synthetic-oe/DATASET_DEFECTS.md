# DATASET_DEFECTS — BC3CAT-Syn/OE, as found by the retrieval side

**Class:** record — append-only. Entries are never renumbered or deleted; a resolved entry is
marked resolved in place with its date and the release that fixed it. Search it by ID.

Opened 2026-09-17, at the close of S2, because the defects had accumulated across `DECISIONS.md`,
two sprint reports and a cross-session thread, and no one place said what is wrong with the
corpus, who owns each item, and what may be done about it.

## The three classes, and why the distinction is the whole point

| Class | Who fixes it | Rule |
|---|---|---|
| **P — packaging defect** | upstream (`bc3cat-dataset`), by re-release | The corpus does not say what it means to say. Fix it, version it, record the digest. |
| **H — harness defect** | this repo, with a test | Our code mis-reads a corpus that is correct. Fix it here; never patch the data. |
| **C — property of the catalogue** | nobody | The thing the benchmark exists to measure. "Fixing" it destroys the phenomenon. |

**A preprocessing pass may act on P and H. It must not act on C.** Near-identical siblings,
discriminating literals buried in parameter values, comparators inside those values, and the fact
that a leaf's identity often lives in a number are not defects — they are the research object. A
preprocessing step that normalises them away, or that copies parameter values into the indexed
text, produces a corpus on which retrieval is easy and the finding is vacuous. The failure mode
has a precedent here: `bm25_unigram_params` reaches 0.9994 identity only because its tokens come
from the record's parsed `parameters` (D-010), which a real query does not carry.

---

## P1 — 776 leaves share a `texto` with a sibling · **open**

**Measured here.** 292 groups, 776 leaves, every group inside one concept: `OEA050$` 192 groups
of 3, `OEG050$` 100 of 2. All 776 fall in dev. OEB has **zero** such groups (0 of 47,513), which
is why the previous study never met this.
**Cause** (confirmed upstream 2026-09-17): the TEXTO templates of those two concepts never
reference one of the concept's parameter axes, so its values render identically. The RESUMEN does
separate them, so a deduplication keyed on the (resumen, texto) pair kept them.
**Consequence.** Expected item-level identity Acc@1 for a `texto`-only method caps at **0.9863**,
not 1.0. Parent level is unaffected, because no group spans two concepts. `bge_m3_colbert` sits on
that ceiling (484 of its 492 identity misses are these leaves).
**Disposition.** D-031: flag, do not collapse — a collapse changes the target pool and the corpus
digest, invalidating every run measured against it. Awaiting César.
**Evidence.** `results/S2/identity_misses.md`, generated. Same class reported upstream for
`OEG010$`.

## P2 — The stacked dose fields overstate what the TEXTO shows · **corrected upstream, not taken in**

**Reported upstream** 2026-09-17: ≈1,800 counted modifications are not visible in the TEXTO,
because the compatibility rule matched strings rather than text variables, so rewrites of
RESUMEN-only variables were counted when the same phrase reappeared through another variable.
**Consequence.** Texts are correct, so every Acc@1 stands; readings *by dose* do not. S2's stacked
by-dose strata are suspended in its report.
**Fix.** `texto_modification_count` / `texto_modification_types`, upstream branch
`syn/stacked-audit` `fd4713d`, not merged into `synthetic` at the time of writing and not taken in
here. S7 and S8 must read the corrected field.
**SINGLE is clean**: audited upstream, 4,439 of 4,439 with exactly one modification visible in the
TEXTO, so L1 slice membership — derived from `modification_count == 1` — stands as measured.

## P3 — `template_paraphrase` is counted twice in the stacked set · **open** (D-025)

The distinct dose is one lower than `modification_count` says. Any figure quoting a dose must name
the field it counted. Overlaps P2 and is expected to be resolved by the same corrected fields.

## P4 — `unit_conversion` also rewrites the maintenance band · **acknowledged upstream, labelling only**

In the tube families the type rewrites an interval (`i >= 5 horas` → `5 horas o más`), so the type
name is broader than the operation for those concepts. Upstream considers it a menu-labelling
matter, not a corpus defect. It matters for any per-type claim: the `unit_conversion` slice is not
purely unit conversion.

## P5 — Pantry artefacts: token doubling and one semantic drift · **kept deliberately** (D-004)

Token doubling ("tubos tubos", "mm mm") and `con topo` → `con topografía` were kept as documented
stress and are traceable per item through the modifications sidecar. D-004 requires a sensitivity
analysis excluding them **before any per-type claim**; S2 recorded 10 of 30 sampled `num_to_text`
misses as carrying doubling, and the exclusion analysis is deferred to S6. Until it runs, the
`num_to_text` figure is provisional.

## P6 — E3 dose set: structural limitations · **reported upstream, not independently verified here**

Delivered 2026-09-17 for S8. Concept coverage is 7 of 83 concepts, all OEB canalizations; two
pairs never co-occur by construction (`reorder`×`template_paraphrase`,
`unit_conversion`×`unit_expansion`), so those interactions are not identifiable;
`unit_conversion` is under-represented within the count-1 cell. S8's split can only partition
those seven concepts. Cited from upstream's `E3_DELIVERY_RESPONSE.md`; nothing here has checked it.

---

## H1 — `normalize_text` reads a synthetic decimal as a thousands group · **open** (D-010 note)

`\d\.\d{3}` is rewritten as a thousands separator, so `0.03x0.015 m` becomes `0.03x0015 m` in
`text_norm`, `text_word` and the param token. Dev reach: 9/204 `unit_conversion`, 4/244
`unit_expansion`, 38/2,521 stacked. Harness behaviour every method inherits; a miss in that set is
classified as a feature artefact, not a rendering effect. **Not the dataset's fault.**

## H2 — The word analyzer erases comparators · **not a defect; a method property** (S2 finding 1)

`(?u)\b\w+\b` drops `<`, `>`, `=`, so the three maintenance bands collapse to token sets that
contain one another and BM25 prefers the shorter sibling. This is why `bm25_unigram` identity is
0.8870. It belongs to the method, not the corpus: keeping the comparators is a **new config** in
S9, never an edit of the existing one, and never a rewrite of the data.

## H3 — Rank-1 ties are broken by candidate order · **measured** (S2 finding 8)

Worth ≤0.007 to the BM25 arms and ColBERT, and −0.05/−0.06 to the structured arms. D-028 (amended)
requires the tie-free reading for every family.

---

## C1 — Identity is a control, not a quality bar · **recorded 2026-09-17**

S2 gated on identity ≈0.98 for BM25 and ColBERT. Two things were conflated:

1. *Does the harness read its own target back?* — a control. It passed: the same code path returns
   0.9994 on the same query table.
2. *Can a method discriminate siblings from the indexed field alone?* — a **property of the
   method**, which is precisely what the study measures.

The previous study ran **no identity control at all**: its 0.974 is `resumen→texto` on the OEB
test split, not a read-back. No method is required to reach 1.0, and after P1 no `texto`-only
method can: the 0.98 threshold was set above the corpus ceiling of 0.9863 without anyone noticing.

**How it should read instead.** Each method's identity is reported as **its own ceiling**, beside
the corpus ceiling for the field it indexes, and every L1 or stacked figure is read against that
ceiling rather than against 1.0. A gate, if one is kept, tests the harness — one method, known to
carry enough information, reading its target back — not the whole method set. Proposed for the
sprint that follows S2; no gate is re-read retroactively.
