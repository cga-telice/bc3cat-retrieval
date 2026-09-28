"""The overlap metric, pinned against the figure the reviewers' objection was granted on (S3 wi9).

`AUTCON_analisis_revision.md` §2.6 measured OEB `resumen` against `texto` and found the target holds
**94.09 %** of the query's tokens and **99.93 %** of its numbers. That measurement is why the
objection was conceded, and S3 reuses the same quantity as the x-axis for H5 and H6. So the
definition is not a free choice: it has to reproduce those figures, and these tests are what stop it
drifting into something that merely sounds similar.

The first test is the load-bearing one. The rest pin the properties that make the number mean what
it says — identity scores 1.0, coverage ignores how often a token repeats, a query with no numbers
is excluded from the numeric mean rather than counted as 0, and the doubled-token detector fires on
the artefact and not on ordinary catalogue prose.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.build_overlap import (
    OEB_REFERENCE,
    TOLERANCE_PP,
    has_doubled_token,
    has_topo_drift,
    lexical_coverage,
    measure,
    numeric_coverage,
)

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "processed"

pytestmark = pytest.mark.skipif(
    not (DATA / "OEB_resumen.json").is_file(),
    reason="data/processed is git-ignored and absent in this checkout",
)


@pytest.fixture(scope="module")
def oeb_stats():
    resumen = json.loads((DATA / "OEB_resumen.json").read_text(encoding="utf-8"))
    texto = {
        r["item_key"]: r["text"]
        for r in json.loads((DATA / "OEB_texto.json").read_text(encoding="utf-8"))
    }
    pairs = [(r["text"], texto[r["item_key"]]) for r in resumen if r["item_key"] in texto]
    return measure(pairs)


# --- the gate ---------------------------------------------------------------------------


@pytest.mark.parametrize("statistic", sorted(OEB_REFERENCE))
def test_reproduces_the_oeb_reference(oeb_stats, statistic):
    """Exit criterion 8. Observed worst gap is 0.08 pp against a 0.5 pp tolerance."""
    assert abs(oeb_stats[statistic] - OEB_REFERENCE[statistic]) <= TOLERANCE_PP


def test_the_median_lands_exactly(oeb_stats):
    """A different tokenisation would move the median; that it matches to 2 dp is the evidence
    that the definition is the review analysis's own and not merely a close relative."""
    assert round(oeb_stats["lexical_median"], 2) == OEB_REFERENCE["lexical_median"]


# --- the properties that make the number mean what it says -------------------------------


def test_identity_is_total_coverage():
    text = "tubo de PVC de 200 mm de diametro, 3 <= i < 5 horas"
    assert lexical_coverage(text, text) == 1.0
    assert numeric_coverage(text, text) == 1.0


def test_coverage_counts_distinct_tokens_not_repetitions():
    """Distinct, not positional — this is what reproduces the reference.

    It also matters for BC3CAT-Syn specifically: the pantry artefact repeats tokens, and a
    positional definition would let a doubled token count twice and inflate coverage exactly where
    the corpus is known to be damaged.
    """
    assert lexical_coverage("tubo tubo tubo", "tubo de pvc") == 1.0
    assert lexical_coverage("tubo tubo canaleta", "tubo de pvc") == 0.5


def test_a_query_with_no_numbers_is_excluded_not_scored_zero():
    """Otherwise the numeric mean would be dragged down by queries that never had a number to
    lose, and `num_to_text` — which removes numbers — would look like a numeric-coverage failure."""
    assert numeric_coverage("canaleta de pvc con tapa", "canaleta de pvc") is None
    stats = measure([("canaleta de pvc", "canaleta de pvc con tapa")])
    assert stats["numeric_mean"] != stats["numeric_mean"]  # NaN: nothing to average
    assert stats["has_number"] == 0.0


def test_missing_numbers_are_counted_against_the_query():
    assert numeric_coverage("tubo de 200 mm", "tubo de 300 mm") == 0.0
    assert numeric_coverage("tubo de 200 y 300", "tubo de 200") == 0.5


def test_coverage_is_asymmetric():
    """It asks what share of the QUERY is in the target, not the reverse: a long target containing
    a short query scores 1.0, which is the near-verbatim regime the objection is about."""
    assert lexical_coverage("tubo de pvc", "tubo de pvc de 200 mm con tapa") == 1.0
    assert lexical_coverage("tubo de pvc de 200 mm con tapa", "tubo de pvc") < 1.0


# --- the D-004 doubled-token detector ----------------------------------------------------


def test_the_detector_fires_on_the_documented_artefact():
    assert has_doubled_token("tubos tubos de PVC")
    assert has_doubled_token("diametro 200 mm mm")


def test_the_detector_does_not_fire_on_ordinary_prose():
    assert not has_doubled_token("tubo de PVC de 200 mm de diametro")
    assert not has_doubled_token("canaleta de 3x1.5 cm con tapa")


def test_the_detector_does_not_fire_anywhere_in_the_corpus():
    """The claim that makes it usable as a marker rather than a correlate: immediate token
    repetition does not occur naturally in this catalogue, so a hit is the artefact."""
    corpus = json.loads((DATA / "OE_texto.json").read_text(encoding="utf-8"))
    hits = [r["item_key"] for r in corpus if has_doubled_token(r["text"])]
    assert not hits, f"{len(hits)} corpus documents contain a doubled token, e.g. {hits[:3]}"


# --- the D-004 "con topo" drift detector (S3 audit F5) ------------------------------------


def test_the_topo_detector_fires_on_the_documented_drift():
    assert has_topo_drift("excavacion con topografia de tunel", "excavacion con topo de tunel")


def test_the_topo_detector_needs_the_target_to_lack_the_word():
    assert not has_topo_drift("con topografia", "levantamiento con topografia")
    assert not has_topo_drift("con topo", "con topo")


def test_the_corpus_never_says_topografia():
    """What makes the detector a marker: the word only enters through the rewrite."""
    corpus = json.loads((DATA / "OE_texto.json").read_text(encoding="utf-8"))
    hits = [r["item_key"] for r in corpus if "topograf" in r["text"].lower()]
    assert not hits, f"{len(hits)} corpus documents say topografia, e.g. {hits[:3]}"
