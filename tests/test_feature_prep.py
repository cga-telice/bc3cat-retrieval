"""The feature pipeline, moved out of features.ipynb without changing what it produces.

Same contract as tests/test_corpus_prep.py: `OEB_short_feats.parquet` and
`OEB_long_feats.parquet` already hold this code's output, so the move is checked by
re-deriving them from `*_norm.parquet` and requiring equality column by column.

`text_word_params` is the field `bm25_unigram_params` indexes and `text_word_uni_bi` the one
the unibigram variants index, so these columns are the ones that would quietly change a
published number if the move were unfaithful.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.feature_prep import build_features

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

pytestmark = pytest.mark.skipif(
    not (PROCESSED / "OEB_short_feats.parquet").exists(),
    reason="data/processed is git-ignored and absent in this checkout",
)

SAMPLE = 400

#: Every column the notebook's own `must_have` check requires, plus the indexed fields.
DERIVED_COLUMNS = (
    "param_phrases",
    "text_word_phrases_add",
    "text_word_phrases_replace",
    "tokens_bigram",
    "text_word_uni_bi",
    "has_numbers",
    "tokens_word_bi",
)


@pytest.fixture(scope="module", params=["short", "long"])
def side(request):
    import pandas as pd

    which = request.param
    norm = pd.read_parquet(PROCESSED / f"OEB_{which}_norm.parquet").head(SAMPLE)
    feats = pd.read_parquet(PROCESSED / f"OEB_{which}_feats.parquet").head(SAMPLE)
    return which, norm, feats


def test_every_derived_column_is_reproduced(side):
    which, norm, recorded = side

    derived = build_features(norm)

    for column in DERIVED_COLUMNS:
        assert column in derived.columns, f"{which}: build_features did not produce {column}"
        left = [_comparable(v) for v in derived[column]]
        right = [_comparable(v) for v in recorded[column]]
        assert left == right, f"{which}: {column}"


def test_the_indexed_field_is_untouched(side):
    """text_word_params comes from data.ipynb and must survive the feature stage unchanged."""
    which, norm, recorded = side

    derived = build_features(norm)

    assert derived["text_word_params"].tolist() == recorded["text_word_params"].tolist(), which


def test_no_row_is_gained_or_lost(side):
    which, norm, recorded = side

    derived = build_features(norm)

    assert len(derived) == len(norm) == len(recorded), which


def _comparable(value):
    """Lists survive a parquet round-trip as numpy arrays, sometimes nested; compare as lists."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return [_comparable(v) for v in value]
    return value
