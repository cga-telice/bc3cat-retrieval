"""Blocked `search_batch` returns what one block returned (S2).

Same claim as tests/test_bm25_batching.py, for the two retrievers S2 adds to the run set: a
query's scores depend on no other query, so splitting the query set changes memory, not
results. Encoders are replaced by deterministic fakes; what is under test is the blocking.
"""

from __future__ import annotations

import numpy as np
import pytest

from retrievers import dense_e5

N_DOCS, DIM, N_QUERIES = 40, 16, 23


def _vec(text: str, dim: int) -> np.ndarray:
    rng = np.random.default_rng(sum(map(ord, text)) * 7919 + len(text))
    return rng.standard_normal(dim).astype(np.float32)


@pytest.fixture()
def e5():
    s = dense_e5.DenseE5Searcher.__new__(dense_e5.DenseE5Searcher)
    rng = np.random.default_rng(0)
    s.X_docs = dense_e5._l2_normalize(rng.standard_normal((N_DOCS, DIM)).astype(np.float32))
    s.external_ids = np.asarray([f"d{i}" for i in range(N_DOCS)], dtype=object)
    s.encode_queries = lambda texts: dense_e5._l2_normalize(np.stack([_vec(t, DIM) for t in texts]))
    return s


QUERIES = [f"consulta numero {i}" for i in range(N_QUERIES)]


@pytest.mark.parametrize("batch_size", [1, 5, 22, 23, 1000])
def test_e5_blocks_equal_one_block(e5, batch_size):
    ref_idx, ref_sc = e5.search_batch(QUERIES, k=10, batch_size=None)
    idx, sc = e5.search_batch(QUERIES, k=10, batch_size=batch_size)
    np.testing.assert_array_equal(idx, ref_idx)
    np.testing.assert_allclose(sc, ref_sc, rtol=0, atol=1e-6)


def test_e5_default_is_blocked_and_rejects_nonsense(e5):
    assert dense_e5.DEFAULT_BATCH_SIZE == 2048
    with pytest.raises(ValueError):
        e5.search_batch(QUERIES, k=5, batch_size=0)


def test_colbert_blocks_equal_one_block(monkeypatch):
    colbert = pytest.importorskip("retrievers.bge_m3_colbert")
    faiss = pytest.importorskip("faiss")

    rng = np.random.default_rng(1)
    doc_mats = [dense_e5._l2_normalize(rng.standard_normal((3 + i % 4, DIM)).astype(np.float32))
                for i in range(N_DOCS)]

    s = colbert.ColBERTSearcher.__new__(colbert.ColBERTSearcher)
    s.d = DIM
    s.doc_ids = np.arange(N_DOCS)
    s._preselect = 15
    s._already_norm = True
    lengths = np.array([m.shape[0] for m in doc_mats])
    s.offsets = np.concatenate([[0], np.cumsum(lengths)]).astype(np.int64)
    s._mm = np.concatenate([m.astype(np.float16).ravel() for m in doc_mats])
    cents = np.stack([m.mean(axis=0) for m in doc_mats]).astype(np.float32)
    faiss.normalize_L2(cents)
    s.faiss = faiss.IndexFlatIP(DIM)
    s.faiss.add(cents)
    s._encode_queries = lambda texts: [
        dense_e5._l2_normalize(np.stack([_vec(t + str(j), DIM) for j in range(4)])) for t in texts
    ]
    monkeypatch.setattr(colbert, "_HAS_TORCH", False)  # CPU MaxSim: deterministic everywhere

    ref_idx, ref_sc = s.search_batch(QUERIES, k=8, batch_size=None)
    for bs in (1, 6, 23):
        idx, sc = s.search_batch(QUERIES, k=8, batch_size=bs)
        np.testing.assert_array_equal(idx, ref_idx)
        np.testing.assert_allclose(sc, ref_sc, rtol=0, atol=1e-6)
