"""D-033's exclusion, and the one equality that licenses it (S3 work item 3).

Item-level scoring drops the queries whose gold leaf shares its `texto` with a sibling: two leaves
carry the same text, so no ranking could have preferred the right one, and counting such a query as
a miss measures the corpus rather than the method. Parent-level scoring drops nothing, because no
group crosses a concept. The corpus itself is untouched — the duplicated leaves stay indexed as
distractors, since ambiguity is a property of the gold and not of the pool.

The re-score is a **subset-and-reaverage** over S2's own per-query tables, not a second scorer. That
is only legitimate because the mean of those per-query columns reproduces the run's reported
`metrics_dual.json`, and that equality is the first thing tested here. If it ever breaks, the
generator must recompute from the stored top-100 lists instead, and this test is what would say so.

Acc@1, Recall@k, RR and nDCG@10 are per-query values whose metric is their mean, so the mean over a
subset is exactly the metric on that subset. Nothing here depends on that being true of a metric
that is *not* a per-query mean — and if such a metric is ever added, it cannot be re-scored this way.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.archived_runs import run_dir_as_of

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"
RUNS = REPO / "runs" / "OE"  # S2's runs; the two rules arms from the archive (S5 A1)
SIDECAR = PROCESSED / "OE_duplicate_texto_groups.json"

#: The exclusion D-033 states, per query set: (queries, excluded, concepts before, after).
D033 = {
    "texto": (35_422, 776, 42, 40),
    "single_texto": (2_206, 29, 42, 40),
    "stacked_texto": (2_521, 55, 41, 39),
}

METHODS = (
    "bm25_unigram_params__k1-0.60__b-0.35__OE",
    "bm25_unigram__k1-0.60__b-0.35__OE",
    "bge_m3_colbert__OE",
    "structured_pipeline_rules__OE",
    "structured_pipeline_rules_valuenorm__OE",
)

pytestmark = pytest.mark.skipif(
    not (RUNS / "texto" / METHODS[0] / "results_perquery.parquet").is_file(),
    reason="runs/ is git-ignored and absent in this checkout",
)


@pytest.fixture(scope="module")
def flagged():
    side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    return {member for group in side["groups"].values() for member in group}


@pytest.fixture(scope="module")
def perquery():
    pd = pytest.importorskip("pandas")
    return {
        (queryset, method): pd.read_parquet(
            run_dir_as_of("S2", "OE", queryset, method, repo=REPO) / "results_perquery.parquet"
        )
        for queryset in D033
        for method in METHODS
    }


# --- the licence: subsetting is the harness's own metric --------------------------------


@pytest.mark.parametrize("queryset", sorted(D033))
@pytest.mark.parametrize("target", ["item", "parent"])
def test_per_query_mean_reproduces_the_reported_metric(perquery, queryset, target):
    """Checked on the FULL population, before any filter.

    Without this the re-score would be a reimplementation of the metrics dressed as a filter.
    """
    for method in METHODS:
        reported = json.loads(
            (run_dir_as_of("S2", "OE", queryset, method, repo=REPO) / "metrics_dual.json").read_text(encoding="utf-8")
        )
        overall = next(
            row["Acc@1"]
            for row in reported
            if row["target"] == target and row["scope"] == "overall"
        )
        observed = float(perquery[(queryset, method)][f"{target}_acc1"].mean())
        assert observed == pytest.approx(overall, abs=5e-5), f"{queryset}/{method}/{target}"


# --- the exclusion is what D-033 says it is --------------------------------------------


@pytest.mark.parametrize("queryset", sorted(D033))
def test_exclusion_counts_match_the_decision(perquery, flagged, queryset):
    queries, excluded, concepts_all, concepts_kept = D033[queryset]
    frame = perquery[(queryset, METHODS[0])]
    kept = frame[~frame["gold_item_key"].isin(flagged)]
    assert len(frame) == queries
    assert len(frame) - len(kept) == excluded
    assert frame["gold_parent_key"].nunique() == concepts_all
    assert kept["gold_parent_key"].nunique() == concepts_kept


@pytest.mark.parametrize("queryset", sorted(D033))
def test_the_excluded_set_is_the_same_for_every_method(perquery, flagged, queryset):
    """It is a property of the query's gold, not of any ranking — so if it differed by
    method, the exclusion would be selecting on the outcome."""
    reference = None
    for method in METHODS:
        frame = perquery[(queryset, method)]
        dropped = set(frame.loc[frame["gold_item_key"].isin(flagged), "query_item_key"])
        if reference is None:
            reference = dropped
        assert dropped == reference, f"{queryset}: {method} excludes a different set"


@pytest.mark.parametrize("queryset", sorted(D033))
def test_the_two_wholly_duplicated_concepts_are_the_ones_that_drop_out(
    perquery, flagged, queryset
):
    frame = perquery[(queryset, METHODS[0])]
    kept = frame[~frame["gold_item_key"].isin(flagged)]
    lost = set(frame["gold_parent_key"]) - set(kept["gold_parent_key"])
    assert lost == {"OEA050$", "OEG050$"}


def test_no_duplicate_group_crosses_a_concept(flagged):
    """Why parent-level scoring excludes nothing: the ambiguity never reaches the parent."""
    side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    for group_id, members in side["groups"].items():
        assert len({m[:6] for m in members}) == 1, group_id


def test_parent_level_keeps_every_query(perquery, flagged):
    """The asymmetry is the decision: item-level filters, parent-level does not."""
    for queryset in D033:
        frame = perquery[(queryset, METHODS[0])]
        assert len(frame) == D033[queryset][0]
        # a parent-level figure over the filtered population would differ; confirm it would,
        # so the asymmetry is doing real work rather than being decorative
        kept = frame[~frame["gold_item_key"].isin(flagged)]
        assert len(kept) < len(frame)


# --- the oracle arm is untouched, which is evidence rather than robustness --------------


def test_the_oracle_arm_misses_no_duplicate_gold(perquery, flagged):
    """`bm25_unigram_params` separates leaves that share a `texto` because it indexes parameter
    tokens minted from the query's own `parameters` field — information a real query does not
    carry (D-010). A text-only method cannot do this even in principle, so a zero here is the
    oracle signal, not robustness. If this ever became non-zero, D-010's reading would need
    revisiting."""
    frame = perquery[("texto", "bm25_unigram_params__k1-0.60__b-0.35__OE")]
    missed = frame[frame["item_acc1"] == 0]
    assert int(missed["gold_item_key"].isin(flagged).sum()) == 0


def test_colberts_identity_shortfall_was_mostly_undecidable(perquery, flagged):
    """Recorded as information, not as a re-reading of G1 (D-032).

    484 of `bge_m3_colbert`'s 492 identity misses had a duplicated gold. The arm G1 called
    *ambiguous* reads its own target back essentially perfectly once the undecidable queries are
    removed.
    """
    frame = perquery[("texto", "bge_m3_colbert__OE")]
    missed = frame[frame["item_acc1"] == 0]
    undecidable = int(missed["gold_item_key"].isin(flagged).sum())
    assert len(missed) == 492
    assert undecidable == 484


# --- S2's record is not disturbed ------------------------------------------------------


def test_the_s2_results_directory_still_holds_what_s2_reported():
    """`results/S2/` is the record of what S2 *reported*; the difference between it and
    `results/S3/s2_rescored/` is itself a result, so the re-score must not overwrite it."""
    s2 = REPO / "docs" / "synthetic-oe" / "results" / "S2"
    identity = (s2 / "identity.md").read_text(encoding="utf-8")
    assert "0.9861" in identity, "S2's ColBERT identity figure is gone from its own record"
    assert "0.8870" in identity, "S2's bm25_unigram identity figure is gone from its own record"


# --- work item 4: stratifying on the corrected dose --------------------------------------
#
# S2's per-query tables predate `texto_modification_count`, so the by-dose table joins it on from
# the re-derived feature table. That join is the single point where this table could go quietly
# wrong: a partial or mis-keyed join would produce a plausible stratification of the wrong rows.


@pytest.fixture(scope="module")
def stacked_feats():
    pd = pytest.importorskip("pandas")
    path = PROCESSED / "OE_stacked_texto_feats.parquet"
    if not path.is_file():
        pytest.skip("stacked feature table absent")
    return pd.read_parquet(path)


def test_the_feature_table_carries_the_corrected_dose(stacked_feats):
    """Without S3 work item 1's loader change (A1) the field never reaches here."""
    assert "texto_modification_count" in stacked_feats.columns
    assert "texto_modification_types" in stacked_feats.columns


