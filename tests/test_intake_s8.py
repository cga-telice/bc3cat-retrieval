"""S8 work item 1: the E3 sets wired as `dose_texto` and `isolated_texto` (D-052), asserted before any run.

`tests/test_intake_e3.py` re-derives what upstream claimed for the delivery. This file checks what S8's
design (entry state, work item 1) relies on: that both sets resolve through `run_context` and
`balanced_texto` does not, that their derived tables are the JSON row for row with the projection the
design names, that the dev population is the one the design counted, and that no dev query is
undecidable. A nonzero undecidable count stops the sprint for an amendment.

Two entry-state facts are pinned because the design's constraints rest on them: the ladder is nested in
text as well as in labels (1,158 of 1,295 steps keep every token the previous rung inserted), and the
isolated set is a different rewrite draw (89 of 328 rung-1 queries equal the isolated query of the same
leaf and type). A later delivery changing either must fail here, not be inherited.

Text is read on dev only (operating rule 2); test-side rows are checked by key and metadata alone.
`data/processed` is git-ignored, so every test skips in a checkout that lacks it.
"""

from __future__ import annotations

import collections
import difflib
import json
from pathlib import Path

import pandas as pd
import pytest

from utils.run_context import QUERY_SETS, data_paths
from utils.splits import load_split, select_split

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

DOSE = PROCESSED / "OE_dose_texto.json"
ISOLATED = PROCESSED / "OE_isolated_texto.json"
CORPUS = PROCESSED / "OE_texto.json"
DUPLICATES = PROCESSED / "OE_duplicate_texto_groups.json"
TABLES = {
    name: (PROCESSED / f"OE_{name}_norm.parquet", PROCESSED / f"OE_{name}_feats.parquet")
    for name in ("dose_texto", "isolated_texto")
}

DEV_CONCEPTS = {"OEB020$": 61, "OEB030$": 87, "OEB230$": 93, "OEB290$": 87}
TYPES = {
    "synonym_label", "num_to_text", "unit_expansion", "unit_conversion",
    "paraphrase", "compression", "expansion", "reorder", "template_paraphrase",
}
PROJECTION = ("gold_item_key", "parent_key", "modification_types", "modification_count", "applicable_types")

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in [DOSE, ISOLATED, CORPUS, DUPLICATES, *sum(TABLES.values(), ())]),
    reason="data/processed is git-ignored; run build_s8_query_tables.py",
)


def records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dev() -> frozenset[str]:
    return load_split("dev")


@pytest.fixture(scope="module")
def dose() -> list[dict]:
    return records(DOSE)


@pytest.fixture(scope="module")
def isolated() -> list[dict]:
    return records(ISOLATED)


@pytest.fixture(scope="module")
def dose_dev(dose, dev) -> list[dict]:
    return [r for r in dose if r["parent_key"] in dev]


@pytest.fixture(scope="module")
def isolated_dev(isolated, dev) -> list[dict]:
    return [r for r in isolated if r["parent_key"] in dev]


@pytest.fixture(scope="module")
def texto() -> list[dict]:
    return records(CORPUS)


@pytest.fixture(scope="module")
def corpus(texto) -> dict[str, str]:
    return {r["item_key"]: r["text"] for r in texto}


# --------------------------------------------------------------------------- registration


def test_both_sets_are_registered_and_balanced_texto_is_retired():
    assert "dose_texto" in QUERY_SETS and "isolated_texto" in QUERY_SETS
    assert "balanced_texto" not in QUERY_SETS
    paths = data_paths("OE", work_root=REPO)
    for name, (norm, feats) in TABLES.items():
        assert paths.query_json[name] == PROCESSED / f"OE_{name}.json"
        assert paths.query_norm[name] == norm
        assert paths.query_feats[name] == feats


# --------------------------------------------------------------------------- tables


@pytest.mark.parametrize("name,total", [("dose_texto", 3000), ("isolated_texto", 5400)])
def test_tables_are_the_json_row_for_row(name, total):
    source = records(PROCESSED / f"OE_{name}.json")
    for table in TABLES[name]:
        frame = pd.read_parquet(table)
        assert len(frame) == total == len(source)
        assert list(frame["item_key"]) == [r["item_key"] for r in source]
        for field in PROJECTION:
            assert field in frame.columns, f"{table.name} lacks {field}"
        assert list(frame["gold_item_key"]) == [r["gold_item_key"] for r in source]
        assert list(frame["modification_count"]) == [r["modification_count"] for r in source]
        assert [sorted(x) for x in frame["applicable_types"]] == [sorted(r["applicable_types"]) for r in source]


