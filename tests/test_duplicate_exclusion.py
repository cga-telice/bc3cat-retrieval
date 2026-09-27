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

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"
RUNS = REPO / "runs" / "OE"
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
            RUNS / queryset / method / "results_perquery.parquet"
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
            (RUNS / queryset / method / "metrics_dual.json").read_text(encoding="utf-8")
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
