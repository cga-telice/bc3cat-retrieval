# Sprint S0 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-09-15 · report `ea2a1718…` (commit `44a48ac`) · repo HEAD `a391ee9` · runs: none — `runs/` and `index/` hold 0 files (verified)

S0 produced no retrieval numbers, so the usual failure modes (mixed samples, stale prose numbers, overclaimed deltas) have little surface. Every descriptive number in the report reproduces exactly from the digested input files. The findings below are provenance and wording defects, not numeric ones.

## Verified

Re-derived independently from `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\data\processed\` (not by re-running the report's generators against their own output):

- **Five OE SHA-256** recomputed in place: `02a2c270…`, `0cd380e9…`, `b6a43961…`, `1bde2115…`, `2d3273ddb…` — match `MANIFEST.md` in full and `INTAKE.md §2` in prefix. 5/5.
- **Counts** 70 242 corpus records / 83 concepts / 4 439 single / 4 998 stacked — recounted from the files; `item_key` unique (70 242/70 242), zero template rows, schema 83 concepts.
- **Gold integrity** single 2 917 gold leaves, 0 absent, 0 parent mismatch; stacked 4 998, 0, 0 — matches `MANIFEST.md` §Integrity checks.
- **Split** 42/41 concepts, 35 422/34 820 leaves (50.4 % dev), 2 206/2 233 single, 2 521/2 477 stacked — recomputed from the committed concept lists in `docs/synthetic-oe/SPLITS.md` against the digested corpus. Partition exact: union = all 83, intersection empty. Per-subchapter and per-type tables reproduce to the unit, including `unit_conversion` 204/345 and `expansion` 130/76.
- **One sample, one claim:** every number in the split and balance tables derives from the same three digested files (`OE_texto`, `OE_single_texto`, `OE_stacked_texto`) and the same concept partition. No mixing.
- **Determinism of the split:** regenerating `build_splits.py` (seed 20260915, into scratchpad, nothing written in-repo) yields a file identical to the committed `SPLITS.md` apart from the generation stamp line. See F2.
- **Configs:** 76 present; 0 lack a `retriever` block; all 76 declared modules import as the notebook does and expose `load()`; `migrate_configs.py --target OE` (check mode) reports 0 defects and resolved inputs byte-identical before/after for all 76. `6d7af8e` touched exactly 62 configs, `35e3606` exactly 72 — matching the report's "62 re-pathed / 72 declarations".
- **Dead-path disclosure is accurate,** including against itself: `src/retrieve.ipynb` (`dynamic_load_retriever`) selects the module from `method_name.split("__", 1)[0]` plus an in-notebook alias table; the newly declared `retriever.module` is never read. The report states this ("Declaring is not obeying") rather than crediting the block. 6 configs carry no `method.impl` — matches the report's "six".
- **Design freeze clean.** `git diff f618571..HEAD -- …/SPRINT_S0_DESIGN.md` = filling the freeze stamp (`de402db`) plus two dated Amendments rows (`15f53ec`, `d745472`). Goal, work items, constraints and exit criteria are untouched in place. Both deviations claimed in the report correspond to those rows.
- **Exit criterion 4:** `configs/dense_colbert128.yaml` and `src/retrievers/tfidf_unigram_phrases.py` absent at HEAD; the surviving `_add`/`_replace` files are two-line shims over `.tfidf_unigram`, as claimed.
- **Split discipline:** no run exists; the split is a function of family sizes and a seed only, fixed before any run, with test concepts enumerated. D-021 and report finding 6 declare cross-side per-type comparison invalid and restrict analysis to within-side paired deltas — the applicability confound is honoured, not merely mentioned.
- **Overclaiming:** H1–H6 explicitly not addressed; no directional retrieval claim is made. Thin slices `paraphrase` 211 and `expansion` 206 are carried with an instruction not to over-read. One wording exception: F6.

## Findings

### F1 — major — Exit criterion 5 is reported "met" but no config is parameterised on `collection: "OE"`
The report: "A config on `collection: "OE"` resolves its inputs to the OE files — yes; `migrate_configs.py --target OE` reports the resolved paths", caveated only on the harness side. The artefacts: all 76 configs still declare `collection: "OEB"` (parsed, 76/76). The OE resolution comes from the script's `--target` flag, which overrides the field — `resolve(cfg, collection=args.target)` in `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\src\utils\migrate_configs.py:39-50` ignores `cfg["collection"]` when a target is passed. What was proven is that the *input templates* resolve to OE files when OE is supplied, which is weaker than the criterion as worded, and weaker in a different way than the caveat admits. Either add one config carrying `collection: "OE"` and re-run the dry run, or amend the criterion and mark it partially discharged.

### F2 — minor — the "byte-identical regeneration" claim cannot be literally true
The report: "`SPLITS.md` was regenerated after committing and produced a byte-identical file (`8d520eb46fa2a2c5`), which is the only evidence that 'seeded' means anything." The artefacts: `SPLITS.md` embeds `git rev-parse --short HEAD` at generation time (`build_splits.py:48-50, 150`) and stamps `af843a6`, while the commit that contains it is `d745472`. A regeneration performed after that commit would stamp `d745472` and could not be byte-identical. My regeneration at HEAD gives `100c0081…` and differs from the committed file in the stamp line only. The determinism claim is true; the wording that evidences it is not. Restate as "identical apart from the generation stamp", or make the stamp an argument.

### F3 — minor — each derived artefact is stamped with two different commits and the report says which is which nowhere
Report artefact table: `MANIFEST.md` → `2662e72`, `SPLITS.md` → `d745472` (the containing commits). The artefacts' own headers: `MANIFEST.md` → code commit `15f53ec`, `SPLITS.md` → `af843a6` (HEAD at generation). Both conventions are defensible; carrying both unlabelled in a sprint whose subject is provenance is not. Fix the column header or the generator.

### F4 — minor — the E3 request document contradicts D-009 and the report
`docs/synthetic-oe/requests/E3_BALANCED_DOSE.md:4` still reads `**Issued:** *(pending — see D-009)*`. D-009, `STATE.md` and report exit criterion 6 all say issued 2026-09-15 (`95b58d3`, which edited `DECISIONS.md` and `STATE.md` only). The criterion as designed — recorded in `DECISIONS.md` with its date — is met; the spec is stale.

### F5 — minor — report finding 9 is already overtaken at HEAD
The report: the mangled `references (11).bib` / `graphical_abstract (1).png` are "left untouched; renaming is the author's call", and "the paper does not compile from this directory as it stands". Commit `a391ee9`, after the report, renamed both. `graphical_abstract (1).pdf` remains mangled. A sprint report is a record, so this is not an error at its commit, but anyone reading it at HEAD is misinformed.

### F6 — minor — "even within a few percent" understates two type imbalances
Report: "Per-type balance is even within a few percent except for the two applicability-limited types"; the design's Amendments row says "near-even on every modification type except the two applicability-limited ones". Computed: `compression` 306/242 = 55.8/44.2, `unit_expansion` 244/298 = 45.0/55.0. Only four of nine types sit within ~2 points of even. These are exactly the slices later sprints will report per type, so the phrasing should carry the numbers rather than a summary adjective.

## Unverifiable

- **"The Zenodo reproducibility release contains no runs. Verified by downloading it."** — no download log, manifest or checksum exists in the repository; the only trace is the report's own prose.
- **The E3 request was actually sent to `bc3cat-dataset` on 2026-09-15** — attested by prose in D-009 and by the commit message of `95b58d3` ("Date as reported by Cesar"). No cross-repo artefact; this is a human attestation, not evidence.
- **OEB provenance before 2026-09-15** — the report says so itself; the seven `OEB_*` digests are forward-checkable only.
- **That the two migration scripts "reported zero defects" at the time they ran** — I verified the end state (76/76 declare, import, expose `load`; 0 defects in check mode today), not the historical run. No script log is committed.
- **Finding 4's "30 non-empty decile cells, 10 singletons; 17 tercile cells, 3 singletons"** — the decile variant is not reachable from the committed code (`build_splits.py` implements terciles only), so the discarded alternative cannot be re-derived from the artefacts.

## Exit criteria

| Criterion | Met | Evidence |
|---|---|---|
| 1 · Manifest committed, digests match, counts agree | yes | 5/5 SHA-256 recomputed against `MANIFEST.md` and `INTAKE.md §2`; 70 242 / 83 / 4 439 / 4 998 recounted from the files |
| 2 · Splits committed, 83 concepts once each, checked not eyeballed | yes | `SPLITS.md` partition recomputed: union = 83, intersection = 0; `build_splits.py:120-121` asserts before writing; regeneration reproduces the lists |
| 3 · Every config resolves to an existing module and declares its retriever | yes | 76/76 declare a `retriever` block; 76/76 import and expose `load()` under the notebook's own import path |
| 4 · `dense_colbert128` runnable or deleted; D-017 closed | yes | both files absent at HEAD; deleted in `15f53ec`; D-017 `Accepted (remove)` |
| 5 · A config on `collection: "OE"` resolves its inputs to the OE files | **not met as worded** | all 76 configs declare `collection: "OEB"`; OE came from `--target OE`, which overrides the field (F1) |
| 6 · E3 request recorded with its issue date | yes | D-009 "Issued 2026-09-15", commit `95b58d3`; the spec document still says pending (F4) |
| 7 · `runs/` still empty | yes | 0 files under `runs/` (and 0 under `index/`) |

No `FAIL` trigger: every reported number reproduced from the digested inputs, no comparison mixes samples, and every post-freeze design change carries a dated amendment. F1 should be closed — by a config or by an amendment — before S0 is marked `done`; F2–F6 are recordable as-is.
