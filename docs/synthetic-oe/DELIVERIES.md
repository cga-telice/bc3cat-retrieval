# DELIVERIES — `research/synthetic-oe`

**Record.** Append-only, unbounded, searched rather than read wholesale. One section per upstream
delivery: what arrived, when, its digests, what was verified about it, and which limitations it
carries into which sprint.

Split out of [`INTAKE.md`](INTAKE.md) on 2026-09-27, when that contract passed its 12 KB budget.
The reason is the documentation model, not housekeeping: `INTAKE.md` is a **contract** — where the
data goes, what its schema is, what breaks on it — and a contract that accumulates one section per
delivery is an archive wearing a contract's name, and stops being read. Delivery history changes
every time upstream ships, so it is a record. The original intake of 2026-09-08 stays in
`INTAKE.md §2` as the branch's founding provenance; everything after it lives here.

Newest first.

---

## 2026-09-29 (later) — the P7 test exclusion list · **taken**; the L2 reach corrected

| File | Records | SHA-256 prefix | Taken |
|---|---:|---|---|
| `OE_P7_test_exclusion.json` | 2 keys | `96fe3854f2b6d935` | yes, D-043 ruling 1 |

It holds keys only: `reason`, `file` (`OE_single_texto.json`), `split` (`test`) and `item_keys`. The
file was checked without reading any query text. Both keys resolve in `OE_single_texto.json`, which
is unchanged (`b6a43961…`), and both belong to test concepts under `SPLITS.md`. It is applied at item
level in S12 and nowhere before.

**The wider-L2 reach was wrong.** Upstream built `OE_single_l2_texto.json` from the frozen menus and
found it adds **no concepts**: 478 queries on the same 5 dev / 3 test concepts per type. The
reachability check tested visibility in the TEXTO, not whether the render engine can apply the
rewrite. 17 of the 25 concepts with a text variable store it as an axis-indexed list (`$T(%A)`), which
the engine cannot yet rewrite. The file is **not taken**; the choice upstream offered is pending with
César.

## 2026-09-29 — answers to the P7 and wider-L2 requests · **no files**

Upstream answered both S4 requests in `bc3cat-dataset/docs/synthetic/REORDER_LOOKUP_RESPONSE.md` and
`WIDER_THIN_SLICES_RESPONSE.md`, on `synthetic` over `f2457fa`. **No file was delivered**:
`OE_single_texto.json` still hashes `b6a43961…`, re-checked here, so no S4 run moves.

- **P7.** Upstream confirmed the diagnosis and fixed the placeholder validator: whole calls,
  arguments in order, literal rows included. The pantry loader now re-checks approved rules and
  drops 28: 9 `reorder`, 16 `template_paraphrase`, 3 `omission`. **The fix was uncommitted when
  answered** ("pending owner review"). Scope:
  - **Dev:** our own test finds only the one query. No other dev query in any delivered set was
    built from a withdrawn rule.
  - **Test** (counts only, from upstream): 0 by our test. **2** `single_texto` `reorder` queries come
    from a different withdrawn rule, which swaps a literal lookup row and drops a field. They match
    no leaf, so our test cannot see them, but they are not referent-preserving.
  - The `$U` permutations reached no delivered file.
- **Wider L2.** Not built yet. Reachable with the frozen menus: `paraphrase` 9, `expansion` 9,
  `compression` 8 dev concepts (today 5), at about 180 / 180 / 160 dev queries with ≤ 20 leaves per
  concept. **Hard ceiling: 13 dev / 12 test concepts.** Only those concepts render a text variable in
  their TEXTO, so no menu can reach ≥ 15.

César's rulings are recorded in D-043.

## 2026-09-27 — duplicate-`texto` sidecar and the corrected stacked set

**Taken in:** S3 work item 1 · **Decisions:** D-031, D-033, D-025

Producer: `bc3cat-dataset`, branch `synthetic` @ `f2457fa`; the files themselves were
repackaged at `903d07b8` from the generation run `e3-20260917T093057Z` (seed 42, generated at
`e057907`). Verified by re-hashing `D:/…/bc3cat-dataset/data/synthetic/handoff_OE/` against that
repository's own `MANIFEST.md`, not by trusting either.

| File | SHA-256 prefix | Taken |
|---|---|---|
| `OE_duplicate_texto_groups.json` | `b3cfcad47c71c5eb` | yes — the D-031 flag as a sidecar |
| `OE_stacked_texto.json` | `c34a222ae2af05a0` | yes — adds `texto_modification_{count,types}` |
| `OE_texto.json` / `OE_resumen.json` with `duplicate_texto_group` inside | — | **no**, deliberately |

**Why the corpus files were refused.** They carry the same grouping as the sidecar, but embedding
it changes their digest although no text changes — and every S2 run is stamped against
`OE_long_feats.parquet` `643f1a72…` / `OE_long_norm.parquet` `75477221…` derived from them. The
sidecar delivers the same information at no provenance cost (D-033).

**The superseded stacked query set is kept, and so are its derived tables.** S2's three stacked
runs are stamped against the *feature table* `7b0894e6…`, not the JSON, so versioning the JSON
alone would have left them dangling. All three survive under digest-stamped names:
`OE_stacked_texto__1bde2115.json`, `OE_stacked_texto_norm__81cd501b.parquet`,
`OE_stacked_texto_feats__7b0894e6.parquet`. They are not a query set — `run_context` resolves
query sets by exact canonical name — so nothing can be run on them; they exist so that a stamp
still resolves. `src/utils/check_run_inputs.py` is what demonstrates it.

