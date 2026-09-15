"""Reading the dev/test split from its contract (D-007, D-021).

`SPLITS.md` *is* the split — "the concept lists below are the split itself, not a recipe for
recomputing it". So the harness reads that file rather than re-deriving anything, and this
checks the reading against the balance table the same document states.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.splits import SPLIT_NAMES, load_split, split_of_concept

REPO = Path(__file__).resolve().parents[1]
SPLITS_MD = REPO / "docs" / "synthetic-oe" / "SPLITS.md"


def test_the_split_names_are_dev_and_test():
    assert SPLIT_NAMES == ("dev", "test")


def test_the_dev_split_has_the_42_concepts_the_contract_states():
    dev = load_split("dev", path=SPLITS_MD)

    assert len(dev) == 42
    assert "OEA010$" in dev
    assert "OEB020$" in dev


def test_the_test_split_has_the_41_concepts_the_contract_states():
    test = load_split("test", path=SPLITS_MD)

    assert len(test) == 41
    assert "OEB280$" in test


def test_the_two_splits_partition_the_83_concepts():
    dev = load_split("dev", path=SPLITS_MD)
    test = load_split("test", path=SPLITS_MD)

    assert dev & test == set()
    assert len(dev | test) == 83


def test_every_concept_key_looks_like_a_concept_key():
    """A stray line picked up from the prose would show up here."""
    for name in SPLIT_NAMES:
        for key in load_split(name, path=SPLITS_MD):
            assert key.startswith("OE") and key.endswith("$"), key


def test_a_concept_is_assigned_to_exactly_one_side():
    assert split_of_concept("OEA010$", path=SPLITS_MD) == "dev"
    assert split_of_concept("OEB280$", path=SPLITS_MD) == "test"


def test_an_unknown_concept_is_an_error_not_a_default():
    """Defaulting an unrecognised concept into dev would quietly enlarge the tuning set."""
    with pytest.raises(KeyError, match="ZZZ999"):
        split_of_concept("ZZZ999$", path=SPLITS_MD)


def test_an_unknown_split_name_is_rejected():
    with pytest.raises(ValueError, match="train"):
        load_split("train", path=SPLITS_MD)
