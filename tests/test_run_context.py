"""The resolver is the only thing that turns a config into paths (D-022).

Every test writes its own config into a tmp_path work root, so nothing here depends on
the repository's own 77 configs or on data that may not be built yet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.run_context import load_run_context

BM25_OEB = {
    "collection": "OEB",
    "paths": {"data_dir": "/work/data/processed", "index_root": "/work/index"},
    "inputs": {
        "short_feats": "{data_dir}/{collection}_short_feats.parquet",
        "long_feats": "{data_dir}/{collection}_long_feats.parquet",
        "features_meta": "{data_dir}/{collection}_features_meta.json",
    },
    "method": {
        "family": "bm25",
        "name": "bm25_unigram_params__k1-0.60__b-0.35",
        "impl": "bm25_unigram_params",
        "save_as": "bm25_unigram_params__k1-0.60__b-0.35",
        "params": {"k1": 0.6, "b": 0.35},
    },
    "retriever": {"module": "src.retrievers.bm25_unigram_params", "entrypoint": "load"},
}


def write_config(work_root: Path, cfg: dict, name: str = "cfg.yaml") -> Path:
    """Write a config and the input files it names, so resolution has something to find."""
    (work_root / "configs").mkdir(parents=True, exist_ok=True)
    path = work_root / "configs" / name
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def test_index_dir_is_keyed_by_collection_and_method(tmp_path):
    cfg_path = write_config(tmp_path, BM25_OEB)

    ctx = load_run_context(cfg_path, queryset="resumen", work_root=tmp_path, require_inputs=False)

    assert ctx.index_dir == tmp_path / "index" / "OEB" / "bm25_unigram_params__k1-0.60__b-0.35"


def test_index_dir_does_not_carry_the_query_set(tmp_path):
    """An index is built from the corpus; the query set only decides what is asked of it."""
    cfg_path = write_config(tmp_path, BM25_OEB)

    resumen = load_run_context(cfg_path, queryset="resumen", work_root=tmp_path, require_inputs=False)
    stacked = load_run_context(cfg_path, queryset="stacked_texto", work_root=tmp_path, require_inputs=False)

    assert resumen.index_dir == stacked.index_dir


def test_run_dir_is_keyed_by_collection_query_set_and_method(tmp_path):
    cfg_path = write_config(tmp_path, BM25_OEB)

    ctx = load_run_context(cfg_path, queryset="single_texto", work_root=tmp_path, require_inputs=False)

    assert ctx.run_dir == (
        tmp_path / "runs" / "OEB" / "single_texto" / "bm25_unigram_params__k1-0.60__b-0.35"
    )


def test_unknown_query_set_is_rejected(tmp_path):
    cfg_path = write_config(tmp_path, BM25_OEB)

    with pytest.raises(ValueError, match="texto_single"):
        load_run_context(cfg_path, queryset="texto_single", work_root=tmp_path, require_inputs=False)


def test_resumen_queries_come_from_short_feats(tmp_path):
    """The identity of the OEB fixture depends on this: resumen must read what it reads today."""
    cfg_path = write_config(tmp_path, BM25_OEB)

    ctx = load_run_context(cfg_path, queryset="resumen", work_root=tmp_path, require_inputs=False)

    assert ctx.query_path == tmp_path / "data" / "processed" / "OEB_short_feats.parquet"


def test_texto_queries_come_from_long_feats(tmp_path):
    """The identity condition asks the corpus about itself: query text == document text."""
    cfg_path = write_config(tmp_path, BM25_OEB)

    ctx = load_run_context(cfg_path, queryset="texto", work_root=tmp_path, require_inputs=False)

    assert ctx.query_path == tmp_path / "data" / "processed" / "OEB_long_feats.parquet"


def test_synthetic_query_sets_have_their_own_feature_table(tmp_path):
    cfg = dict(BM25_OEB, collection="OE")
    cfg_path = write_config(tmp_path, cfg)

    ctx = load_run_context(cfg_path, queryset="single_texto", work_root=tmp_path, require_inputs=False)

    assert ctx.query_path == tmp_path / "data" / "processed" / "OE_single_texto_feats.parquet"


def test_corpus_is_always_the_long_feature_table(tmp_path):
    """Whatever is asked, it is asked of the full corpus (D-023)."""
    cfg_path = write_config(tmp_path, BM25_OEB)

    ctx = load_run_context(cfg_path, queryset="stacked_texto", work_root=tmp_path, require_inputs=False)

    assert ctx.corpus_path == tmp_path / "data" / "processed" / "OEB_long_feats.parquet"


# --- the three input shapes the 77 configs actually use ------------------------------

DENSE_OE = {
    "collection": "OE",
    "paths": {"data_dir": "/work/data/processed", "index_root": "/work/index"},
    "inputs": {
        "short_text_path": "{data_dir}/{collection}_resumen.json",
        "long_text_path": "{data_dir}/{collection}_texto.json",
    },
    "method": {"family": "dense", "save_as": "dense_e5", "params": {}},
    "retriever": {"module": "src.retrievers.dense_e5", "entrypoint": "load"},
}

RRF_OE = {
    "collection": "OE",
    "paths": {"data_dir": "/work/data/processed", "index_root": "/work/index"},
    "inputs": {
        "short_text_path": "{data_dir}/{collection}_short_norm.parquet",
        "long_text_path": "{data_dir}/{collection}_long_norm.parquet",
    },
    "method": {"family": "hybrid", "save_as": "rrf__bm25_char_e5", "params": {}},
    "retriever": {"module": "src.retrievers.rrf", "entrypoint": "load"},
}


def test_text_path_configs_resolve_their_corpus(tmp_path):
    """The five neural configs read the raw JSON, not the feature parquets."""
    cfg_path = write_config(tmp_path, DENSE_OE)

    ctx = load_run_context(cfg_path, queryset="resumen", work_root=tmp_path, require_inputs=False)

    assert ctx.corpus_path == tmp_path / "data" / "processed" / "OE_texto.json"
    assert ctx.query_path == tmp_path / "data" / "processed" / "OE_resumen.json"


def test_text_path_configs_get_the_synthetic_set_in_their_own_format(tmp_path):
    """OE_single_texto.json is the upstream file itself — the rule lands on what exists."""
    cfg_path = write_config(tmp_path, DENSE_OE)

    ctx = load_run_context(cfg_path, queryset="single_texto", work_root=tmp_path, require_inputs=False)

    assert ctx.query_path == tmp_path / "data" / "processed" / "OE_single_texto.json"


def test_norm_parquet_configs_keep_their_own_suffix(tmp_path):
    cfg_path = write_config(tmp_path, RRF_OE)

    ctx = load_run_context(cfg_path, queryset="stacked_texto", work_root=tmp_path, require_inputs=False)

    assert ctx.query_path == tmp_path / "data" / "processed" / "OE_stacked_texto_norm.parquet"


# --- what must fail loud -------------------------------------------------------------


def test_config_without_a_collection_is_rejected(tmp_path):
    cfg = {k: v for k, v in BM25_OEB.items() if k != "collection"}
    cfg_path = write_config(tmp_path, cfg)

    with pytest.raises(KeyError, match="collection"):
        load_run_context(cfg_path, queryset="resumen", work_root=tmp_path, require_inputs=False)


def test_config_without_a_retriever_module_is_rejected(tmp_path):
    """72 of 77 configs lacked this block until S0. Declaring is not optional (D-016)."""
    cfg = {k: v for k, v in BM25_OEB.items() if k != "retriever"}
    cfg_path = write_config(tmp_path, cfg)

    with pytest.raises(KeyError, match="retriever.module"):
        load_run_context(cfg_path, queryset="resumen", work_root=tmp_path, require_inputs=False)


def test_missing_input_file_is_named(tmp_path):
    cfg_path = write_config(tmp_path, BM25_OEB)

    with pytest.raises(FileNotFoundError, match="OEB_short_feats.parquet"):
        load_run_context(cfg_path, queryset="resumen", work_root=tmp_path)


def test_inputs_present_on_disk_resolve(tmp_path):
    cfg_path = write_config(tmp_path, BM25_OEB)
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    for name in ("OEB_short_feats.parquet", "OEB_long_feats.parquet", "OEB_features_meta.json"):
        (processed / name).write_bytes(b"")

    ctx = load_run_context(cfg_path, queryset="resumen", work_root=tmp_path)

    assert ctx.query_path.exists()


# --- the retriever comes from the config, not from the filename ----------------------


def test_retriever_module_is_importable_as_the_notebooks_import_it(tmp_path):
    """Configs say `src.retrievers.x`; /work/src is what sits on sys.path, so `retrievers.x`
    is the importable name. The resolver hands over a name that import_module accepts."""
    cfg_path = write_config(tmp_path, BM25_OEB)

    ctx = load_run_context(cfg_path, queryset="resumen", work_root=tmp_path, require_inputs=False)

    assert ctx.retriever_module == "retrievers.bm25_unigram_params"


def test_retriever_module_survives_a_renamed_config(tmp_path):
    """The old harness derived the module from the filename, so renaming a config silently
    changed which code ran (S0 finding 1). It must not."""
    cfg_path = write_config(tmp_path, BM25_OEB, name="something_else_entirely.yaml")

    ctx = load_run_context(cfg_path, queryset="resumen", work_root=tmp_path, require_inputs=False)

    assert ctx.retriever_module == "retrievers.bm25_unigram_params"
