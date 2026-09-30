# Sprint S5 — E1 ablation, Track B (structured) · report

| Field | Value |
|---|---|
| **Design** | [`SPRINT_S5_DESIGN.md`](SPRINT_S5_DESIGN.md) · frozen at `432b39e` · amendments A1–A3 in [`SPRINT_S5_AMENDMENTS.md`](SPRINT_S5_AMENDMENTS.md) |
| **Closed** | 2026-09-30 (report written). Audit 2026-09-30 **PASS WITH FINDINGS** ([`SPRINT_S5_AUDIT.md`](SPRINT_S5_AUDIT.md)); all four resolved. **done** 2026-09-30. See [Audit response](#audit-response) |
| **Code commit** | 6 structured runs at `26ed9ff`, all `code_dirty: false`. 6 reference runs read, not re-run, at `31bf1a1`. Generator `src/utils/build_results_s5.py` |
| **Query-set digests** | `single_texto` `e5b79ae4` · `texto` `643f1a72` (ColBERT's `texto` reads `OE_long_norm` `75477221`) |
| **Runs** | `runs/OE/{texto,single_texto}/structured_pipeline_{rules,rules_valuenorm,oracleparams_valuenorm}__OE` · split `dev`. S2's four rules runs archived at `runs/_archive/S2` (A1) |
| **Results** | [`results/S5/`](../results/S5): T1–T7, generated, byte-identical on regeneration, under the prose guard |

## What ran

Three structured arms × nine single types on OE dev, each query paired with the same arm's identity result on
its gold, and set query by query against three S4 reference arms. Every stamp is in
[`run_provenance.md`](../results/S5/run_provenance.md) (T7).

| Arm | Config SHA-256 | Role |
|---|---|---|
| `structured_pipeline_rules_valuenorm__OE` | `e9e2acdc` | the published method, Stage-3 comma fix; **every claim rests on it** |
| `structured_pipeline_rules__OE` | `a3b08f47` | faithful port, for comparability only |
| `structured_pipeline_oracleparams_valuenorm__OE` | `b6e3031c` | **oracle** bound: Stage 2 = the query record's parameters, schema values only (D-010) |
| `bm25_unigram__k1-0.60__b-0.35__OE` | `ec943fef` | deployable reference |
| `bm25_unigram_params__k1-0.60__b-0.35__OE` | `c695c126` | **oracle** reference, the previous study's comparison |
| `bge_m3_colbert__OE` | `130f0fc4` | printed, never predicted (D-029) |

| Block | What | Where |
|---|---|---|
| Harness | Oracle Stage 2 (`param_extractor_oracle.py`), `bind_queries` in the pipeline and `retrieve.ipynb` (A1b), config, tests; `utils/archived_runs.py` | `26ed9ff` |
| Check | Oracle on 20 dev `texto` leaves selects the gold alone; on 20 dev L1 queries abstains on exactly one axis. Over all L1 dev queries, the per-query axis recovery is T4's (generated). An earlier all-2,206 statement had no committed check and is withdrawn (audit) | `tests/test_structured_pipeline.py` · T4 |
| Runs | Oracle new; both rules arms **re-run** (A1a), S2's copies archived and routed | T7 |
| Analysis | T1 ceilings · T2/T3 profile · T4 stages · T5 contrasts · T6 predictions and G2 | [`results/S5/`](../results/S5) |

**Population** (S4's). 2,206 dev queries over 42 concepts; item level scores 2,176 (29 D-033 golds, the P7
query); parent level scores all. Layers reach different leaves, so any comparison across them is
**between-population**; L2 is **5 concepts**. Pantry artefacts are in every figure (D-004; S6).
**Tie-free Acc@1 is the reading of every contrast** (D-028): as-run values are printed beside it in T5.

## Findings

**1. The published pipeline ranks below deployable BM25 under L1 (H3 contradicted).** On pooled L1, tie-free,
`rules_valuenorm` − `bm25_unigram` is −0.0525 [−0.1338, −0.0105], 39 concepts; on `unit_conversion`
−0.1589 [−0.2345, −0.0667], 12 concepts. Both Q1 tests are **contradicted** (T6). On `num_to_text` it is
−0.0177 [−0.0322, +0.0125], **not supported**, on 9 concepts (‡). Against ColBERT the pooled-L1 difference is
−0.5528 [−0.6008, −0.4721] (T5; not a registered test).

**2. Even perfect literal extraction is not detected overtaking BM25 on pooled L1 (Q2, blind).** The oracle bound
against `bm25_unigram`, pooled L1: −0.0393 [−0.1523, +0.0278], **not supported**. `unit_conversion` −0.1201
[−0.1873, −0.0409], **contradicted**; `num_to_text` +0.0166 [+0.0045, +0.0437], **supported** on 9 concepts (‡).
Where every value stays readable the bound is above BM25 on L2, +0.2592 [+0.2094, +0.2918] on 5 concepts (‡), and
on L3, +0.3403 [+0.2707, +0.3794]; its twin `rules_valuenorm` is below it, −0.1308 [−0.1781, −0.0981] on L2 and
−0.0677 [−0.1438, +0.1091] on L3 (T5). Between-population across layers.

**3. Why: under L1 the rewritten axis is blank, and nothing orders what remains (T4).** The oracle recovers every
gold axis on 0.0039 of L1 queries (P8's case-only ones) and abstains on exactly one. Its tie set then has a median
of 4 leaves (IQR [3, 8]); on `num_to_text`, 11. The rules extractor recovers every axis on 0.0513 of L1 queries
and on none under `unit_conversion` or `num_to_text`. A pipeline that reads schema literals cannot choose among
those siblings. BM25 can still use the rest of the text.

**4. The gap to BM25 narrows, but not where H3 puts it (Q3).** DiD `rules_valuenorm` vs `bm25_unigram`:
L1 +0.0656 [−0.1919, +0.2119], **not supported**; L2 +0.0817 [+0.0119, +0.1193], **not supported** (Holm p
0.1624, 5 concepts ‡); L3 +0.0903 [+0.0465, +0.1264], **supported**. At identity on the L1 golds, the
difference is −0.1181 [−0.2349, +0.0966], a concept-clustered interval containing 0. Between-population across layers.

**5. The previous study's comparison does not close either.** Against the oracle `bm25_unigram_params`, pooled
L1: Δ mod −0.1512 [−0.2829, −0.0639]; DiD +0.0975 [−0.1327, +0.2360] (T5). This is deployable against oracle
(D-010), as in the previous study's BM25-against-structured comparison.

**6. Stage-3 ordering changes the reading.** At identity, `rules_valuenorm` scores 0.8136 as run and 0.7532
tie-free; its unique-gold rate is 0.7085 (T1). As run, the pooled-L1 difference to BM25 is −0.0183
[−0.0935, +0.0285], an interval containing 0. Tie-free it is contradicted (finding 1). The oracle's identity item,
tie-free and unique-gold figures are all 0.9975, equal to its parent level (T1).

**7. Profile (T2), side by side.** `rules_valuenorm` retains 0.2988 under pooled L1 and 0.1614 on
`num_to_text`; `reorder` δ is +0.0000. On L2 its δ is −0.1673 and the oracle's +0.0000; on L3, −0.1899 and −0.0118.

**8. Carried caveats, counted.** P8: without the four case-only queries, `synonym_label` Δ mod vs BM25 moves from
−0.0291 to −0.0295; no reading changes. The decimal artefact: 9 `unit_conversion` queries carry a `d.ddd`
decimal, 5 of them one their gold lacks (T4).

**G2 reads no** under the frozen rule: Q1's pooled-L1 test is contradicted (T6). Q2 beside it is not supported.
The plan's consequence, method-contribution priority moving from S11 to S10, is **accepted** by César (D-046).

## Hypotheses

| Hypothesis | Movement | Evidence |
|---|---|---|
| **H3** (rank inversion) | **refuted on dev for the published method**: the ranking does not invert under L1; it is contradicted pooled and on `unit_conversion`. `num_to_text` **unresolved** (9 concepts). The **bound** is not detected inverting on pooled L1 either (interval includes 0); it does on `num_to_text` (9 concepts ‡). S6 does not revisit it; S7 reads the stacked set | Findings 1–3; Q1 ×2 contradicted, Q2 L1 not supported |
| H3, "the previous study's BM25 / structured gap closes or reverses" | **not supported**: the DiD against `bm25_unigram_params` has an interval containing 0 | Finding 5 |
| H1, H2, H4, H5, H6 | **not addressed** | S6–S9 |

## What is now known to be wrong

1. **"Structured extraction pipelines normalise parameter surfaces"** (H3's wording, `RESEARCH_PROPOSAL.md`).
   The published pipeline reads schema literals. So does its oracle bound, which did not detectably beat BM25 on
   pooled L1 (interval includes 0). What the structured approach needs under L1 is a step that *reads* a rewritten
   value, and neither arm has one.
2. **"Perfect extraction would win"**, on pooled L1 and on `unit_conversion`. Perfect on every readable axis, the
   bound still leaves the one rewritten axis blank. The pipeline then has no way to rank a median of 4 siblings
   (finding 3). The exception is `num_to_text`, where the bound wins, +0.0166 [+0.0045, +0.0437] on 9 concepts (‡).
3. **"Structured identity is what it scores as run."** 0.8136 as run, 0.7532 tie-free: key order was worth the difference.
   Read as run, Q1's pooled-L1 test would have been "not supported" rather than "contradicted" (finding 6).
4. **"S2's rules runs are reusable."** Their Stage 1 read an E5 index that S3 rebuilt (D-034), so they could not
   share a Stage 1 with the oracle (A1a).
5. **"H3's closing is L1-specific."** The only detected narrowing is on L3 (finding 4).

## Exit criteria

| # | Met | Evidence |
|---|---|---|
| 1 | yes | `26ed9ff`: oracle mode, config, tests; suite 1135 passed, 1 xfailed, OEB fixture included |
| 2 | yes, as amended | 6 runs clean at `26ed9ff`, dev, 216 of 216 OE runs resolve (`check_run_inputs.py`). Reuse replaced by re-run and archive (A1) |
| 3 | yes | T1–T7 byte-identical on regeneration, under the prose guard. n excluded was first printed in T1–T3 only. It was added to T4, T5 and T6 before this report (columns only, no estimate moved). Every contrast has both intervals, tie-free and as run |
| 4 | yes | 3 arms × 9 types × 2 levels plus three pools and the P8 scope; T5 each arm against three references; no empty cell |
| 5 | yes | T6: 2 supported, 4 not supported, 3 contradicted; Q1 and Q3 labelled confirmatory |
| 6 | yes | G2 read from T6's Q1 pooled-L1 row, Q2 beside it; H3 row above |

## Deviations from design

| Amendment | Deviation | Why |
|---|---|---|
| A1 | The four S2 rules runs re-run, not reused; S2's copies archived, readers routed; `retrieve.ipynb` gains `bind_queries` | Stage 1 reads the E5 index S3 rebuilt; the oracle needs the query record |
| A2 | Tie set is the Stage-1 family when Stage 3 matches nothing | The design left the empty match open; it reaches `rules_faithful` only |
| A3 | A2's "written before any T5 or T6 figure was read" withdrawn; the rule and the tables are recorded as committed together (`93e5a41`) | Audit F4: the order could not be checked |

## What the next sprint inherits

- **S6** — no H3 work. The paired frames of the three structured arms are in `results/S5/`.
- **S7** — the structured arms, oracle included, on the corrected stacked file `c34a222a`.
- **S9** — the value-reading step findings 2–3 name as missing. The bound measures its value: the rewritten
  axis is the whole L1 gap for a literal reader. The LLM extractor is listed there (`RESEARCH_PLAN.md`).
- **S10 / S11** — S10 has priority (D-046); S11, if it runs, builds on S9's value reading.
- **Debt.**
  - Stage 3 still orders by key (tie-free measures it).
  - `index/*/meta.json` still omits the ML stack (H4).
  - `utils/archived_runs.py` is the one place a superseded run is found; S7's stacked re-runs will need it.

## Decisions raised

| ID | Status | What |
|---|---|---|
| D-046 | **Accepted** (César, 2026-09-30) | G2 reads *no* on dev. Priority moves from S11 to S10 per the plan. Record with it that the literal-reading ceiling is the L1 bottleneck (findings 2–3), so any structured route needs S9's value reading first |
| D-047 | **Accepted** (César, 2026-09-30) | A run superseded by a later sprint is copied, checksum-verified, to `runs/_archive/<sprint>/`, and every reader of the earlier sprint is routed through `utils/archived_runs.py` (A1, César's choice) |
| D-028 | note proposed | Tie-free reading changes a structured reading (finding 6); primary for every structured contrast from S5 on |

## Audit response

The audit ([`SPRINT_S5_AUDIT.md`](SPRINT_S5_AUDIT.md), fresh session, 2026-09-30) regenerated T1–T7
byte-identically and traced every quoted figure. It raised 1 major and 3 minor findings. No run was re-made and
no table changed; every fix is to prose or to the amendments record.

| Finding | Resolution |
|---|---|
| F1 — known-wrong 1–2 overstate Q2 | **Fixed.** Known-wrong 1 says the bound "did not detectably beat BM25 on pooled L1 (interval includes 0)". Known-wrong 2 is scoped to pooled L1 and `unit_conversion` and states the `num_to_text` exception, +0.0166 [+0.0045, +0.0437] on 9 concepts (‡). Finding 2's heading and the H3 row are aligned with it |
| F2 — oracle figures without twin or interval | **Fixed.** Finding 2 gives the bound's L2 and L3 figures with their clustered intervals, ‡ on L2, the `rules_valuenorm` twin beside them, and the between-population label. Finding 7 sets `rules_valuenorm`'s L2 / L3 δ beside the oracle's |
| F3 — "trails" on an interval spanning 0 | **Fixed.** Finding 4 drops "trails" and says the concept-clustered interval contains 0 |
| F4 — A2's timing claim uncheckable | **Fixed** by amendment A3 (A2 left unedited, append-only): the rule and the tables are recorded as committed together in `93e5a41` |
| Unverifiable — the all-2,206 oracle check | **Withdrawn.** The committed tests cover 20 `texto` leaves and 20 L1 queries; the all-query L1 recovery is T4's. The Check row now says so |
| Unverifiable — A1's timing; OEB fixture not isolated | **Accepted.** A1 is committed before the runs' timestamps, which is as far as artefacts can show; the OEB fixture runs inside the suite, which passes whole |
