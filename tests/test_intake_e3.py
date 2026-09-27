"""The E3 balanced dose set, checked against the claims made for it (S3 work item 2, D-009).

E3 is the one data extension `RESEARCH_PROPOSAL` depends on. It exists because the stacked set
cannot identify interactions: `reorder` never co-occurs there and `template_paraphrase` is in
100 % of items, so "count" and "which types" are confounded and H4 is untestable on it.

Upstream answered the request point by point in `bc3cat-dataset/docs/synthetic/
E3_DELIVERY_RESPONSE.md`, and that document is unusually precise — which is exactly why its
claims are re-derived here instead of quoted. Every number below was checked against the files:
the nested ladder, the 600-per-rung balance, the two exclusive pairs, the per-concept leaf counts,
the `unit_conversion` shortfall. All of them held.

Several of these tests pin **limitations** rather than guarantees — the two non-identifiable
interactions, the seven-concept coverage. They are written to fail if a later delivery changes
them, because a limitation that quietly disappears is as dangerous as one that quietly appears:
S8's inference is planned around these, and the plan must be revisited, not silently inherited.
"""

from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

DOSE = PROCESSED / "OE_dose_texto.json"
ISOLATED = PROCESSED / "OE_isolated_texto.json"
APPLICABILITY = PROCESSED / "OE_leaf_applicability.jsonl"

#: Digests from `bc3cat-dataset/data/synthetic/handoff_OE/MANIFEST.md`, run `e3-20260917T093057Z`.
EXPECTED = {
    "OE_dose_texto.json": "555fab84d134886f85ece40115ffd485e796fd4e96291e6a9af3129004a80819",
    "OE_isolated_texto.json": "054041ff05349fae79fd5b91ff111f4fe574b37f7f8ee9647cea044503c5e3ce",
    "OE_leaf_applicability.jsonl": "eda12d17c323add48a7d8deac0f93e767188824950357303b497a7ca8d3fbaa3",
}

#: Per-concept leaf counts the delivery response states under "Limitations 1".
CLAIMED_COVERAGE = {
    "OEB020$": 61, "OEB030$": 87, "OEB040$": 96, "OEB230$": 93,
    "OEB280$": 87, "OEB290$": 87, "OEB300$": 89,
}

THE_NINE = {
    "compression", "expansion", "num_to_text", "paraphrase", "reorder",
    "synonym_label", "template_paraphrase", "unit_conversion", "unit_expansion",
}

