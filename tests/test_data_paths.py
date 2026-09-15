"""Where the data phase reads and writes (D-022).

`run_context` answers that for a method, from its config. `data.ipynb` runs before any
method exists, so it needs the same answer keyed on the collection alone — otherwise it goes
back to building paths itself, which is the thing D-022 forbids.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.run_context import data_paths

REPO = Path(__file__).resolve().parents[1]


def make_collection(root: Path, collection: str, querysets: tuple[str, ...] = ()) -> Path:
    processed = root / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    for name in ("resumen", "texto", *querysets):
        (processed / f"{collection}_{name}.json").write_text("[]", encoding="utf-8")
    return processed


def test_the_corpus_pair_is_resolved(tmp_path):
    processed = make_collection(tmp_path, "OEB")

    paths = data_paths("OEB", work_root=tmp_path)

    assert paths.short_json == processed / "OEB_resumen.json"
    assert paths.long_json == processed / "OEB_texto.json"


def test_the_normalised_outputs_keep_the_names_the_harness_already_uses(tmp_path):
    make_collection(tmp_path, "OEB")

    paths = data_paths("OEB", work_root=tmp_path)

    assert paths.short_norm.name == "OEB_short_norm.parquet"
    assert paths.long_norm.name == "OEB_long_norm.parquet"


def test_a_collection_without_synthetic_sets_offers_none(tmp_path):
    """OEB has no synthetic queries, and asking for them must not invent a path."""
    make_collection(tmp_path, "OEB")

    paths = data_paths("OEB", work_root=tmp_path)

    assert paths.query_json == {}


def test_synthetic_sets_are_discovered_when_present(tmp_path):
    make_collection(tmp_path, "OE", querysets=("single_texto", "stacked_texto"))

    paths = data_paths("OE", work_root=tmp_path)

    assert set(paths.query_json) == {"single_texto", "stacked_texto"}
    assert paths.query_norm["single_texto"].name == "OE_single_texto_norm.parquet"


def test_a_collection_with_no_corpus_is_an_error(tmp_path):
    (tmp_path / "data" / "processed").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="ZZ_texto.json"):
        data_paths("ZZ", work_root=tmp_path)


def test_the_real_collections_resolve():
    """Against the repository, which has both OEB and OE in data/processed."""
    if not (REPO / "data" / "processed" / "OE_texto.json").exists():
        pytest.skip("data/processed is git-ignored and absent in this checkout")

    oe = data_paths("OE", work_root=REPO)
    oeb = data_paths("OEB", work_root=REPO)

    assert set(oe.query_json) == {"single_texto", "stacked_texto"}
    assert oeb.query_json == {}


def test_feature_outputs_are_resolved(tmp_path):
    make_collection(tmp_path, "OE", querysets=("single_texto", "stacked_texto"))

    paths = data_paths("OE", work_root=tmp_path)

    assert paths.short_feats.name == "OE_short_feats.parquet"
    assert paths.long_feats.name == "OE_long_feats.parquet"
    assert paths.features_meta.name == "OE_features_meta.json"
    assert paths.query_feats["stacked_texto"].name == "OE_stacked_texto_feats.parquet"


def test_the_feature_paths_are_the_ones_the_configs_declare():
    """A config's inputs.short_feats and this must be the same file, or the index would be
    built from one table and queried with another."""
    if not (REPO / "data" / "processed" / "OE_texto.json").exists():
        pytest.skip("data/processed is git-ignored and absent in this checkout")

    from utils.run_context import load_run_context

    ctx = load_run_context(
        REPO / "configs" / "bm25_unigram_params__k1-0.60__b-0.35__OE.yaml",
        queryset="single_texto",
        work_root=REPO,
        require_inputs=False,
    )
    paths = data_paths("OE", work_root=REPO)

    assert ctx.inputs["short_feats"] == paths.short_feats
    assert ctx.inputs["long_feats"] == paths.long_feats
    assert ctx.inputs["features_meta"] == paths.features_meta
    assert ctx.query_path == paths.query_feats["single_texto"]