@pytest.mark.parametrize("name,dev_rows", [("dose_texto", 1640), ("isolated_texto", 2952)])
def test_a_dev_selection_holds_only_the_four_dev_concepts(name, dev_rows):
    frame = pd.read_parquet(TABLES[name][1])
    selected = select_split(frame, "dev")
    assert len(selected) == dev_rows
    assert set(selected["parent_key"]) == set(DEV_CONCEPTS)
    assert not set(selected["parent_key"]) & load_split("test")


def test_every_gold_resolves_and_agrees_with_its_parent(dose, isolated, texto):
    parent_of = {r["item_key"]: r["parent_key"] for r in texto}
    for r in dose + isolated:
        assert r["gold_item_key"] in parent_of
        assert parent_of[r["gold_item_key"]] == r["parent_key"]


# --------------------------------------------------------------------------- dev population


def test_dev_population_is_the_one_the_design_counted(dose_dev, isolated_dev):
    leaves = collections.defaultdict(set)
    for r in dose_dev:
        leaves[r["parent_key"]].add(r["gold_item_key"])
    assert {k: len(v) for k, v in leaves.items()} == DEV_CONCEPTS
    assert collections.Counter(r["modification_count"] for r in dose_dev) == {k: 328 for k in range(1, 6)}
    iso_leaves = collections.defaultdict(set)
    for r in isolated_dev:
        assert r["modification_count"] == 1
        iso_leaves[r["gold_item_key"]].add(r["modification_types"][0])
    assert set(iso_leaves) == {r["gold_item_key"] for r in dose_dev}
    assert all(types == TYPES for types in iso_leaves.values())


def test_the_ladder_is_nested_per_leaf(dose_dev):
    by_leaf = collections.defaultdict(dict)
    for r in dose_dev:
        by_leaf[r["gold_item_key"]][r["modification_count"]] = set(r["modification_types"])
    for rungs in by_leaf.values():
        assert sorted(rungs) == [1, 2, 3, 4, 5]
        for k in range(2, 6):
            assert rungs[k - 1] < rungs[k] and len(rungs[k] - rungs[k - 1]) == 1


def _inserted(a: str, b: str) -> collections.Counter:
    ops = difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).get_opcodes()
    out: collections.Counter = collections.Counter()
    for op, _i1, _i2, j1, j2 in ops:
        if op in ("insert", "replace"):
            out.update(b.split()[j1:j2])
    return out


def test_the_ladder_is_nested_in_text(dose_dev, corpus):
    """Pinned (design, entry state): 1,158 of 1,295 steps keep every token rung k-1 inserted."""
    by_leaf = collections.defaultdict(dict)
    for r in dose_dev:
        by_leaf[r["gold_item_key"]][r["modification_count"]] = r["text"]
    steps = complete = 0
    for gold, rungs in by_leaf.items():
        for k in range(2, 6):
            previous = _inserted(corpus[gold], rungs[k - 1])
            if not previous:
                continue
            current = collections.Counter(rungs[k].split())
            kept = sum(min(n, current[w]) for w, n in previous.items())
            steps += 1
            complete += kept == sum(previous.values())
    assert (complete, steps) == (1158, 1295)


def test_the_isolated_set_is_a_different_draw(dose_dev, isolated_dev):
    """Pinned (design, entry state): 89 of 328 rung-1 queries equal the isolated query."""
    iso = {(r["gold_item_key"], r["modification_types"][0]): r["text"] for r in isolated_dev}
    rung1 = [r for r in dose_dev if r["modification_count"] == 1]
    equal = sum(iso[(r["gold_item_key"], r["modification_types"][0])] == r["text"] for r in rung1)
    assert (equal, len(rung1)) == (89, 328)


# --------------------------------------------------------------------------- exclusions


def test_no_dev_query_is_undecidable(dose_dev, isolated_dev, corpus):
    """Zero, or the sprint stops for an amendment (design, work item 1)."""
    queries = dose_dev + isolated_dev
    texts = set(corpus.values())
    lowered = {t.lower() for t in texts}
    assert sum(r["text"] in texts for r in queries) == 0
    assert sum(r["text"].lower() in lowered for r in queries) == 0
    golds_by_text = collections.defaultdict(set)
    for r in queries:
        golds_by_text[r["text"]].add(r["gold_item_key"])
    assert sum(len(g) > 1 for g in golds_by_text.values()) == 0


def _strings(node) -> set[str]:
    if isinstance(node, str):
        return {node}
    if isinstance(node, dict):
        return set().union(*(_strings(v) for v in node.values())) if node else set()
    if isinstance(node, list):
        return set().union(*(_strings(v) for v in node)) if node else set()
    return set()


def test_no_ladder_gold_is_a_duplicate_texto_leaf(dose, isolated):
    flagged = _strings(json.loads(DUPLICATES.read_text(encoding="utf-8")))
    assert len(flagged) > 0
    assert not {r["gold_item_key"] for r in dose + isolated} & flagged