def test_the_dose_join_is_one_to_one_and_complete(perquery, stacked_feats):
    for method in METHODS:
        frame = perquery[("stacked_texto", method)]
        joined = frame.merge(
            stacked_feats[["item_key", "texto_modification_count", "modification_count"]].rename(
                columns={"item_key": "query_item_key", "modification_count": "mc_feats"}
            ),
            on="query_item_key",
            how="left",
            validate="one_to_one",
        )
        assert len(joined) == len(frame)
        assert joined["texto_modification_count"].notna().all(), method


def test_the_join_matched_the_right_rows(perquery, stacked_feats):
    """`modification_count` exists on both sides and must agree — a cheap check that the join
    lined up the rows it claims to, rather than merely finding a key for each."""
    for method in METHODS:
        frame = perquery[("stacked_texto", method)]
        joined = frame.merge(
            stacked_feats[["item_key", "modification_count"]].rename(
                columns={"item_key": "query_item_key", "modification_count": "mc_feats"}
            ),
            on="query_item_key",
            validate="one_to_one",
        )
        assert (joined["modification_count"] == joined["mc_feats"]).all(), method


def test_the_visible_dose_is_never_above_the_field_s2_used(perquery, stacked_feats):
    """The direction the defect has to run: the TEXTO cannot show more than was applied.

    If this inverted, the correction would be doing something other than what upstream described.
    """
    frame = perquery[("stacked_texto", METHODS[0])]
    joined = frame.merge(
        stacked_feats[["item_key", "texto_modification_count"]].rename(
            columns={"item_key": "query_item_key"}
        ),
        on="query_item_key",
        validate="one_to_one",
    )
    assert (joined["texto_modification_count"] <= joined["distinct_modification_count"]).all()


