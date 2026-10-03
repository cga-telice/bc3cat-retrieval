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

> **`H` here means *harness*, not *hypothesis*.** This register's `H1…H5` are defects in our code;
> the proposal's `H1…H6` are the research hypotheses, and the two sets are unrelated — `H4` is a
> missing version stamp here and super-additivity there. The collision was harmless while the
> register stopped at `H3`; S3 added `H4` and `H5` and made it actively misleading. Renaming the
> classes would touch every reference in this file and in `DECISIONS.md`, so it is flagged rather
> than done: **cite a harness defect as "defect H4", never bare "H4".**

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

## P7 — `reorder` permuted the arguments of a lookup, so one query renders a sibling's TEXTO · **excluded at item level** (S4, 2026-09-29)

`OEC140$`'s TEXTO is not prose with substituted values but a lookup, `$T(%A,%B,%C)`, into a 2×2×2
table of whole sentences. An approved `reorder` rule rewrote it to `$T(%C,%A,%B)`, so the renderer read
another row: query `OEC140baa_syn_74d5dd2c9da3` (gold `OEC140baa`, "Recrecido de arqueta…") carries,
verbatim, the TEXTO of `OEC140aba` ("Reparación de cámara…"), while its `parameters` stay the gold's.
The query is not referent-preserving: a text-only arm that retrieves what the text says is scored
wrong, and only the oracle arm (D-010) can hit it.
- **Mechanism, upstream** (`bc3cat-dataset` `synthetic`): the modifications sidecar logs the rewrite;
  `src/synthetic/variant_proposer.py:302`'s placeholder regex reads a single argument, so
  `_require_placeholders_preserved` accepts any permutation; the reorder verdicts approved all three
  permutations of `$T` and of the RESUMEN's `$U` as meaning-preserving.
- **Scope, dev only** (test not read, operating rule 2): 1 of 2,206 `single_texto` queries (1 of 306
  `reorder`); 0 in `stacked_texto`, `OE_dose_texto`, `OE_isolated_texto`. `OEC140$` is the only dev
  concept with a multi-argument lookup. Found by S4 work item 4.
- **Handling:** excluded from item-level scoring from S4 on (design A2), n excluded printed; kept at
  parent level, since the text names the right concept. The file is **not** re-taken: a corrected one
  changes the `single_texto` digest and invalidates every run on it. Reported upstream in
  [`requests/REORDER_LOOKUP_ARGUMENTS.md`](requests/REORDER_LOOKUP_ARGUMENTS.md), which also asks for the
  test split and the `$U` permutations to be checked on their side.

**Upstream answer (2026-09-29, `DELIVERIES.md`, D-043).** The diagnosis was confirmed and the
validator fixed; 28 approved rules were withdrawn for future builds. The class is wider than the
permutation. On test, **2** `reorder` queries come from a rule that swaps a literal lookup row. They
match no leaf, so the equality test cannot see them, but they are not referent-preserving either.
They get the same treatment, applied in S12 from a key-only list, since test is not read before then.
Dev has no other case.

## P8 — `synonym_label` rewrote a label to itself in another case · **kept in, shown both ways; reported upstream** (S4 audit F8, 2026-09-29; D-044)

Four dev `synonym_label` queries differ from their gold TEXTO in one token only, `semi-rocoso` →
`Semi-Rocoso`: `OED010bkabc_syn_85a4f552cd1b`, `OED030babca_syn_609ea3a72274`,
`OED050bcbdc_syn_c59e212d9862`, `OED080bhbda_syn_7575e67f784b`. The synonym menu offered a case variant
as a synonym. For an arm that reads `normalize_text` output the query is the identity query, so it is
untreated and its δ is 0 by construction. That dilutes the treatment-on-the-treated reading of its cell.
- **Class.** Candidate P: the rewrite is upstream's. It becomes a non-treatment only through the
  harness's case folding. An arm reading raw case (the dense tokenizers) does see a change.
- **Scope, dev only.** 4 of 291 `synonym_label` queries; none in another type. Found by the S4
  auditor, not by work item 4, whose equality test compares raw text.
