"""S9 work item 1 (a, b): the derived query sets and D-040, asserted before any run.

- The 17 S9 names resolve through `run_context`, for a lexical, a neural and a hybrid config, and land in
  `runs/OE/{queryset}/…` like any other set.
- `texto_u` / `resumen_u` are U — 2,691 dev leaves, the golds of the dev single, L2 and stacked queries —
  as the corpus's own records with `gold_item_key` added and nothing else changed. Their tables are the
  stored corpus rows of those leaves (proven by `build_s9_query_tables.py`, re-checked here on the keys).
- A transformed set may differ from its base in `text` only; anything else is refused.
- D-040 is in the harness, and its counts are the ones D-040 recorded ad hoc: 9,346 coded, 9,348 under
  coded or decoded, 200 of them also D-033, 9,924 excluded, 25,498 scored on dev.

`data/processed` is git-ignored, so the data tests skip in a checkout that lacks it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from utils import exclusions
from utils.build_s9_query_tables import same_but_text
from utils.run_context import QUERY_SETS, S9_QUERY_SETS, load_run_context
from utils.splits import load_split

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"
CONFIGS = {
    "lexical": REPO / "configs" / "bm25_unigram__k1-0.60__b-0.35__OE.yaml",
    "neural": REPO / "configs" / "dense_e5__OE.yaml",
    "hybrid": REPO / "configs" / "bge_m3_dense__OE.yaml",
}
needs_data = pytest.mark.skipif(not (PROCESSED / "OE_texto_u.json").exists(), reason="data/processed absent")


def read(name: str) -> list[dict]:
    return json.loads((PROCESSED / name).read_text(encoding="utf-8"))


def test_seventeen_s9_sets_are_registered_and_earlier_ones_kept():
    assert len(S9_QUERY_SETS) == 17
    assert set(S9_QUERY_SETS) <= set(QUERY_SETS)
    for earlier in ("texto", "resumen", "single_texto", "stacked_texto", "resumen_decoded", "dose_texto"):
        assert earlier in QUERY_SETS
    assert len(set(QUERY_SETS)) == len(QUERY_SETS)


@pytest.mark.parametrize("queryset", S9_QUERY_SETS)
@pytest.mark.parametrize("family", sorted(CONFIGS))
def test_every_s9_set_resolves(queryset, family):
    ctx = load_run_context(CONFIGS[family], queryset=queryset, work_root=REPO, require_inputs=False)
    assert ctx.run_dir == REPO / "runs" / "OE" / queryset / ctx.method
    assert ctx.query_path.name in {f"OE_{queryset}{suffix}" for suffix in ("_feats.parquet", "_norm.parquet", ".json")}


@needs_data
def test_u_is_the_dev_golds_of_the_three_synthetic_sets():
    dev = load_split("dev")
    u = set()
    for name in ("OE_single_texto.json", "OE_single_l2_texto.json", "OE_stacked_texto.json"):
        u |= {r["gold_item_key"] for r in read(name) if r["parent_key"] in dev}
    assert len(u) == 2_691
    for base, source in (("texto_u", "OE_texto.json"), ("resumen_u", "OE_resumen.json")):
        records = read(f"OE_{base}.json")
        assert [r["gold_item_key"] for r in records] == [r["item_key"] for r in records]
        assert {r["item_key"] for r in records} == u
        assert all(r["parent_key"] in dev for r in records)
        corpus = {r["item_key"]: r for r in read(source)}
        for r in records:
            assert {k: v for k, v in r.items() if k != "gold_item_key"} == corpus[r["item_key"]]


@needs_data
@pytest.mark.parametrize("base,side", [("texto_u", "long"), ("resumen_u", "short")])
def test_base_tables_are_the_stored_corpus_rows(base, side):
    feats = pd.read_parquet(PROCESSED / f"OE_{base}_feats.parquet")
    stored = pd.read_parquet(PROCESSED / f"OE_{side}_feats.parquet")
    stored = stored[stored["item_key"].isin(set(feats["item_key"]))].reset_index(drop=True)
    assert len(feats) == len(stored) == 2_691
    for column in stored.columns:
        assert feats[column].astype(str).tolist() == stored[column].astype(str).tolist(), column


def test_a_transformed_set_may_change_text_only(tmp_path):
    base = [{"item_key": "a", "gold_item_key": "a", "text": "x", "parameters": "{}"}]
    good = [{**base[0], "text": "y"}]
    bad = [{**base[0], "text": "y", "parameters": "{'A': 1}"}]
    extra = [{**base[0], "text": "y", "note": "z"}]
    paths = {}
    for name, records in (("base", base), ("good", good), ("bad", bad), ("extra", extra)):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(records), encoding="utf-8")
    same_but_text(paths["base"], paths["good"])
    for name in ("bad", "extra"):
        with pytest.raises(SystemExit):
            same_but_text(paths["base"], paths[name])


@needs_data
def test_d040_counts_regenerate():
    dev = load_split("dev")
    leaves = {r["item_key"] for r in read("OE_resumen.json") if r["parent_key"] in dev}
    coded = {r["item_key"]: r["text"] for r in read("OE_resumen.json") if r["parent_key"] in dev}
    assert sum(len(g) for g in exclusions.identical_groups(coded)) == 9_346
    identical = exclusions.resumen_identical(frozenset(dev))
    assert len(identical) == 9_348
    assert len(identical & exclusions.duplicate_texto()) == 200
    excluded = exclusions.item_excluded("resumen", leaves, dev)
    assert len(excluded) == 9_924
    assert len(leaves) - len(excluded) == 25_498


@needs_data
def test_d040_applies_to_the_resumen_family_only():
    dev = load_split("dev")
    golds = [r["gold_item_key"] for r in read("OE_resumen_u.json")]
    assert len(exclusions.item_excluded("resumen_u", golds, dev)) == 758
    assert len(exclusions.item_excluded("resumen_u__rewrite", golds, dev)) == 758
    assert len(exclusions.item_excluded("texto_u", golds, dev)) == 55
    assert exclusions.item_excluded("texto_u", golds, dev) <= exclusions.item_excluded("resumen_u", golds, dev)


def test_text_collisions_count_only_cross_gold_identity():
    records = [
        {"gold_item_key": "a", "text": "same  text"},
        {"gold_item_key": "b", "text": "same text"},
        {"gold_item_key": "c", "text": "other"},
        {"gold_item_key": "c", "text": "other"},
    ]
    assert exclusions.text_collisions(records) == 2
