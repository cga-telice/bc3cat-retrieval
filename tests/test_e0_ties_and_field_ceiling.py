"""S3 re-audit F4 and F5: a field's ceiling is counted on the field, and a tie is not a win."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.build_results_e0 import TRANSFERRED, argmax_outcome, unavoidable_misses  # noqa: E402


def test_unavoidable_misses_counts_all_but_one_per_group():
    texts = pd.Series(["a", "a", "a", "b", "b", "c"])
    assert unavoidable_misses(texts) == 3


def test_a_field_without_duplicates_has_no_unavoidable_miss():
    assert unavoidable_misses(pd.Series(["a|p1", "a|p2", "b|p1"])) == 0


def _cell(variant, queryset, argmaxes):
    return {"variant": variant, "queryset": queryset, "argmaxes": argmaxes}


def test_an_exact_tie_is_reported_as_a_tie_not_a_win():
    cells = [
        _cell("v", "s1", [TRANSFERRED]),
        _cell("v", "s2", sorted([TRANSFERRED, (0.80, 0.35)])),
        _cell("v", "s3", [(0.60, 0.20)]),
    ]
    text = argmax_outcome(cells)
    assert text.startswith("the unique argmax in 1 of 3 cells")
    assert "ties exactly for it in one more" in text and "0.80/0.35" in text