- **Handling.** Not excluded, because the design names no such rule and S4's figures had been read. T4
  lists the four and prints `synonym_label` item δ with and without them for every arm. The largest
  move is 0.0103 (`tfidf_phrases_replace`, −0.7308 → −0.7411). For `bm25_unigram` it is −0.6434 →
  −0.6525. No reading changes. Kept in from S4 on, with every
  `synonym_label` cell shown both ways (D-044). Reported upstream for information in
  [`requests/SYNONYM_CASE_ONLY.md`](requests/SYNONYM_CASE_ONLY.md); the file is not re-taken.
- **Upstream answer (2026-09-29, `DELIVERIES.md`).** The cause is four case-only candidates in the
  frozen menu (`semi-rocoso` ×2, `rocoso`, `elevada`), approved in review. The reach is 4 dev and
  **2 test** queries, all `single_texto`; every other file has none. The test keys are in
  `OE_P8_test_exclusion.json` (`6cda7fa0`), used in S12 for the "without" view. Future builds drop
  such candidates.

## P9 — `OE_concept_schema.json` names axes with stray spaces · **open; the registered extractor is defeated by it** (S9, 2026-10-03; D-056 accepted 2026-10-03: stripped in the harness from the next sprint that compares axis labels)

Axis labels in the delivered schema carry leading or trailing spaces in some concepts and not in others:
`' Nº TUBOS '`, `' TIPO DE TERRENO '`, `'TIPO '`, `' CONDICIONES DE EJECUCIÓN'`, `'MATERIAL '`, and more; the same
axis is spelled both ways across concepts (`'Nº TUBOS'` and `' Nº TUBOS '`).
- **Class.** Candidate P: the labels are upstream's. They are harmless to every arm that does not compare axis
  names, and to the rules extractor.
- **Effect.** The LLM extractor ported from `research/structured-retrieval` reads each axis from the model's JSON
  by its exact schema name; the model writes the name trimmed, so the value is dropped. On S9's runs, 15,046 of
  the 16,401 axes the registered arm loses are this case (`results/S9/extraction.md`, post hoc, A7–A8).
- **Handling.** The registered S9 result stands as published. Proposed (D-056): the harness strips axis labels
  wherever it compares them; reported upstream for information.

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

## H4 — `index/*/meta.json` does not stamp the ML stack that produced the embeddings · **open** (D-034)

**Found in S3 work item 5.** An index's `meta.json` records `software: {python, sklearn}` and nothing
else. For the four local dense arms the embeddings are produced by `torch`, `transformers` and
`sentence-transformers`, none of which is recorded anywhere in the artefact.
**Why it matters.** The branch's first operating rule says a number must be reproducible from
`{run_id, config SHA, code commit, query-set digest}`. For a neural arm that set is **incomplete**: the
same config and commit on two different `transformers` versions can produce different vectors, and
nothing in the index says which produced these. The blocker behind D-034 was invisible for exactly
this reason — it surfaced only when a model was actually loaded and failed, not from any stamp.
**Interim.** The versions are recorded in `logs/S3/build_indexes.sh`'s captured output (torch
2.2.2+cu121, transformers 4.57.6, sentence-transformers 3.4.1, sklearn 1.4.2). That is a log, not a
stamp: it lives in a git-ignored directory and is not attached to the artefact.
**Fix.** Have the builders record the versions of the libraries they actually imported. It touches
every builder's `write_index_payload` call, so it is not a mid-sprint change; it should land before
S12, since the frozen test evaluation is the one run that cannot be repeated.

## H5 — The dirty-tree check disagrees between host and container, so stamps read `code_dirty: true` on a clean tree · **worked around** (S3)