def test_the_correction_actually_moves_queries_between_strata(perquery, stacked_feats):
    """Guards against a table that replaces S2's and says the same thing.

    S2 called 730 dev queries dose 5; only 193 show five modifications in the TEXTO. If the two
    fields agreed, work item 4 would be ceremony.
    """
    frame = perquery[("stacked_texto", METHODS[0])]
    joined = frame.merge(
        stacked_feats[["item_key", "texto_modification_count"]].rename(
            columns={"item_key": "query_item_key"}
        ),
        on="query_item_key",
        validate="one_to_one",
    )
    moved = (joined["texto_modification_count"] != joined["distinct_modification_count"]).sum()
    assert moved > 0, "the corrected field changes no stratum — the correction is cosmetic"
    at_five = joined[joined["distinct_modification_count"] == 5]
    assert len(at_five) == 730
    assert int((at_five["texto_modification_count"] == 5).sum()) == 193


def test_the_high_dose_cells_rest_on_few_concepts(perquery, stacked_feats):
    """The confound the table has to declare, asserted so it cannot be quietly dropped.

    Dose is not assigned at random: a leaf receives many modifications because its concept admits
    many. So the high-dose cells come from progressively fewer, larger families, and a slope read
    off them confounds dose with family. This is why H4 is answered on E3 (D-009), not here.
    """
    frame = perquery[("stacked_texto", METHODS[0])]
    joined = frame.merge(
        stacked_feats[["item_key", "texto_modification_count"]].rename(
            columns={"item_key": "query_item_key"}
        ),
        on="query_item_key",
        validate="one_to_one",
    )
    per_dose = joined.groupby("texto_modification_count")["gold_parent_key"].nunique()
    assert per_dose.loc[2] > per_dose.loc[4] > per_dose.loc[5] >= per_dose.loc[6]
    assert per_dose.loc[6] <= 3, "the top dose cell is no longer a handful of concepts"


# --- criterion 13: a superseded query set stays resolvable ------------------------------


def test_the_superseded_stacked_feature_table_is_still_findable_by_digest():
    """S2's three stacked runs are stamped `7b0894e6…`, which the S3 re-derivation superseded.

    Versioning the JSON alone would not have saved them: `run_meta.json` records the digest of the
    *derived* table the run actually read. So the check is not that a file with a similar name
    exists, but that some file in `data/processed` still carries the exact digest those runs name.
    """
    import hashlib

    stamped = {
        json.loads((RUNS / "stacked_texto" / m / "run_meta.json").read_text(encoding="utf-8"))[
            "query_set_sha256"
        ]
        for m in METHODS
    }
    assert len(stamped) == 1, "S2's stacked runs disagree about their query set"
    wanted = stamped.pop()

    def sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()

    carriers = [p.name for p in PROCESSED.iterdir() if p.is_file() and sha256(p) == wanted]
    assert carriers, f"no file carries {wanted[:16]}…; S2's stacked runs no longer resolve"
