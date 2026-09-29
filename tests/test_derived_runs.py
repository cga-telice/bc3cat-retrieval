"""Fusion and reranking runs computed from other runs (S4 work items 2–3).

Checked before any S4 run: the arithmetic on hand-computed cases, the fail-loud paths that
keep components paired by row, the shape a derived run must have for `metrics.ipynb`, and
that `check_run_inputs.py` resolves a derived run through its components.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from utils.check_run_inputs import check_components
from utils.fuse_rrf import rrf_fuse
from utils.fuse_rrf import run as run_rrf
from utils.provenance import assert_clean_stamp
from utils.rerank_ce import blend, minmax
from utils.rerank_ce import run as run_ce
from utils.run_context import load_run_context
from utils.splits import load_split

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- arithmetic

def test_rrf_matches_a_hand_computed_fusion():
    fused = rrf_fuse([["a", "b", "c"], ["b", "d", "a"]], k=60)

    assert [key for key, _ in fused] == ["b", "a", "d", "c"]
    scores = dict(fused)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 63)
    assert scores["d"] == pytest.approx(1 / 62)
    assert scores["c"] == pytest.approx(1 / 63)


def test_rrf_breaks_an_exact_tie_by_the_first_component():
    # Both score exactly 1/61; the design's rule puts the first component's document first.
    assert [k for k, _ in rrf_fuse([["x"], ["y"]], k=60)] == ["x", "y"]
    assert [k for k, _ in rrf_fuse([["y"], ["x"]], k=60)] == ["y", "x"]


def test_rrf_respects_depth_and_k_final():
    fused = rrf_fuse([list("abcdef"), list("fedcba")], k=60, depth=2, k_final=3)
    assert {k for k, _ in fused} <= set("abef")
    assert len(fused) == 3


def test_rrf_refuses_a_list_with_a_repeated_document():
    with pytest.raises(ValueError, match="twice"):
        rrf_fuse([["a", "a"], ["b"]])


def test_minmax_maps_a_zero_range_to_zero():
    assert minmax([3.0, 3.0, 3.0]).tolist() == [0.0, 0.0, 0.0]
    assert minmax([1.0, 3.0, 2.0]).tolist() == [0.0, 1.0, 0.5]


def test_blend_matches_a_hand_computed_case():
    # base min-max: [1, 0.5, 0]; CE min-max: [0, 1, 0.5]; λ = 0.6
    out = dict(blend(["a", "b", "c"], [10.0, 5.0, 0.0], [-2.0, 2.0, 0.0], 0.6))
    assert out["a"] == pytest.approx(0.4)
    assert out["b"] == pytest.approx(0.6 + 0.2)
    assert out["c"] == pytest.approx(0.3)


def test_blend_on_a_constant_score_query_keeps_base_order():
    # Both normalise to zero: every candidate ties, and ties keep base rank.
    out = blend(["a", "b", "c"], [5.0, 5.0, 5.0], [1.0, 1.0, 1.0], 0.6)
    assert [k for k, _ in out] == ["a", "b", "c"]
    assert all(s == 0.0 for _, s in out)


def test_the_dirty_tree_refusal_is_in_committed_code():
    with pytest.raises(RuntimeError, match="dirty"):
        assert_clean_stamp({"run_id": "r", "code_dirty": True, "code_dirty_paths": ["src/x.py"]})
    assert_clean_stamp({"run_id": "r", "code_dirty": False})


# ---------------------------------------------------------------- a small world

DEV = sorted(load_split("dev"))[:2]


def _write_run(root: Path, queryset: str, method: str, rows, *, split="dev", dirty=False):
    run_dir = root / "runs" / "OE" / queryset / method
    run_dir.mkdir(parents=True)
    with gzip.open(run_dir / "results_top100.jsonl.gz", "wt", encoding="utf-8") as gz:
        for i, (qkey, gkey, parent, ranked) in enumerate(rows):
            gz.write(json.dumps({
                "query_id": f"q_{i:06d}", "query_item_key": qkey, "gold_item_key": gkey,
                "gold_parent_key": parent, "query_text": "",
                "candidates": [
                    {"rank": r + 1, "doc_id": r, "index_item_key": k, "score": float(s)}
                    for r, (k, s) in enumerate(ranked)
                ],
            }) + "\n")
    meta = {
        "run_id": f"OE/{queryset}/{method}", "config": f"/work/configs/{method}.yaml",
        "config_sha256": "c" * 64, "code_commit": "a" * 40, "code_dirty": dirty,
        "query_set_sha256": "q" * 64, "corpus_sha256": "d" * 64, "split": split,
        "queryset": queryset, "queries": len(rows),
    }
    (run_dir / "run_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return run_dir


@pytest.fixture
def world(tmp_path):
    """Two dev concepts, six leaves, two single queries, two component runs."""
    c1, c2 = DEV
    docs = pd.DataFrame({
        "item_key": ["A1", "A2", "A3", "B1", "B2", "B3"],
        "parent_key": [c1] * 3 + [c2] * 3,
        "text": ["alpha one", "alpha two", "alpha three", "beta one", "beta two", "beta three"],
    })
    data = tmp_path / "data" / "processed"
    data.mkdir(parents=True)
    docs.to_parquet(data / "OE_long_feats.parquet", index=False)
    docs.to_parquet(data / "OE_short_feats.parquet", index=False)
    queries = pd.DataFrame({
        "item_key": ["A2_syn_1", "B1_syn_1"], "gold_item_key": ["A2", "B1"],
        "parent_key": [c1, c2], "text": ["alpha 2", "beta 1"],
    })
    queries.to_parquet(data / "OE_single_texto_feats.parquet", index=False)

    rows_x = [("A2_syn_1", "A2", c1, [("A1", 9), ("A2", 8), ("B1", 1)]),
              ("B1_syn_1", "B1", c2, [("B2", 5), ("B1", 4), ("B3", 3)])]
    rows_y = [("A2_syn_1", "A2", c1, [("A2", 0.9), ("A3", 0.5), ("A1", 0.1)]),
              ("B1_syn_1", "B1", c2, [("B3", 0.8), ("B1", 0.7), ("A1", 0.2)])]
    _write_run(tmp_path, "single_texto", "X", rows_x)
    _write_run(tmp_path, "single_texto", "Y", rows_y)

    configs = tmp_path / "configs"
    configs.mkdir()
    base = {
        "collection": "OE", "paths": {"data_dir": "/work/data/processed"},
        "inputs": {"short_feats": "{data_dir}/{collection}_short_feats.parquet",
                   "long_feats": "{data_dir}/{collection}_long_feats.parquet"},
    }
    rrf = {**base, "method": {"family": "rrf", "save_as": "rrf__X+Y", "params": {
        "k_rrf": 60, "weights": [1.0, 1.0], "depth": 100, "k_final": 100}},
        "derived": {"components": ["X", "Y"]},
        "retriever": {"module": "src.utils.fuse_rrf", "entrypoint": "run"}}
    (configs / "rrf.yaml").write_text(json.dumps(rrf), encoding="utf-8")
    ce = {**base, "method": {"family": "ce_blend", "save_as": "ce__X", "params": {
        "model": "fake/model", "revision": "0" * 40, "max_length": 320, "depth": 100,
        "lambda": 0.6, "batch_size": 8, "precision": "fp32"}},
        "derived": {"components": ["X"]},
        "retriever": {"module": "src.utils.rerank_ce", "entrypoint": "run"}}
    (configs / "ce.yaml").write_text(json.dumps(ce), encoding="utf-8")
    return tmp_path


def _records(run_dir: Path):
    with gzip.open(run_dir / "results_top100.jsonl.gz", "rt", encoding="utf-8") as gz:
        return [json.loads(line) for line in gz if line.strip()]


def test_an_rrf_run_has_the_shape_metrics_reads(world):
    out = run_rrf(world / "configs" / "rrf.yaml", "single_texto", work_root=world, allow_dirty=True)
    records = _records(out)
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))

    assert [r["query_item_key"] for r in records] == ["A2_syn_1", "B1_syn_1"]
    assert [r["gold_item_key"] for r in records] == ["A2", "B1"]
    # A2: rank 2 in X, rank 1 in Y → 1/62 + 1/61, above A1's 1/61 + 1/63.
    assert records[0]["candidates"][0]["index_item_key"] == "A2"
    # doc_id is the corpus row, whatever the components said.
    assert records[0]["candidates"][0]["doc_id"] == 1
    for key in ("run_id", "config_sha256", "code_commit", "query_set_sha256", "corpus_sha256",
                "collection", "queryset", "split", "query_path", "index_dir", "gold_column",
                "queries", "queries_before_split"):
        assert key in meta, key
    assert meta["derived"] is True
    assert [c["run_id"] for c in meta["components"]] == ["OE/single_texto/X", "OE/single_texto/Y"]
    assert meta["queries"] == 2


def test_components_out_of_row_order_are_refused(world):
    y = world / "runs" / "OE" / "single_texto" / "Y"
    lines = gzip.open(y / "results_top100.jsonl.gz", "rt", encoding="utf-8").read().splitlines()
    with gzip.open(y / "results_top100.jsonl.gz", "wt", encoding="utf-8") as gz:
        gz.write("\n".join(reversed(lines)) + "\n")

    with pytest.raises(ValueError, match="pair by row"):
        run_rrf(world / "configs" / "rrf.yaml", "single_texto", work_root=world, allow_dirty=True)


def test_a_component_on_another_split_is_refused(world):
    meta_path = world / "runs" / "OE" / "single_texto" / "Y" / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_path.write_text(json.dumps({**meta, "split": "all"}), encoding="utf-8")

    with pytest.raises(ValueError, match="split"):
        run_rrf(world / "configs" / "rrf.yaml", "single_texto", work_root=world, allow_dirty=True)


def test_a_dirty_component_is_refused(world):
    meta_path = world / "runs" / "OE" / "single_texto" / "Y" / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_path.write_text(json.dumps({**meta, "code_dirty": True}), encoding="utf-8")

    with pytest.raises(ValueError, match="dirty"):
        run_rrf(world / "configs" / "rrf.yaml", "single_texto", work_root=world, allow_dirty=True)


def test_a_missing_component_is_refused(world):
    import shutil
    shutil.rmtree(world / "runs" / "OE" / "single_texto" / "Y")
    with pytest.raises(FileNotFoundError):
        run_rrf(world / "configs" / "rrf.yaml", "single_texto", work_root=world, allow_dirty=True)


def test_a_ce_run_blends_and_reuses_its_cache(world):
    # A fake CE that prefers documents whose text shares the query's number word.
    word = {"2": "two", "1": "one"}

    def fake(pairs):
        return np.array([1.0 if d.endswith(word[q.split()[-1]]) else 0.0 for q, d in pairs])

    out = run_ce(world / "configs" / "ce.yaml", "single_texto", work_root=world,
                 allow_dirty=True, scorer=fake, stack={"fake": True})
    records = _records(out)
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))

    # Query 1: base X [A1 9, A2 8, B1 1] → ŝ [1, .875, 0]; CE [0, 1, 0] → A2 = .6 + .35 = .95.
    assert records[0]["candidates"][0]["index_item_key"] == "A2"
    assert records[0]["candidates"][0]["score"] == pytest.approx(0.95)
    assert meta["ce_pairs_scored"] == 6
    assert meta["ml_stack"] == {"fake": True}

    def exploding(pairs):
        raise AssertionError("every pair should have come from the cache")

    import shutil
    shutil.rmtree(out)
    again = run_ce(world / "configs" / "ce.yaml", "single_texto", work_root=world,
                   allow_dirty=True, scorer=exploding, stack={"fake": True})
    assert _records(again) == records
    assert json.loads((again / "run_meta.json").read_text(encoding="utf-8"))["ce_pairs_scored"] == 0


def test_check_run_inputs_follows_a_derived_run_to_its_components(world):
    out = run_rrf(world / "configs" / "rrf.yaml", "single_texto", work_root=world, allow_dirty=True)
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    runs_root = world / "runs"

    assert check_components(meta, runs_root) == []

    y_meta = runs_root / "OE" / "single_texto" / "Y" / "run_meta.json"
    changed = {**json.loads(y_meta.read_text(encoding="utf-8")), "code_commit": "b" * 40}
    y_meta.write_text(json.dumps(changed), encoding="utf-8")
    problems = check_components(meta, runs_root)
    assert len(problems) == 1 and "code_commit" in problems[0]


def test_a_derived_run_with_no_components_does_not_resolve():
    assert check_components({"derived": True, "components": []}) == ["derived run lists no components"]
    assert check_components({"run_id": "a retrieval run"}) == []


# ---------------------------------------------------------------- the real configs

DERIVED = {
    "rrf__bm25_unigram+bge_m3_colbert__OE": ["bm25_unigram__k1-0.60__b-0.35__OE", "bge_m3_colbert__OE"],
    "rrf__bm25_unigram_params+bge_m3_colbert__OE": ["bm25_unigram_params__k1-0.60__b-0.35__OE", "bge_m3_colbert__OE"],
    "ce_blend__bm25_unigram__OE": ["bm25_unigram__k1-0.60__b-0.35__OE"],
    "ce_blend__bge_m3_colbert__OE": ["bge_m3_colbert__OE"],
    "ce_blend__rrf__bm25_unigram+bge_m3_colbert__OE": ["rrf__bm25_unigram+bge_m3_colbert__OE"],
}


@pytest.mark.parametrize("name", sorted(DERIVED))
def test_the_derived_configs_carry_the_frozen_design_values(name):
    path = REPO / "configs" / f"{name}.yaml"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    ctx = load_run_context(path, queryset="single_texto", work_root=REPO, require_inputs=False)

    assert ctx.collection == "OE" and ctx.method == name
    assert cfg["derived"]["components"] == DERIVED[name]
    for component in DERIVED[name]:
        assert (REPO / "configs" / f"{component}.yaml").exists(), component
    params = cfg["method"]["params"]
    if cfg["method"]["family"] == "rrf":
        assert (params["k_rrf"], params["weights"], params["depth"]) == (60, [1.0, 1.0], 100)
    else:
        assert params["model"] == "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
        assert len(params["revision"]) == 40
        assert (params["lambda"], params["depth"], params["max_length"]) == (0.6, 100, 320)
        assert params["precision"] == "fp32"
