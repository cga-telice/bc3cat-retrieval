"""S9 work item 3: the IDF guard.

Without `idf_cap_df` both BM25 builders must produce what they produced before (every existing index
and run depends on it). With it, every IDF above the cap is the cap, in the document weights and in the
saved `idf.npy` the retriever reads, and nothing below it moves. The two S9 configs differ from their
parents only in name and the cap.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from index_builders import bm25_unigram, bm25_unigram_params
from index_builders.idf_cap import apply_idf_cap, cap_value

REPO = Path(__file__).resolve().parents[1]

DOCS = ["tubo pvc 110 mm r", "tubo pvc 160 mm", "tubo pe 110 mm", "arqueta 90x81x70 cm", "tubo pvc 110 mm"] * 4


def build(module, params):
    cfg = {"method": {"params": {"k1": 0.6, "b": 0.35, **params}}}
    frame = pd.DataFrame({"t": DOCS})
    artifacts, _, X = module.build(cfg, frame, "t")
    return artifacts, X


@pytest.mark.parametrize("module", [bm25_unigram, bm25_unigram_params])
def test_no_cap_is_the_uncapped_formula(module):
    artifacts, _ = build(module, {})
    df = artifacts["df.npy"]
    n = len(DOCS)
    expected = np.log((n - df + 0.5) / (df + 0.5) + 1.0).astype(np.float32)
    assert np.array_equal(artifacts["idf.npy"], expected)


@pytest.mark.parametrize("module", [bm25_unigram, bm25_unigram_params])
def test_cap_bounds_idf_and_document_weights(module):
    plain, X_plain = build(module, {})
    capped, X_capped = build(module, {"idf_cap_df": 8})
    cap = cap_value(len(DOCS), 8)
    idf_p, idf_c = plain["idf.npy"], capped["idf.npy"]
    assert np.all(idf_c <= np.float32(cap) + 1e-6)
    below = idf_p <= cap
    assert np.array_equal(idf_c[below], idf_p[below])
    assert np.any(~below), "the toy corpus must have a term above the cap, or this test is vacuous"
    # document weight = idf × tf-part, so capped / plain = capped idf / plain idf, column by column
    ratio = sparse.csr_matrix(X_capped).toarray() / np.where(X_plain.toarray() == 0, 1, X_plain.toarray())
    vocab = plain["vocab.json"]
    for term, j in vocab.items():
        col = X_plain.toarray()[:, j] != 0
        assert np.allclose(ratio[col, j], idf_c[j] / idf_p[j], rtol=1e-5), term


def test_cap_rejects_a_bad_value():
    with pytest.raises(ValueError):
        apply_idf_cap(np.ones(3, dtype=np.float32), 10, {"idf_cap_df": 0})
    with pytest.raises(ValueError):
        apply_idf_cap(np.ones(3, dtype=np.float32), 10, {"idf_cap_df": 1.5})


def test_the_design_cap_on_oe():
    # S9 work item 3: the BM25 IDF of a term in 1,200 of OE's 70,242 documents.
    assert cap_value(70_242, 1_200) == pytest.approx(np.log((70_242 - 1_200 + 0.5) / 1_200.5 + 1.0))


@pytest.mark.parametrize("parent", ["bm25_unigram__k1-0.60__b-0.35__OE", "bm25_unigram_params__k1-0.60__b-0.35__OE"])
def test_s9_configs_differ_only_by_name_and_cap(parent):
    child = parent.replace("__OE", "__idfcap-1200__OE")
    a = json.loads((REPO / "configs" / f"{parent}.yaml").read_text(encoding="utf-8"))
    b = json.loads((REPO / "configs" / f"{child}.yaml").read_text(encoding="utf-8"))
    assert b["method"]["params"].pop("idf_cap_df") == 1200
    assert b["method"]["name"] == b["method"]["save_as"] == child
    b["method"]["name"] = b["method"]["save_as"] = parent
    assert a == b
