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
has a precedent here: `bm25_unigram_params` reaches 0.9994 identity only because the *query*
carries the record's parsed `parameters` (D-010 and its second note, where this was checked
against the code: the scorer is unmodified, the field is what differs).

---

## P1 — 776 leaves share a `texto` with a sibling · **flagged and excluded at scoring** (S3, 2026-09-27)

**Measured here.** 292 groups, 776 leaves, every group inside one concept: `OEA050$` 192 groups
of 3, `OEG050$` 100 of 2. All 776 fall in dev. OEB has **zero** such groups (0 of 47,513), which
is why the previous study never met this.
**Cause** (confirmed upstream 2026-09-17): the TEXTO templates of those two concepts never
reference one of the concept's parameter axes, so its values render identically. The RESUMEN does
separate them, so a deduplication keyed on the (resumen, texto) pair kept them.
**Consequence.** Expected item-level identity Acc@1 for a `texto`-only method caps at **0.9863**,
not 1.0. Parent level is unaffected, because no group spans two concepts. `bge_m3_colbert` sits on
that ceiling (484 of its 492 identity misses are these leaves).
**Disposition.** **D-031 accepted 2026-09-17 (César): flag, do not collapse.** Upstream adds a
`duplicate_texto_group` field carrying a stable group id; the target pool, the texts and the
70,242-leaf figure stay as they are, so S2's runs remain valid. The harness can also derive the
grouping itself from the corpus, deterministically, which is what `identity_misses.md` does.
**Evidence.** `results/S2/identity_misses.md`, generated. Same class reported upstream for
`OEG010$`.
**Delivered 2026-09-27, not yet taken in.** `OE_duplicate_texto_groups.json`
(`b3cfcad47c71c5eb…`, 292 groups / 776 leaves, verified against the handoff) plus the
`duplicate_texto_group` field inside the corpus files. **D-033 (2026-09-27): take the sidecar
only and exclude those queries at scoring time**, leaving the corpus and S2's digests alone; S3
takes it.
**Taken in, S3 work item 1.** Sidecar in at `b3cfcad4…`; the corpus files with the field inside were
refused, so `643f1a72…` / `75477221…` still resolve. The sidecar was checked against the figures
D-031 was decided on rather than trusted — 292 groups, 776 leaves, 192 triples in `OEA050$` and 100
pairs in `OEG050$`, no group crossing a concept, every member in the corpus and every group genuinely
sharing one `texto` (`tests/test_intake_20260927.py`).
**Resolved at scoring, work item 3.** Item-level excludes duplicate-gold queries; `OEA050$` and
`OEG050$` contribute parent-level figures only, so item level rests on 40 of 42 dev concepts. **On
the scored population the ceiling is 1.0, so the 0.9863 cap is gone rather than worked around.** The
predicted consequence above is confirmed exactly: 484 of `bge_m3_colbert`'s 492 identity misses were
these leaves, and its identity Acc@1 goes 0.9861 → **0.9998** (n 35,422 → 34,646). Also measured:
`bm25_unigram_params` loses **nothing** to this defect — zero of its 21 misses had a duplicated gold,
because parameter tokens separate what the text cannot (D-010's oracle, quantified once more).
`results/S3/s2_rescored/`, and the two-populations rule in the D-033 note: no item-level figure is
quoted without its n.

## P2 — The stacked dose fields overstate what the TEXTO shows · **corrected and taken in** (S3, 2026-09-27)

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
**Delivered 2026-09-27, not yet taken in.** `syn/stacked-audit` is merged; `OE_stacked_texto.json`
(`c34a222ae2af05a0…`, verified) carries `texto_modification_count` / `texto_modification_types`,
with the same ids and texts as ours (checked row for row). Visible-count distribution 1→5, 2→1,252,
3→1,465, 4→1,799, 5→401, 6→76. Taking it changes that query set's digest, so D-033 keeps the
current file under a versioned name. `template_paraphrase` is still visible in all 4,998 and
`reorder` in none, so P3's dose/composition confound survives — E3 exists for that.
**Taken in, S3 work item 1, and acted on in work item 4.** The corrected file is in at `c34a222a…`,
the feature tables re-derived, and `QUERY_FIELDS` widened so the field actually reaches them —
without that the correction would have stopped at the JSON and been silently ignored (design
amendment A1). The re-derivation moved only the two stacked tables, and inside the new feature table
all 26 pre-existing columns are identical row for row, so **no Acc@1 moved**, exactly as upstream
said.
**What did move is the attribution.** `results/S3/s2_rescored/stacked_by_dose.md` re-stratifies on
`texto_modification_count` and prints the crosstab against the field S2 used: of the 730 dev queries
S2 called dose 5, only **193** show five modifications in the TEXTO — 456 show four, 80 three, 1 two.
S2's suspended by-dose strata are therefore not merely uncertain, they were misattributed, and the
corrected table replaces them. Dev spans visible dose 2–6; the five dose-1 records are all on test.

## P3 — `template_paraphrase` is counted twice in the stacked set · **resolved by the corrected field** (S3, 2026-09-27)

The distinct dose is one lower than `modification_count` says. Any figure quoting a dose must name
the field it counted. Overlaps P2 and is expected to be resolved by the same corrected fields.
**Resolved as expected, and verified.** `texto_modification_types` is delivered de-duplicated:
`texto_modification_count == len(set(texto_modification_types))` for all 4,998 records, and the same
holds for both E3 sets (`tests/test_intake_20260927.py`, `tests/test_intake_e3.py`). So the corrected
field is both *visible* and *distinct*, and `distinct_modification_count` — the workaround D-025
introduced — is retired: S3 work item 4 stratifies on the delivered field, and nothing downstream
counts doses itself. The rule stands and is now cheap to obey: any figure quoting a dose names the
field, and for the stacked set that field is `texto_modification_count`.

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

## P6 — E3 dose set: structural limitations · **verified here** (S3, 2026-09-27)

Delivered 2026-09-17 for S8. Concept coverage is 7 of 83 concepts, all OEB canalizations; two
pairs never co-occur by construction (`reorder`×`template_paraphrase`,
`unit_conversion`×`unit_expansion`), so those interactions are not identifiable;
`unit_conversion` is under-represented within the count-1 cell. S8's split can only partition
those seven concepts.
**Verified here, S3 work item 2** (`tests/test_intake_e3.py`, 23 tests): every claim re-derived from
the files rather than cited, and all held — the per-concept leaf counts 61/87/96/93/87/87/89, the two
zero-co-occurrence pairs, `unit_conversion` at 39 items in the count-1 cell against ≥70 for the other
eight, all 8,400 gold keys resolving, `available_types` ⊆ `applicable_types` everywhere.
**And what upstream delivered beyond the request:** all 600 leaves carry the **complete ladder 1–5**,
**nested** — the types at count *k* are those at *k*−1 plus exactly one — so H4 is a within-item slope
with paired rung-to-rung contrasts rather than a between-item regression. The isolated set covers the
same 600 leaves, so the "sum of isolated effects" sums over the ladder's own population.
**The limitation that binds S8** is the coverage, not the composition: the seven concepts split 4 dev
/ 3 test, so a dev slope rests on 328 leaves but a **concept-clustered interval on it resamples four
clusters** — and D-030 reads thresholds against exactly that interval. S8 must report both intervals
and say which it reads. The tests pin the two zero-co-occurrence pairs deliberately, so a later
delivery that changes the identifiability fails loudly instead of being inherited in silence.
**No cost from P1 here:** no ladder leaf is in a duplicate group, E3 being OEB-only.

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

**How it reads instead**, ruled by César on 2026-09-17 (**D-032**, Accepted): each method's
identity is reported as **its own ceiling**, beside the corpus ceiling for the field it indexes,
and every L1 or stacked figure is read against that ceiling rather than against 1.0. Identity is
no longer a gate over the method set. Whether a narrow harness control remains — one method,
known to carry enough information, reading its target back — is part of the S14 design
discussion. No gate is re-read retroactively: S2's G1 stays *ambiguous* as recorded.