**Found in S3 work item 5**, after the first build pass stamped all seven OE indexes
`code_dirty: true` over `src/index_builders/README.md`, a file nobody had touched.
**Cause.** The repo sets `core.autocrlf=true` and `.gitattributes` pins `eol=lf` for `.py`, `.yaml`
and `.sh` — but says nothing about `.md`. That README therefore sits on disk as CRLF against an LF
blob: the host's git normalises it and reports a clean tree, while a container git with `autocrlf`
unset reports all 54 of its lines modified. `provenance_stamp` asks git inside the container, so it
got the false answer.
**Reach.** Wider than the stamp. The same phantom is why `logs/S3/rederive_stacked.sh` printed
`dirty=57` in work item 1, and why the S1 `resumen` run archived under design amendment A2 carries
`code_dirty: true` on `src/index_builders/README.md` and `src/utils/build_results.py`. **That
archiving was still correct** — an index or run stamped dirty cannot be cited either way — but the
cause was line endings, not an uncommitted change.
**Worked around.** `logs/S3/build_indexes.sh` sets `core.autocrlf=true` in the container so it agrees
with the host, and **refuses to build at all** when `src/` or `configs/` is dirty. Checked before
relying on it that the fix agrees rather than blinds: a real append to the same file still shows
as ` M`. All seven indexes then rebuilt clean at `2dd653d`.
**Not fixed, and why.** The permanent fix is `*.md text eol=lf` in `.gitattributes`, which only works
alongside `git add --renormalize` over every markdown file — rewriting the frozen S3 design and making
`git log -- SPRINT_S3_DESIGN.md` noisy, the opposite of what the freeze rule asks of it. Also note the
guard lives in a **git-ignored** directory, as S2's did: it protects this sprint's builds and would
vanish if `logs/` were cleaned. The durable place for it is `utils/provenance.py`, where it would
cover every run and index rather than the ones this script drives.

## H6 — Five retrievers scored every query in one block, so ten arms could not run at scale · **fixed** (S3)

**Found in S3 work items 6–7**: the first E0 pass lost **12 of 17 runs** to `DeadKernelError`.
**Cause.** Batching is each retriever's own business — `retrieve.ipynb` sets `BATCH_SIZE = None`,
meaning "the retriever's default" — and S1 blocked only the three methods S2 needed
(`bm25_unigram`, `dense_e5`, `bge_m3_colbert`). D-012 widened the set to ten, and the five new arms
had never been run at 35,422 queries. Four densify a B × N score matrix — 35,422 × 70,242 is
**9.3 GiB** in float32 against ~20 GiB of container RAM — and `bge_m3_dense` posted every query to
the embedding container in a single HTTP request, ~290 MB of float32 returning as JSON numbers.
**Fixed** in all five, following S1's pattern: `DEFAULT_BATCH_SIZE = 2048`, the old body renamed
`_search_block`, `search_batch` delegating to it. One scoring path per arm.
`tests/test_retriever_batching.py`, 55 tests — blocks equal one block across seven block sizes,
shapes hold, nonsense sizes refused, and **every arm's default is 2048 rather than `None`**, since an
arm defaulting to one block dies however careful the caller is.
**Generalisation worth keeping.** The harness only ever gets exercised at the scale some sprint
happens to need. Any arm D-012 did not already include should be assumed unbatched until run.

## H7 — `bge_m3_dense`'s builder wrote its FAISS index outside the collection layout · **fixed** (S3)

**Found in S3 work item 6**: both `bge_m3_dense` runs failed with
`could not open .../faiss.index`, *after* the build had reported `num_docs 70,242` and a clean stamp.
**Cause.** The builder derived `index_root/{save_as}/data` itself instead of
`index_root/{collection}/{save_as}/data`, so the OE index came out split across two directories —
the notebook's artefacts under `index/OE/bge_m3_dense__OE/data/` and `faiss.index` under
`index/bge_m3_dense__OE/data/`, where the retriever does not look. Path construction outside the
resolver is what D-022 forbade.
**`bge_m3_colbert` carried the identical bug and was fixed in S2**, when S2 ran ColBERT; its builder
still carries the comment describing the split. This arm was left behind because no sprint ran it.
The fix is that same line, copied rather than reinvented.
**Left behind:** the stray `index/bge_m3_dense__OE/` directory (275 MB). Agents hold no delete
permission over `index/` (D-019), so removing it is César's call.
**Same lesson as H6**, from the other end: a build can report success, a clean stamp and the right
document count while writing a required artefact somewhere nothing will read it. `num_docs` is not an
integrity check.

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
