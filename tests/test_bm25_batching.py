"""Batched scoring must return exactly what unbatched scoring returned (S1 item 12).

The scores of one query do not depend on any other query, so splitting the query set into
batches is an arithmetic no-op. That is the claim; these tests hold it to it on a toy index
built here, and the golden fixture holds it on the real one.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

from retrievers.bm25_unigram import BM25Searcher

VOCAB = ["hormigon", "acero", "tubo", "zanja", "mm"]

#: Five documents over five terms, with weights chosen so that no two rows tie — a tie would
#: make the top-k order depend on the sort, which is not what these tests are about.
DOC_WEIGHTS = [
    [3.0, 0.0, 1.0, 0.0, 0.5],
    [0.0, 2.5, 1.5, 0.0, 0.25],
    [1.0, 0.0, 3.5, 2.0, 0.75],
    [0.5, 1.0, 0.0, 3.0, 0.125],
    [2.0, 0.5, 0.25, 1.0, 1.5],
]

QUERIES = [
    "hormigon tubo",
    "acero mm",
    "zanja",
    "tubo zanja mm",
    "hormigon acero tubo zanja mm",
    "acero",
    "mm mm",
]


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    """A minimal BM25 index in the on-disk shape the searcher expects."""
    data = tmp_path / "data"
    data.mkdir(parents=True)

    sparse.save_npz(data / "bm25_docs.npz", sparse.csr_matrix(np.array(DOC_WEIGHTS, dtype=np.float32)))
    (data / "vocab.json").write_text(
        json.dumps({term: i for i, term in enumerate(VOCAB)}), encoding="utf-8"
    )
    np.save(data / "idf.npy", np.array([1.0, 2.0, 0.5, 1.5, 0.25], dtype=np.float32))

    (tmp_path / "mapping.jsonl").write_text(
        "\n".join(
            json.dumps({"doc_id": i, "external_id": f"OEB{i:03d}aa"}) for i in range(len(DOC_WEIGHTS))
        ),
        encoding="utf-8",
    )
    (tmp_path / "meta.json").write_text(
        json.dumps({"method": "bm25", "text_field": "text_word_params", "params": {}}),
        encoding="utf-8",
    )
    (tmp_path / "fields.json").write_text(json.dumps({"text_field": "text_word_params"}), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("batch_size", [1, 2, 3, len(QUERIES), len(QUERIES) + 5])
def test_batching_changes_nothing(index_dir, batch_size):
    searcher = BM25Searcher(index_dir)

    whole_idx, whole_scores = searcher.search_batch(QUERIES, k=3, batch_size=None)
    batched_idx, batched_scores = searcher.search_batch(QUERIES, k=3, batch_size=batch_size)

    assert np.array_equal(whole_idx, batched_idx)
    assert np.array_equal(whole_scores, batched_scores)


def test_batched_results_match_one_query_at_a_time(index_dir):
    """The batch path and the single-query path are the same computation."""
    searcher = BM25Searcher(index_dir)

    batched_idx, batched_scores = searcher.search_batch(QUERIES, k=3, batch_size=2)

    for row, query in enumerate(QUERIES):
        one_idx, one_scores = searcher.search(query, k=3)
        assert np.array_equal(batched_idx[row], one_idx), query
        assert np.array_equal(batched_scores[row], one_scores), query


def test_a_default_batch_size_is_applied(index_dir):
    """Without a default, the caller that forgets is the caller that kills the kernel."""
    searcher = BM25Searcher(index_dir)

    assert searcher.default_batch_size > 0


def test_an_invalid_batch_size_is_rejected(index_dir):
    searcher = BM25Searcher(index_dir)

    with pytest.raises(ValueError, match="batch_size"):
        searcher.search_batch(QUERIES, k=3, batch_size=0)


def test_an_empty_query_list_returns_empty_results(index_dir):
    searcher = BM25Searcher(index_dir)

    idx, scores = searcher.search_batch([], k=3)

    assert idx.shape[0] == 0 and scores.shape[0] == 0
