"""S7 work item 1: the stacked set is checked before any S7 run reads it.

Three checks, each a stop condition in the frozen design (`SPRINT_S7_DESIGN.md`, `5e89809`):

**The corrected file agrees with the superseded one on `parameters`.** The 2026-09-27 intake test
(`test_intake_20260927.py`) checked `text`, `id`, `item_key` and `gold_item_key` row for row, and the
feature tables' indexed columns, but not the raw `parameters` dict. The oracle arms read it, so a
difference would make S7's oracle runs measure a query set S2 never saw.

**No dev stacked query is undecidable from its text** (S4 work item 4, D-040's scope clause): none equals
another dev leaf's `texto` — raw or after case and whitespace folding — and none shares its text with
another dev stacked query. P7 was found on `single_texto` by exactly this test.

**The item-level exclusions are what the design expects**: 55 D-033 golds (all in `OEA050$` and
`OEG050$`), and no P7 or P8 key, since both lists name `single_texto` queries.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from utils.splits import split_of_concept

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

STACKED = PROCESSED / "OE_stacked_texto.json"
SUPERSEDED = PROCESSED / "OE_stacked_texto__1bde2115.json"
CORPUS = PROCESSED / "OE_texto.json"
DUPLICATES = PROCESSED / "OE_duplicate_texto_groups.json"
P7 = PROCESSED / "OE_P7_test_exclusion.json"
P8 = PROCESSED / "OE_P8_test_exclusion.json"

pytestmark = pytest.mark.skipif(
    not STACKED.exists(),
    reason="data/processed is git-ignored and absent in this checkout",
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _fold(text: str) -> str:
    return " ".join(text.lower().split())


@pytest.fixture(scope="module")
def corrected():
    return _load(STACKED)


@pytest.fixture(scope="module")
def dev(corrected):
    return [r for r in corrected if split_of_concept(r["parent_key"]) == "dev"]


@pytest.fixture(scope="module")
def dev_leaves():
    return {
        r["item_key"]: r["text"]
        for r in _load(CORPUS)
        if split_of_concept(r["parent_key"]) == "dev"
    }


# --- check 1: parameters ----------------------------------------------------------------


def test_parameters_are_identical_row_for_row(corrected):
    superseded = _load(SUPERSEDED)
    assert len(corrected) == len(superseded) == 4998
    differing = [
        r["item_key"]
        for r, s in zip(corrected, superseded)
        if r["parameters"] != s["parameters"]
    ]
    assert not differing, f"{len(differing)} stacked queries changed `parameters`: S7 stops"


# --- check 2: undecidable queries -------------------------------------------------------


def test_the_dev_population_is_the_one_the_design_counted(dev):
    assert len(dev) == 2521
    assert len({r["gold_item_key"] for r in dev}) == 2521
    assert len({r["parent_key"] for r in dev}) == 41


def test_no_dev_query_renders_another_dev_leafs_texto(dev, dev_leaves):
    exact, folded = defaultdict(set), defaultdict(set)
    for key, text in dev_leaves.items():
        exact[text].add(key)
        folded[_fold(text)].add(key)
    hits = [
        r["item_key"]
        for r in dev
        if (exact.get(r["text"], set()) | folded.get(_fold(r["text"]), set()))
        - {r["gold_item_key"]}
    ]
    assert hits == [], f"undecidable dev stacked queries: {hits}"


def test_no_two_dev_queries_share_a_text(dev):
    shared = [t for t, n in Counter(r["text"] for r in dev).items() if n > 1]
    assert shared == []


# --- check 3: item-level exclusions -----------------------------------------------------


def test_d033_golds_in_dev_stacked(dev):
    groups = _load(DUPLICATES)["groups"]
    members = {k for g in (groups.values() if isinstance(groups, dict) else groups) for k in g}
    excluded = Counter(r["parent_key"] for r in dev if r["gold_item_key"] in members)
    assert sum(excluded.values()) == 55
    assert set(excluded) == {"OEA050$", "OEG050$"}


@pytest.mark.parametrize("path", [P7, P8], ids=["P7", "P8"])
def test_no_p7_or_p8_key_is_a_stacked_query(corrected, path):
    keys = set(_load(path)["item_keys"])
    assert keys.isdisjoint({r["item_key"] for r in corrected})
