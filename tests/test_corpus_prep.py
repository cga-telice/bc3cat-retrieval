"""The feature functions, moved out of data.ipynb without changing what they produce.

These functions lived inside a notebook cell, where they could not be tested and could not
be shared with the query-side code that S1 needs. Moving them is only safe if they still
produce exactly what they produced before, and there is an unusually good way to check that:
`OEB_short_norm.parquet` already holds their output for all 47,513 rows.

The input is taken from `OEB_texto.json` / `OEB_resumen.json`, not from the parquet: a
round-trip through parquet turns the nested `parameters` dict into a struct and fills absent
keys with None, so the parquet's own `parameters` column is not what the notebook saw. The
derived columns are unaffected, and those are what is compared.

They skip when data/ is absent — it is git-ignored, so a bare checkout has no corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.corpus_prep import (
    add_param_token_columns,
    add_processed_columns,
    build_param_tokens,
    clean_df,
    extract_numbers,
    load_records,
    make_text_char,
    normalize_parameters_field,
    normalize_text,
    tokenize_words,
)

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

pytestmark = pytest.mark.skipif(
    not (PROCESSED / "OEB_short_norm.parquet").exists(),
    reason="data/processed is git-ignored and absent in this checkout",
)

#: Enough rows to exercise the variety without re-deriving all 47,513.
SAMPLE = 400


@pytest.fixture(scope="module")
def recorded():
    """The columns as data.ipynb saved them, indexed by item_key."""
    import pandas as pd

    short = pd.read_parquet(PROCESSED / "OEB_short_norm.parquet").set_index("item_key")
    long = pd.read_parquet(PROCESSED / "OEB_long_norm.parquet").set_index("item_key")
    return {"short": short, "long": long}


@pytest.fixture(scope="module")
def raw():
    """The same records as they enter the pipeline, from the JSON the notebook read."""
    return {
        "short": clean_df(load_records(PROCESSED / "OEB_resumen.json")).head(SAMPLE),
        "long": clean_df(load_records(PROCESSED / "OEB_texto.json")).head(SAMPLE),
    }


def test_the_template_row_is_what_separates_47_514_from_47_513():
    """D-024: the JSON holds one more record than the parquet, and this is why."""
    records = load_records(PROCESSED / "OEB_texto.json")
    cleaned = clean_df(records)

    dropped = set(records["item_key"]) - set(cleaned["item_key"])

    assert dropped == {"OEB#"}
    assert len(records) - len(cleaned) == 1


@pytest.mark.parametrize("column", ["text_norm", "text_word", "text_char"])
def test_text_columns_are_reproduced(raw, recorded, column):
    derive = {
        "text_norm": lambda t: normalize_text(t),
        "text_word": lambda t: " ".join(tokenize_words(normalize_text(t))),
        "text_char": lambda t: make_text_char(normalize_text(t)),
    }[column]

    for _, row in raw["short"].iterrows():
        assert derive(row["text"]) == recorded["short"].loc[row["item_key"], column], row["item_key"]


def test_token_and_number_lists_are_reproduced(raw, recorded):
    for _, row in raw["short"].iterrows():
        norm = normalize_text(row["text"])
        saved = recorded["short"].loc[row["item_key"]]

        assert list(tokenize_words(norm)) == list(saved["tokens_word"]), row["item_key"]
        assert list(extract_numbers(norm)) == list(saved["numbers"]), row["item_key"]


def test_multiword_parameter_values_are_reproduced(raw, recorded):
    for _, row in raw["long"].iterrows():
        _, multi = normalize_parameters_field(row["parameters"])

        saved = list(recorded["long"].loc[row["item_key"], "param_values_multi_norm"])
        assert list(multi) == saved, row["item_key"]


def test_param_tokens_and_the_fused_field_are_reproduced(raw, recorded):
    """text_word_params is the field bm25_unigram_params indexes, so it is the one that
    would silently change the headline method if this move were not faithful."""
    for _, row in raw["long"].iterrows():
        par_norm, _ = normalize_parameters_field(row["parameters"])
        tokens = build_param_tokens(par_norm)
        saved = recorded["long"].loc[row["item_key"]]

        assert list(tokens) == list(saved["param_tokens"]), row["item_key"]
        fused = (saved["text_word"] + " " + " ".join(tokens)).strip()
        assert fused == saved["text_word_params"], row["item_key"]


def test_the_whole_frame_is_reproduced_end_to_end(raw, recorded):
    processed = add_param_token_columns(add_processed_columns(raw["long"], "text")).set_index(
        "item_key"
    )
    saved = recorded["long"].loc[processed.index]

    for column in ("text_norm", "text_word", "text_char", "text_word_params"):
        assert processed[column].tolist() == saved[column].tolist(), column
    for column in ("tokens_word", "numbers", "param_tokens", "param_values_multi_norm"):
        assert [list(v) for v in processed[column]] == [
            list(v) for v in saved[column]
        ], column
