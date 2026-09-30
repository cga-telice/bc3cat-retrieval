"""S6 work item 1: the wider L2 query set and the SINGLE modifications sidecar, asserted before any run.

Two intakes. `single_l2_texto` (D-043) is registered as a query set and its tables derived along
`single_texto`'s path (`build_s6_query_tables.py`, which proves that path before writing). The SINGLE
sidecar (`RESEARCH_PLAN.md` §5) is taken in as the cross-check of S3's pantry-artefact detector (S6
design, "D-004 sensitivity").

Text is read on dev only (operating rule 2): test queries are checked by key and metadata alone.
`data/processed` is git-ignored, so every test skips in a checkout that lacks it.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from utils.build_manifest import INTAKE_PREFIXES
from utils.pantry_flags import load_sidecar, sidecar_doubling, sidecar_topo, text_flags
from utils.provenance import sha256_file
from utils.run_context import QUERY_SETS, data_paths
from utils.splits import load_split

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

L2_JSON = PROCESSED / "OE_single_l2_texto.json"
L2_SIDECAR = PROCESSED / "OE_single_l2_modifications.jsonl"
SINGLE_JSON = PROCESSED / "OE_single_texto.json"
SINGLE_SIDECAR = PROCESSED / "OE_single_modifications.jsonl"
CORPUS = PROCESSED / "OE_texto.json"
DUPLICATES = PROCESSED / "OE_duplicate_texto_groups.json"
L2_NORM = PROCESSED / "OE_single_l2_texto_norm.parquet"
L2_FEATS = PROCESSED / "OE_single_l2_texto_feats.parquet"

#: The one dev query excluded at item level under S4 design A2 (DATASET_DEFECTS P7).
P7_DEV = "OEC140baa_syn_74d5dd2c9da3"
L2_TYPES = {"paraphrase", "compression", "expansion"}

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in [L2_JSON, L2_SIDECAR, SINGLE_JSON, SINGLE_SIDECAR, CORPUS, L2_NORM, L2_FEATS]),
    reason="data/processed is git-ignored; run build_s6_query_tables.py and take in the sidecar",
)


def records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def l2() -> list[dict]:
    return records(L2_JSON)


@pytest.fixture(scope="module")
def single() -> list[dict]:
    return records(SINGLE_JSON)


@pytest.fixture(scope="module")
def corpus() -> dict[str, dict]:
    return {r["item_key"]: r for r in records(CORPUS)}


@pytest.fixture(scope="module")
def dev() -> frozenset[str]:
    return load_split("dev")


# --------------------------------------------------------------------------- registration


def test_single_l2_is_a_registered_query_set():
    assert "single_l2_texto" in QUERY_SETS
    paths = data_paths("OE", work_root=REPO)
    assert paths.query_json["single_l2_texto"] == L2_JSON
    assert paths.query_feats["single_l2_texto"] == L2_FEATS


@pytest.mark.parametrize("path", [L2_JSON, L2_SIDECAR, SINGLE_SIDECAR])
def test_delivered_digests_match_the_record(path):
    assert sha256_file(path).startswith(INTAKE_PREFIXES[path.name])


@pytest.mark.parametrize("table", [L2_NORM, L2_FEATS])
def test_derived_tables_hold_the_query_set_in_order(l2, table):
    frame = pd.read_parquet(table)
    assert list(frame["item_key"]) == [r["item_key"] for r in l2]
    assert list(frame["gold_item_key"]) == [r["gold_item_key"] for r in l2]


# --------------------------------------------------------------------------- the L2 queries


def test_every_l2_gold_resolves_to_a_leaf_of_its_concept(l2, corpus):
    for r in l2:
        leaf = corpus.get(r["gold_item_key"])
        assert leaf is not None, r["item_key"]
        assert leaf["parent_key"] == r["parent_key"], r["item_key"]


def test_every_l2_query_is_a_single_l2_modification(l2):
    assert {r["modification_count"] for r in l2} == {1}
    assert {t for r in l2 for t in r["modification_types"]} == L2_TYPES


def test_dev_breadth_is_the_delivered_9_9_8(l2, dev):
    concepts: dict[str, set] = {t: set() for t in L2_TYPES}
    queries = Counter()
    for r in l2:
        if r["parent_key"] in dev:
            t = r["modification_types"][0]
            concepts[t].add(r["parent_key"])
            queries[t] += 1
    assert {t: len(c) for t, c in concepts.items()} == {"paraphrase": 9, "expansion": 9, "compression": 8}
    assert dict(queries) == {"paraphrase": 179, "expansion": 180, "compression": 159}


def test_no_dev_l2_gold_is_a_duplicate_texto_leaf(l2, dev):
    sidecar = records(DUPLICATES)
    members = {k for keys in sidecar["groups"].values() for k in keys}
    assert len(members) == sidecar["n_leaves"]
    assert not [r["item_key"] for r in l2 if r["parent_key"] in dev and r["gold_item_key"] in members]


def test_no_l2_key_is_a_p7_or_p8_key(l2):
    keys = {r["item_key"] for r in l2}
    listed = {P7_DEV}
    for name in ("OE_P7_test_exclusion.json", "OE_P8_test_exclusion.json"):
        listed |= set(records(PROCESSED / name)["item_keys"])
    assert not keys & listed


def test_l2_keys_are_disjoint_from_single(l2, single):
    assert not {r["item_key"] for r in l2} & {r["item_key"] for r in single}


# --------------------------------------------------------------------------- the sidecars


@pytest.mark.parametrize("which", ["single", "l2"])
def test_each_sidecar_row_names_its_querys_type(which, single, l2):
    queries, path = (single, SINGLE_SIDECAR) if which == "single" else (l2, L2_SIDECAR)
    side = load_sidecar(path)
    assert set(side) == {r["item_key"] for r in queries}
    for r in queries:
        applied = [m["type"] for m in side[r["item_key"]] if m["status"] == "applied"]
        assert applied == list(r["modification_types"]), r["item_key"]


def _flags(queries, sidecar, corpus, dev):
    side = load_sidecar(sidecar)
    out = []
    for r in queries:
        if r["parent_key"] not in dev:
            continue
        mods = side[r["item_key"]]
        t = text_flags(r["text"], corpus[r["gold_item_key"]]["text"])
        out.append((mods[0]["layer"], t, sidecar_doubling(r["text"], mods), sidecar_topo(mods)))
    return out


def test_detector_and_sidecar_agree_on_every_decidable_single_dev_query(single, corpus, dev):
    flags = _flags(single, SINGLE_SIDECAR, corpus, dev)
    assert len(flags) == 2206
    decidable = [(t["doubled"], sd) for layer, t, sd, _ in flags if layer != "template"]
    assert all(sd is not None for _, sd in decidable)
    assert all(td == sd for td, sd in decidable)
    assert sum(td for td, _ in decidable) == 185
    # L3 rewrites are templates: the sidecar cannot decide them, and says so rather than guessing.
    assert all(sd is None for layer, _, sd, _ in flags if layer == "template")
    assert all(t["topo"] == st for _, t, _, st in flags)
    assert sum(st for *_, st in flags) == 19


def test_detector_and_sidecar_agree_on_every_l2_dev_query(l2, corpus, dev):
    flags = _flags(l2, L2_SIDECAR, corpus, dev)
    assert len(flags) == 518
    assert all(sd is not None and sd == t["doubled"] for _, t, sd, _ in flags)
    assert not any(t["doubled"] for _, t, _, _ in flags)
    assert all(t["topo"] == st for _, t, _, st in flags)
    assert sum(st for *_, st in flags) == 17
