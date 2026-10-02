"""S9 work item 2: the canonicaliser (transform C).

Behaviour is pinned on hand-written cases against a small synthetic corpus, so the rules are tested apart
from the catalogue. Two properties are pinned on the real corpus, because the design's constraints rest on
them: C leaves every corpus `texto` unchanged (so Z2 holds by construction, and the report must say so),
and C reads nothing but the corpus — no menu, no sidecar, no query field but its text.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from query_rewrite import canon
from query_rewrite.canon import Canonicaliser

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "processed" / "OE_texto.json"

TOY = [
    "Canaleta PVC de 30x15 mm con tapa.",
    "Canalización de 4 tubos de 110 mm. Banda de mantenimiento: i < 3 horas.",
    "Arqueta de 90x81x70 cm. Canalización de 4 tubos de 110 mm.",
    "Canalización de un tubo de 110 mm, con dos tapas.",
    "Canalización de un tubo de 160 mm, con dos tapas.",
    "Cimentación de 1,60 m de profundidad. Hormigón de 25 N/mm2.",
] * 3


@pytest.fixture(scope="module")
def toy():
    return Canonicaliser(TOY)


@pytest.mark.parametrize("text,expected", [
    ("Canalización de cuatro tubos de ciento diez milímetros", "Canalización de 4 tubos de 110 mm"),
    ("Canaleta PVC de 0,03x0,015 m con tapa.", "Canaleta PVC de 30x15 mm con tapa."),
    ("arqueta de 0,9 m x 0,81 m x 0,7 m", "arqueta de 90x81x70 cm"),
    ("arqueta de 900 mm x 81 cm x 0,7 m", "arqueta de 90x81x70 cm"),
    ("banda: i < 3 h", "banda: i < 3 horas"),
    ("hormigón de veinticinco N/mm2", "hormigón de 25 N/mm2"),
    ("uno coma sesenta metros", "1,6 m"),
    ("treinta por quince milímetros", "30x15 mm"),
    ("dos mil trescientos cuarenta y cinco", "2345"),
])
def test_rewrites_to_catalogue_surfaces(toy, text, expected):
    assert toy.apply(text)[0] == expected


@pytest.mark.parametrize("text", [
    "con una cama de arena",          # article, no corpus evidence: stays
    "un tubo de PVC",                 # the corpus writes "un tubo"
    "dos tapas",                      # the corpus writes "dos tapas"
    "tubo de 0,07 m",                 # 70 mm is not in the inventory: declined, unchanged
    "Trabajo: Diurno. 3 <= i < 5 horas",
    "Canaleta PVC de 30x15 mm con tapa.",
])
def test_leaves_alone_what_it_has_no_evidence_for(toy, text):
    assert toy.apply(text)[0] == text


def test_report_counts_what_it_did(toy):
    _, rep = toy.apply("cuatro tubos de 0,11 m y tubo de 0,07 m")
    assert (rep.numbers, rep.converted, rep.declined) == (1, 1, 1)
    assert rep.touched()


def test_a_unit_the_corpus_never_writes_is_left_alone(toy):
    assert "kilogramos" not in toy.spelling and "kg" not in toy.spelling
    assert toy.apply("pesa 5 kilogramos")[0] == "pesa 5 kilogramos"


def test_canonicaliser_reads_only_the_text():
    params = inspect.signature(Canonicaliser.apply).parameters
    assert list(params) == ["self", "text"]
    source = inspect.getsource(canon)
    code = source.split('"""', 2)[2]  # past the module docstring
    for forbidden in ("modification", "menu", "sidecar", "gold", "parameters", "parent_key"):
        assert forbidden not in code, forbidden
    assert canon.CORPUS.name == "OE_texto.json"


@pytest.mark.skipif(not CORPUS.exists(), reason="data/processed absent")
def test_identity_on_the_whole_corpus():
    texts = [r["text"] for r in json.loads(CORPUS.read_text(encoding="utf-8"))]
    c = Canonicaliser(texts)
    changed = [t for t in texts if c.apply(t)[0] != t]
    assert len(texts) == 70_242
    assert changed == []