pytestmark = pytest.mark.skipif(
    not DOSE.exists(), reason="data/processed is git-ignored and absent in this checkout"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@pytest.fixture(scope="module")
def dose():
    return json.loads(DOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def isolated():
    return json.loads(ISOLATED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def applicability():
    return [
        json.loads(line)
        for line in APPLICABILITY.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture(scope="module")
def parent_of():
    corpus = json.loads((PROCESSED / "OE_texto.json").read_text(encoding="utf-8"))
    return {r["item_key"]: r["parent_key"] for r in corpus}


@pytest.fixture(scope="module")
def ladder(dose):
    """leaf -> {count: set(types)}."""
    out: dict[str, dict[int, set[str]]] = collections.defaultdict(dict)
    for q in dose:
        out[q["gold_item_key"]][q["modification_count"]] = set(q["modification_types"])
    return out


# --- the files are the delivered ones --------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_digest_matches_the_upstream_manifest(name):
    assert sha256(PROCESSED / name) == EXPECTED[name]


def test_sizes(dose, isolated, applicability):
    assert len(dose) == 3000
    assert len(isolated) == 5400
    assert len(applicability) == 1500


# --- the gold resolves, which is what makes the set usable at all -----------------------


def test_every_gold_resolves_against_the_corpus(dose, isolated, parent_of):
    absent = [q["gold_item_key"] for q in dose + isolated if q["gold_item_key"] not in parent_of]
    assert not absent, f"{len(absent)} of 8,400 gold keys absent from the corpus"


def test_every_parent_key_agrees_with_the_corpus(dose, isolated, parent_of):
    wrong = [
        q["item_key"]
        for q in dose + isolated
        if parent_of[q["gold_item_key"]] != q["parent_key"]
    ]
    assert not wrong, f"{len(wrong)} records disagree with the corpus on parent_key"


def test_no_query_is_identical_to_its_target(dose, isolated):
    """A query that equals its target is an identity rendering, not a dose rung."""
    corpus = json.loads((PROCESSED / "OE_texto.json").read_text(encoding="utf-8"))
    texto_of = {r["item_key"]: r["text"] for r in corpus}
    same = [q["item_key"] for q in dose + isolated if q["text"] == texto_of[q["gold_item_key"]]]
    assert not same, f"{len(same)} queries are byte-identical to their target"


# --- the ladder: the part of the request that mattered most ----------------------------


def test_both_sets_cover_the_same_600_leaves(dose, isolated):
    """Isolated effects must be measured on the same leaves as the ladder, or the
    'sum of isolated effects' in H4 is a sum over a different population."""
    assert {q["gold_item_key"] for q in dose} == {q["gold_item_key"] for q in isolated}
    assert len({q["gold_item_key"] for q in dose}) == 600


def test_exactly_600_queries_per_rung(dose):
    per_rung = collections.Counter(q["modification_count"] for q in dose)
    assert sorted(per_rung) == [1, 2, 3, 4, 5]
    assert set(per_rung.values()) == {600}


def test_every_leaf_carries_the_complete_ladder(ladder):
    assert len(ladder) == 600
    incomplete = [leaf for leaf, rungs in ladder.items() if sorted(rungs) != [1, 2, 3, 4, 5]]
    assert not incomplete, f"{len(incomplete)} leaves do not carry counts 1-5"


def test_the_ladder_is_nested_and_steps_by_exactly_one(ladder):
    """The property that makes the slope a within-item contrast.

    Nested means the types at count k are the types at k-1 plus one, so consecutive rungs on
    one leaf differ by a single modification. Without it, a count effect is confounded with a
    change of composition even inside the same leaf.
    """
    problems = []
    for leaf, rungs in ladder.items():
        for k in range(2, 6):
            if not rungs[k - 1] <= rungs[k]:
                problems.append(f"{leaf}: rung {k-1} is not contained in rung {k}")
            elif len(rungs[k] - rungs[k - 1]) != 1:
                problems.append(f"{leaf}: rung {k} adds {len(rungs[k]-rungs[k-1])} types, not 1")
    assert not problems, problems[:5]


def test_the_isolated_set_is_nine_single_modification_cells(isolated):
    assert {q["modification_count"] for q in isolated} == {1}
    per_type = collections.Counter(q["modification_types"][0] for q in isolated)
    assert set(per_type) == THE_NINE
    assert set(per_type.values()) == {600}


def test_counts_agree_with_the_distinct_type_lists(dose, isolated):
    """D-025's defect, absent here by construction — and verified, not assumed.

    The stacked set's `modification_count` overstates the dose reaching the TEXTO, which is why
    every stacked stratification now reads `texto_modification_count`. The E3 sets are exact, so
    they carry no such field; that exactness is the thing being checked.
    """
    for name, records in (("dose", dose), ("isolated", isolated)):
        bad = [
            q["item_key"]
            for q in records
            if q["modification_count"] != len(set(q["modification_types"]))
        ]
        assert not bad, f"{name}: {len(bad)} records whose count disagrees with their types"


# --- limitations, pinned so they cannot change quietly ---------------------------------


@pytest.mark.parametrize(
    "pair", [("reorder", "template_paraphrase"), ("unit_conversion", "unit_expansion")]
)
def test_the_two_exclusive_pairs_never_co_occur(dose, pair):
    """A limitation, not a guarantee (response §1).

    Both pairs rewrite the same span — the TEXTO template, or one parameter value — so they
    cannot be composed. Those two interactions are therefore **not identifiable** from this set,
    and S8 must not claim them. If a later delivery makes them co-occur, this test fails, which
    is the point: the identifiability changed and S8's plan has to be revisited rather than
    silently inherited.
    """
    a, b = pair
    together = [
        q["item_key"]
        for q in dose
        if a in q["modification_types"] and b in q["modification_types"]
    ]
    assert not together, f"{a} x {b} now co-occur in {len(together)} items — re-read §1"


def test_coverage_is_the_seven_concepts_claimed(dose, parent_of):
    """Also a limitation (response "Limitations 1"): 7 of 83 concepts, all OEB canalizations."""
    observed = collections.Counter(
        parent_of[leaf] for leaf in {q["gold_item_key"] for q in dose}
    )
    assert dict(observed) == CLAIMED_COVERAGE


def test_the_split_partitions_the_seven_as_four_dev_and_three_test(dose):
    """The constraint S8 inherits, and the reason a clustered interval will be near-useless.

    D-030 reads a threshold against the concept-clustered interval. On the dev side that
    bootstrap resamples **four** clusters. The within-leaf slope is still well powered — 328
    leaves x 5 rungs — but any concept-clustered interval on it will be extremely wide, and S8
    has to say so rather than discover it.
    """
    splits = (REPO / "docs" / "synthetic-oe" / "SPLITS.md").read_text(encoding="utf-8")
    dev = set(splits.split("## dev — 42 concepts")[1].split("```")[1].split())
    test = set(splits.split("## test — 41 concepts")[1].split("```")[1].split())

    covered = set(CLAIMED_COVERAGE)
    assert covered <= (dev | test), "a covered concept is in neither side of the split"
    assert not (covered & dev) & (covered & test), "a concept is in both sides"

    dev_concepts = covered & dev
    assert dev_concepts == {"OEB020$", "OEB030$", "OEB230$", "OEB290$"}
    assert covered & test == {"OEB040$", "OEB280$", "OEB300$"}

    dev_queries = [q for q in dose if q["parent_key"] in dev_concepts]
    assert len(dev_queries) == 1640
    assert len({q["gold_item_key"] for q in dev_queries}) == 328


def test_unit_conversion_is_the_thin_type(dose):
    """Response §3: 39 items at count 1 against ~300-390 for the others, because these concepts
    admit only four approved `unit_conversion` rewrites and each is capped at 40 uses."""
    count_one = collections.Counter(
        t for q in dose if q["modification_count"] == 1 for t in q["modification_types"]
    )
    assert count_one["unit_conversion"] == 39
    others = [n for t, n in count_one.items() if t != "unit_conversion"]
    assert min(others) >= 70, "the other eight types are no longer balanced at count 1"


# --- applicability, which is what keeps cross-count comparisons honest -----------------


def test_applicability_rows_are_well_formed(applicability, parent_of):
    required = {"leaf_item_key", "applicable_types", "available_types", "in_pool"}
    assert all(required <= set(row) for row in applicability)
    keys = [row["leaf_item_key"] for row in applicability]
    assert len(set(keys)) == len(keys) == 1500
    assert not [k for k in keys if k not in parent_of], "a probed leaf is not in the corpus"


def test_available_is_always_a_subset_of_applicable(applicability):
    """`applicable` is what the grammar admits; `available` is what actually changes this leaf's
    TEXTO. The second cannot exceed the first."""
    bad = [
        row["leaf_item_key"]
        for row in applicability
        if not set(row["available_types"]) <= set(row["applicable_types"])
    ]
    assert not bad, f"{len(bad)} rows claim an available type the grammar does not admit"


def test_in_pool_marks_exactly_the_600_ladder_leaves(applicability, dose):
    in_pool = {row["leaf_item_key"] for row in applicability if row["in_pool"]}
    assert in_pool == {q["gold_item_key"] for q in dose}


def test_every_ladder_leaf_admits_all_nine_types(applicability):
    """Why the ladder can reach count 5 with a drawn composition rather than a forced one."""
    short = [
        row["leaf_item_key"]
        for row in applicability
        if row["in_pool"] and set(row["available_types"]) != THE_NINE
    ]
    assert not short, f"{len(short)} ladder leaves do not admit all nine types"


# --- the duplicate-texto exclusion costs nothing here ----------------------------------


def test_no_ladder_leaf_shares_its_texto_with_a_sibling(dose):
    """D-033 excludes duplicate-gold queries from item-level scoring. The duplicate groups are
    confined to `OEA050$` and `OEG050$`, and E3 covers only OEB, so the exclusion removes no E3
    query — worth knowing before S8 budgets for it."""
    sidecar = PROCESSED / "OE_duplicate_texto_groups.json"
    if not sidecar.exists():
        pytest.skip("duplicate sidecar absent")
    flagged = {
        m for g in json.loads(sidecar.read_text(encoding="utf-8"))["groups"].values() for m in g
    }
    assert not ({q["gold_item_key"] for q in dose} & flagged)
