"""BC3CAT-Syn's parameters, against the real OE files (INTAKE §4 breakpoint 2).

Two shapes have to meet here. The corpus nests each axis:

    {"A": {"label": "DIMENSIONES", "values": [{"label": "a", "value": "30x15 mm"}]}, "F": null}

and a synthetic query flattens it, with the values rewritten:

    {"A": "0.03x0.015 m", "B": "Diurno", "C": "3 <= i < 5 horas", "F": null}

What matters is not that both parse, but that they mint the *same* param tokens wherever the
modification did not touch the axis. `text_word_params` — the field `bm25_unigram_params`
indexes — is built from those tokens, so a query whose unmodified axes minted different
tokens would be measuring the adapter instead of the retrieval.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.corpus_prep import (
    axis_labels_from_corpus,
    build_param_tokens,
    is_flat_parameters,
    normalize_parameters_field,
)

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

pytestmark = pytest.mark.skipif(
    not (PROCESSED / "OE_texto.json").exists(),
    reason="data/processed is git-ignored and absent in this checkout",
)


@pytest.fixture(scope="module")
def corpus():
    return json.loads((PROCESSED / "OE_texto.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def single_queries():
    return json.loads((PROCESSED / "OE_single_texto.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_item_key(corpus):
    return {r["item_key"]: r for r in corpus}


# --- telling the two shapes apart ------------------------------------------------------


def test_the_corpus_shape_is_not_flat(corpus):
    assert not is_flat_parameters(corpus[0]["parameters"])


def test_the_query_shape_is_flat(single_queries):
    assert is_flat_parameters(single_queries[0]["parameters"])


def test_an_empty_or_absent_parameters_field_is_not_mistaken_for_flat():
    assert not is_flat_parameters({})
    assert not is_flat_parameters(None)


# --- null axes -------------------------------------------------------------------------


def test_a_null_axis_in_the_corpus_does_not_raise(corpus):
    """7,212 of 70,242 OE records carry one; the unmigrated code raises on every one."""
    record = next(r for r in corpus if any(v is None for v in r["parameters"].values()))

    par_norm, _ = normalize_parameters_field(record["parameters"])

    assert all(block is not None for block in par_norm.values())


def test_a_null_axis_mints_no_token(corpus):
    record = next(r for r in corpus if any(v is None for v in r["parameters"].values()))
    present = [k for k, v in record["parameters"].items() if v is not None]

    tokens = build_param_tokens(normalize_parameters_field(record["parameters"])[0])

    assert len(tokens) == len(present)


def test_a_null_axis_in_a_query_mints_no_token(single_queries):
    query = next(q for q in single_queries if any(v is None for v in q["parameters"].values()))
    present = [k for k, v in query["parameters"].items() if v is not None]

    tokens = build_param_tokens(normalize_parameters_field(query["parameters"])[0])

    assert len(tokens) == len(present)


# --- the axis labels -------------------------------------------------------------------


def test_axis_labels_come_from_the_corpus(corpus):
    """The concept schema lists axes by label without their letter, so the letter-to-label
    map is read off the corpus itself, where both appear together."""
    labels = axis_labels_from_corpus(corpus)

    assert labels["OEA010$"]["A"] == "DIMENSIONES"
    assert labels["OEA010$"]["B"] == "TRABAJO"


# --- the point of the whole thing ------------------------------------------------------


def test_unmodified_axes_mint_the_same_tokens_as_the_corpus(corpus, single_queries, by_item_key):
    """For a single-modification query, every axis the modification did not touch must mint
    exactly the token its gold leaf mints. Checked over every single-modification query that
    changed a parameter value, not a sample."""
    labels = axis_labels_from_corpus(corpus)
    checked = 0
    unchanged_axes_checked = 0

    for query in single_queries:
        gold = by_item_key.get(query["gold_item_key"])
        if gold is None:
            continue

        gold_norm, _ = normalize_parameters_field(gold["parameters"])
        query_norm, _ = normalize_parameters_field(
            query["parameters"], labels.get(query["parent_key"], {})
        )
        gold_tokens = dict(zip(gold["parameters"].keys(), build_param_tokens(gold_norm)))
        query_tokens = dict(zip(query["parameters"].keys(), build_param_tokens(query_norm)))

        for axis, raw in query["parameters"].items():
            if raw is None or gold["parameters"].get(axis) is None:
                continue
            gold_value = gold["parameters"][axis]["values"][0]["value"]
            if str(raw).strip() != str(gold_value).strip():
                continue  # this axis is what the modification rewrote
            assert query_tokens.get(axis) == gold_tokens.get(axis), (
                query["item_key"],
                axis,
            )
            unchanged_axes_checked += 1
        checked += 1

    assert checked > 1000, "too few queries compared for this to mean anything"
    assert unchanged_axes_checked > 1000


# --- gold integrity (INTAKE §4 breakpoint 1) -------------------------------------------


def test_every_synthetic_gold_key_is_present_in_the_corpus(single_queries, by_item_key):
    from utils.corpus_prep import assert_gold_present

    import pandas as pd

    queries = pd.DataFrame(
        [{"item_key": q["item_key"], "gold_item_key": q["gold_item_key"]} for q in single_queries]
    )

    assert_gold_present(queries, set(by_item_key))  # must not raise


def test_a_missing_gold_key_fails_loud_and_names_the_query():
    """Silently dropping such a query is how a whole condition disappears from a report."""
    import pandas as pd
    import pytest as _pytest

    from utils.corpus_prep import assert_gold_present

    queries = pd.DataFrame(
        [
            {"item_key": "OEA010aaba_syn_1", "gold_item_key": "OEA010aaba"},
            {"item_key": "OEA010aaba_syn_2", "gold_item_key": "OEA010_not_in_corpus"},
        ]
    )

    with _pytest.raises(KeyError, match="OEA010aaba_syn_2"):
        assert_gold_present(queries, {"OEA010aaba"})


def test_a_corpus_query_set_without_gold_keys_is_accepted():
    """texto and resumen are the leaf's own renderings: the query key is the gold."""
    import pandas as pd

    from utils.corpus_prep import assert_gold_present

    queries = pd.DataFrame([{"item_key": "OEA010aaba"}])

    assert_gold_present(queries, {"OEA010aaba"})