**What the re-derivation actually moved.** `data.ipynb` + `features.ipynb` re-run on
`COLLECTION=OE` at commit `17d36ba` (`logs/S3/rederive_stacked.sh`, container `bc3cat-s3`).
Seven of the nine OE derived tables came out **byte-identical**, including every digest S2's
other twelve runs depend on. Only the stacked pair moved: norm `81cd501b…` → `4939d99f…`, feats
`7b0894e6…` → `f34c1798…`. Inside the new feature table, **all 26 pre-existing columns are
identical row for row** and only `texto_modification_count` / `texto_modification_types` are
appended — so S2's stacked Acc@1 describes exactly the inputs it described before, and the digest
change is metadata. Asserted by `tests/test_intake_20260927.py`, not by this paragraph.

**The corrected dose, which is the point of the delivery.** `texto_modification_count` runs 1–6
(mode 4: 5 · 1,252 · 1,465 · 1,799 · 401 · 76) where the original `modification_count` runs 2–8
(mode 5). Five stacked queries carry a single visible modification. S3 work item 4 re-stratifies
S2's by-dose table on the corrected field; `modification_count` is not used for any
stratification again (D-025).

**Digests of the delivered files as taken in are in [`MANIFEST.md`](MANIFEST.md)**, which now also
covers the derived tables — it listed only the deliveries until S3, so every OE run made before
then was stamped against a digest this branch did not record.

## 2026-09-17 — E3 balanced dose set

**Taken in:** S3 work item 2 (2026-09-27) · **Decision:** D-009

Producer: `bc3cat-dataset` `synthetic`, `scripts/build_dose_ladder.py`, config
`configs/synthetic/variant_budgets_OE_dose.yaml`, **seed 42**, run `e3-20260917T093057Z`,
generated at `e057907`, repackaged at `903d07b8`. Upstream reports the run reproduces byte for
byte. Answered point by point in `bc3cat-dataset/docs/synthetic/E3_DELIVERY_RESPONSE.md`.

| File | Records | SHA-256 prefix |
|---|---:|---|
| `OE_dose_texto.json` | 3,000 | `555fab84d134886f` |
| `OE_isolated_texto.json` | 5,400 | `054041ff05349fae` |
| `OE_leaf_applicability.jsonl` | 1,500 | `eda12d17c323add4` |

**It arrived on 2026-09-17 and was recorded on 2026-09-27**, having sat unregistered for ten days
while `STATE.md` said it was blocked and waiting. See the D-009 note; the delay is recorded because
the provenance failure is the interesting part, not the files.

**Every claim the response makes was re-derived from the files** (`tests/test_intake_e3.py`, 23
tests), and all of them held:

- 600 leaves, each carrying the **complete ladder 1–5**, exactly 600 queries per rung.
- The ladder is **nested**: the types at count *k* are the types at *k*−1 **plus exactly one**, so
  consecutive rungs on one leaf differ by a single modification. This is what makes the dose slope
  a within-item contrast and admits paired rung-to-rung comparisons.
- The isolated set is the same 600 leaves × the 9 types, one modification each — so "the sum of the
  isolated effects" in H4 is a sum over the *same* population as the ladder.
- All 8,400 `gold_item_key` resolve against the 70,242-leaf corpus, every `parent_key` agrees with
  it, and no query is byte-identical to its target.
- `modification_count` equals the distinct type count everywhere: these sets are exact, so they
  carry no `texto_modification_*` field and need none (contrast D-025).
- `available_types` ⊆ `applicable_types` on all 1,500 probed leaves; `in_pool` marks exactly the 600
  ladder leaves; every ladder leaf admits all nine types.

**Three limitations, measured here and binding on S8.**

1. **Two interactions are not identifiable.** `reorder` × `template_paraphrase` and
   `unit_conversion` × `unit_expansion` never co-occur, by construction — each pair rewrites the
   same span. S8 must not claim those interactions. The tests pin this, so that a later delivery
   changing it fails loudly instead of being inherited in silence.
2. **Coverage is 7 of 83 concepts**, all OEB canalizations: `OEB020$` 61 leaves, `OEB030$` 87,
   `OEB040$` 96, `OEB230$` 93, `OEB280$` 87, `OEB290$` 87, `OEB300$` 89. Upstream explains this as
   structural: a clean count-5 cell needs leaves admitting ≥6 types on distinct TEXTO spans, and
   only these families have them; relaxing it would fix the composition at count 5 and bring back
   the very confound E3 exists to remove. **They straddle our split** — dev `OEB020$ 030$ 230$
   290$` (328 leaves, 1,640 dose / 2,952 isolated queries), test `OEB040$ 280$ 300$` (272 leaves,
   1,360 / 2,448). So a dev-side slope rests on 328 leaves — well powered *within* item — but a
   **concept-clustered interval on it resamples four clusters**, and under D-030 that is what a
   threshold is read against. S8 states this rather than discovers it.
3. **`unit_conversion` is thin**: 39 items at count 1 against ≥70 for the other eight (18 on the
   dev side), because these concepts admit only four approved rewrites and each is capped at 40
   uses so that a type's effect is not one repeated edit.

**D-033 costs nothing here:** no ladder leaf shares its `texto` with a sibling — the duplicate
groups are confined to `OEA050$` and `OEG050$`, and E3 covers only OEB.

**Not wired into the harness.** These are registered, not runnable: `run_context.QUERY_SETS`
reserves the single name `balanced_texto` (D-008 amended) and the delivery is **two** query sets.
Naming them, and deciding whether the isolated set is a query set or the reference the dose slope
is measured against, is S8's first design question — S3 deliberately leaves it open rather than
half-wiring it.
