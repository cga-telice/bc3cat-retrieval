"""Blocked `search_batch` returns what one block returned — the five arms S3 added (defect H6).

Same claim as `tests/test_bm25_batching.py` and `tests/test_dense_batching.py`, which cover the
three retrievers S1 blocked because S2 needed them: a query's scores depend on no other query, so
splitting the query set changes memory, not results.

Why these five needed it. D-012 widened the run set from five arms to ten, and the first E0 pass
(S3 work items 6–7) lost **12 of 17 runs** to `DeadKernelError`. Four of the five build a B x N
score matrix — 35,422 x 70,242 is 9.3 GiB in float32 against ~20 GiB of container RAM — and
`bge_m3_dense` instead posted all 35,422 queries to the embedding container in one HTTP request.
Neither had ever been exercised at that scale, because no earlier sprint ran these arms.

Encoders are replaced by deterministic fakes, and the searchers are built with `__new__` so no
index has to exist: what is under test is the blocking, not the scoring or the encoder.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import sparse

from retrievers import bge_m3_dense, bge_m3_sparse, dense_es_hiiamsid, dense_gte, tfidf_unigram

N_DOCS, DIM, VOCAB, N_QUERIES = 40, 16, 50, 23
QUERIES = [f"consulta numero {i}" for i in range(N_QUERIES)]
BATCH_SIZES = [1, 2, 5, 22, 23, 24, 1000]


def _rng(text: str) -> np.random.Generator:
    return np.random.default_rng(sum(map(ord, text)) * 7919 + len(text))


def _l2(X: np.ndarray) -> np.ndarray:
    return (X / np.maximum(np.linalg.norm(X, axis=-1, keepdims=True), 1e-12)).astype(np.float32)


def _dense_vec(text: str, dim: int = DIM) -> np.ndarray:
    """L2-normalised, as every dense arm here actually is.

    `dense_gte` and `dense_es_hiiamsid` declare `normalize: true`, and `bge_m3_dense` calls
    `faiss.normalize_L2` on both sides. Keeping the fixture faithful also keeps the test strict:
    float32 matrix multiply is not associative, so a block of 1 row and a block of 23 go through
    different BLAS kernels and disagree in the last bits. On unnormalised vectors that showed up
    as ~2e-6 on scores of ~6 — real, harmless, and enough to force a loose tolerance. On
    normalised vectors the scores are bounded by 1 and 1e-6 is a tight bound rather than a
    generous one.
    """
    return _l2(_rng(text).standard_normal(dim))


# --- the four that densify a B x N score matrix -----------------------------------------


@pytest.fixture()
def tfidf():
    s = tfidf_unigram.TfidfSearcher.__new__(tfidf_unigram.TfidfSearcher)
    rng = np.random.default_rng(0)
    s.X_docs = sparse.csr_matrix(rng.random((N_DOCS, VOCAB), dtype=np.float32) < 0.2, dtype=np.float32)
    s.external_ids = np.asarray([f"d{i}" for i in range(N_DOCS)], dtype=object)
    s.encode = lambda texts: sparse.csr_matrix(
        np.stack([_rng(t).random(VOCAB).astype(np.float32) for t in texts])
    )
    return s


@pytest.fixture()
def sparse_bge():
    s = bge_m3_sparse.BGEM3SparseSearcher.__new__(bge_m3_sparse.BGEM3SparseSearcher)
    rng = np.random.default_rng(1)
    s.X_docs = sparse.csr_matrix(rng.random((N_DOCS, VOCAB), dtype=np.float32) < 0.2, dtype=np.float32)
    s.external_ids = np.asarray([f"d{i}" for i in range(N_DOCS)], dtype=object)
    # the two steps the real path composes: encode to lexical weights, align to the doc vocabulary
    s._encode_queries_sparse = lambda texts: list(texts)
    s._align_query_matrix = lambda texts: sparse.csr_matrix(
        np.stack([_rng(t).random(VOCAB).astype(np.float32) for t in texts])
    )
    return s


@pytest.fixture()
def gte():
    s = dense_gte.DenseGTESearcher.__new__(dense_gte.DenseGTESearcher)
    rng = np.random.default_rng(2)
    s.X_docs = _l2(rng.standard_normal((N_DOCS, DIM)))
    s.external_ids = np.asarray([f"d{i}" for i in range(N_DOCS)], dtype=object)
    s.encode = lambda texts: np.stack([_dense_vec(t) for t in texts])
    return s


@pytest.fixture()
def hiiamsid():
    s = dense_es_hiiamsid.DenseESSearcher.__new__(dense_es_hiiamsid.DenseESSearcher)
    rng = np.random.default_rng(3)
    s.X_docs = _l2(rng.standard_normal((N_DOCS, DIM)))
    s.external_ids = np.asarray([f"d{i}" for i in range(N_DOCS)], dtype=object)
    s.encode = lambda texts: np.stack([_dense_vec(t) for t in texts])
    return s


@pytest.fixture()
def dense_bge():
    """FAISS replaced by an exact brute-force stand-in with the same return contract (I, D)."""
    s = bge_m3_dense._Searcher.__new__(bge_m3_dense._Searcher)
    rng = np.random.default_rng(4)
    X = _l2(rng.standard_normal((N_DOCS, DIM)))
    s.external_ids = np.asarray([f"d{i}" for i in range(N_DOCS)], dtype=object)

    class _FakeIndex:
        def search(self, Q, k):
            sims = Q @ X.T
            idx = np.argsort(-sims, axis=1)[:, :k]
            rows = np.arange(len(Q))[:, None]
            return sims[rows, idx], idx

    s.index = _FakeIndex()
    s._encode = lambda texts: np.stack([_dense_vec(t) for t in texts])
    return s


ARMS = ["tfidf", "sparse_bge", "gte", "hiiamsid", "dense_bge"]


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("batch_size", BATCH_SIZES)
def test_blocks_equal_one_block(arm, batch_size, request):
    searcher = request.getfixturevalue(arm)
    ref_idx, ref_scores = searcher.search_batch(QUERIES, k=10, batch_size=None)
    idx, scores = searcher.search_batch(QUERIES, k=10, batch_size=batch_size)
    np.testing.assert_array_equal(idx, ref_idx)
    np.testing.assert_allclose(scores, ref_scores, rtol=0, atol=1e-6)


@pytest.mark.parametrize("arm", ARMS)
def test_shape_is_n_queries_by_k(arm, request):
    """A concatenation bug would most likely show up as a wrong row count."""
    searcher = request.getfixturevalue(arm)
    idx, scores = searcher.search_batch(QUERIES, k=10, batch_size=5)
    assert idx.shape == (N_QUERIES, 10)
    assert scores.shape == (N_QUERIES, 10)


@pytest.mark.parametrize(
    "module", [tfidf_unigram, bge_m3_sparse, dense_gte, dense_es_hiiamsid, bge_m3_dense]
)
def test_every_arm_blocks_by_default(module):
    """The default has to be blocking, not `None`.

    `retrieve.ipynb` passes no `batch_size` at all — `BATCH_SIZE = None` in the notebook means
    "the retriever's own default". So an arm whose default is one block dies at 35,422 queries
    however careful the caller is, which is exactly what happened.
    """
    assert module.DEFAULT_BATCH_SIZE == 2048


@pytest.mark.parametrize("arm", ARMS)
def test_nonsense_batch_size_is_refused(arm, request):
    searcher = request.getfixturevalue(arm)
    for bad in (0, -1):
        with pytest.raises(ValueError):
            searcher.search_batch(QUERIES, k=10, batch_size=bad)


@pytest.mark.parametrize("arm", ARMS)
def test_the_block_helper_is_still_reachable(arm, request):
    """`search_batch` must delegate rather than duplicate: one scoring path, not two."""
    searcher = request.getfixturevalue(arm)
    assert hasattr(searcher, "_search_block")
    direct = searcher._search_block(QUERIES[:5], 10)
    viaapi = searcher.search_batch(QUERIES[:5], k=10, batch_size=None)
    np.testing.assert_array_equal(direct[0], viaapi[0])
