"""S14 work item 1: the sprint's population, asserted in the tree rather than taken from the design.

The design (`SPRINT_S14_DESIGN.md`, frozen 2026-10-19) quotes an entry state — the pairing of `bt_texto` to
STACKED-P v2 leaf for leaf, the D-033 exclusions, the translated-sentence fractions, the value / glossary flags,
F-BT-1 — and every figure it quotes is re-derived here from the delivered files, the split and the corpus. Text is
read on dev only, except where the pairing itself is checked on both splits (operating rule 2 forbids reading test
results, not test query text; the same reading `test_intake_20261016.py` makes).
"""

from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from utils.build_overlap import lexical_coverage  # noqa: E402
from utils.exclusions import collapse, duplicate_texto, stacked_p  # noqa: E402
from utils.splits import load_split  # noqa: E402

PROCESSED = REPO / "data" / "processed"
pytestmark = pytest.mark.skipif(not (PROCESSED / "OE_bt_texto.json").exists(), reason="data/ not populated")


def load(name: str):
    return json.loads((PROCESSED / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dev() -> frozenset[str]:
    return load_split("dev")


@pytest.fixture(scope="module")
def corpus() -> dict[str, dict]:
    return {r["item_key"]: r for r in load("OE_texto.json")}


@pytest.fixture(scope="module")
def bt_dev(dev) -> list[dict]:
    return [r for r in load("OE_bt_texto.json") if r["parent_key"] in dev]


@pytest.fixture(scope="module")
def stacked_p_dev(dev) -> dict[str, dict]:
    """STACKED-P v2 on dev, keyed by gold leaf (one query per leaf)."""
    recs = load("OE_stacked_texto_v2.json")
    keep = stacked_p([r["item_key"] for r in recs])
    out = {}
    for r, k in zip(recs, keep):
        if k and r["parent_key"] in dev:
            assert r["gold_item_key"] not in out, "STACKED-P holds two dev queries of one leaf"
            out[r["gold_item_key"]] = r
    return out


@pytest.fixture(scope="module")
def mods() -> dict[str, list[dict]]:
    rows = [json.loads(l) for l in (PROCESSED / "OE_bt_modifications.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["item_key"]: r["modifications"] for r in rows}


def test_population_is_2331_dev_queries_on_40_concepts_paired_to_stacked_p(bt_dev, stacked_p_dev):
    assert len(bt_dev) == 2331
    assert len({r["parent_key"] for r in bt_dev}) == 40
    leaves = {r["gold_item_key"] for r in bt_dev}
    assert len(leaves) == 2331, "one BT query per leaf"
    assert leaves <= set(stacked_p_dev), "every BT dev leaf is a STACKED-P v2 dev leaf"
    assert len(stacked_p_dev) == 2332 and sorted(set(stacked_p_dev) - leaves) == ["OEB160a"]
    for r in bt_dev:
        assert r["item_key"] == r["gold_item_key"] + "_btorigv_en"
        assert r["source_item_key"] == r["gold_item_key"] == stacked_p_dev[r["gold_item_key"]]["gold_item_key"]
        assert r["parent_key"] == stacked_p_dev[r["gold_item_key"]]["parent_key"]


def test_every_bt_leaf_has_an_identity_and_a_texto_u_row(bt_dev, corpus):
    """The identity is each arm's `texto` run on the gold; the S11 arms' identity is their `texto_u` run."""
    u = {r["item_key"] for r in load("OE_texto_u.json")}
    for r in bt_dev:
        assert r["gold_item_key"] in corpus and r["gold_item_key"] in u


def test_item_level_excludes_the_55_d033_golds_and_no_p7_p8_key(bt_dev, stacked_p_dev):
    dup = duplicate_texto()
    excluded = {r["gold_item_key"] for r in bt_dev} & dup
    assert len(excluded) == 55
    assert excluded == {g for g in stacked_p_dev if g in dup} - {"OEB160a"}
    keys = {r["item_key"] for r in bt_dev} | {r["gold_item_key"] for r in bt_dev}
    for name in ("OE_P7_test_exclusion.json", "OE_P8_test_exclusion.json"):
        assert not keys & set(load(name)["item_keys"])


def test_no_bt_dev_text_equals_a_corpus_texto_or_another_dev_query(bt_dev, corpus, stacked_p_dev):
    """S4 work item 4's test: a BT query that equals a leaf's `texto` is the identity, not a rendering."""
    corpus_texts = {collapse(r["text"]) for r in corpus.values()}
    seen: dict[str, str] = {}
    for r in bt_dev:
        t = collapse(r["text"])
        assert t not in corpus_texts, r["item_key"]
        assert t != collapse(corpus[r["gold_item_key"]]["text"])
        assert t not in seen, (r["item_key"], seen.get(t))
        seen[t] = r["item_key"]
    sp_texts = {collapse(q["text"]) for q in stacked_p_dev.values()}
    assert not set(seen) & sp_texts, "a BT query equals a STACKED-P query"


def test_translated_fractions_and_chains(bt_dev):
    fr = [r["bt_sentences"]["fraction"] for r in bt_dev]
    assert sum(f < 0.5 for f in fr) == 522 and sum(f == 0.5 for f in fr) == 1511 and sum(f > 0.5 for f in fr) == 298
    assert round(statistics.mean(fr), 2) == 0.48
    chains = collections.Counter(c for r in bt_dev for c in r["bt_sentences"]["chains"])
    assert chains["en-fr"] > chains["en-it"] and chains["en-fr"] > chains["en-de"]
    assert all(r["bt"]["engine"] == "marian" and r["bt"]["pivot"] == "en" for r in bt_dev)


def test_value_and_glossary_flags(bt_dev, mods):
    vbt = {r["item_key"] for r in bt_dev if "value_back_translation" in r["modification_types"]}
    gs = {r["item_key"] for r in bt_dev if "glossary_synonym" in r["modification_types"]}
    assert len(vbt) == 1855 and len(gs) == 1438 and len(vbt & gs) == 1140
    assert len(bt_dev) - len(vbt | gs) == 178, "pure BT: neither list"
    assert all(set(r["modification_types"]) <= {"back_translation", "value_back_translation", "glossary_synonym"} for r in bt_dev)
    label_added = sum(any(m.get("label_added") for m in mods[r["item_key"]]) for r in bt_dev)
    assert label_added == 97
    for r in bt_dev:
        kinds = {m["type"] for m in mods[r["item_key"]]}
        assert kinds == set(r["modification_types"]), r["item_key"]


def test_bt_parameters_hold_the_golds_values_not_the_variants(bt_dev, corpus, mods):
    """The asymmetry César's ruling rests on: every `value_back_translation` leaves `parameters` at the original."""
    located, variant = 0, 0
    for r in bt_dev:
        values = {str(v) for v in r["parameters"].values() if v is not None}
        # the corpus keeps the nested block per axis; BT's flat value is that block's value string
        nested = corpus[r["gold_item_key"]]["parameters"]
        for axis, v in r["parameters"].items():
            block = nested.get(axis)
            got = {x["value"].strip() for x in block["values"]} if isinstance(block, dict) else set()
            assert (v is None and not got) or (v.strip() in got), (r["item_key"], axis, v, got)
        for m in mods[r["item_key"]]:
            if m["type"] == "value_back_translation":
                located += m["original"] in values
                variant += m["new"] in values and m["new"] != m["original"]
    assert variant == 0 and located > 0


def test_f_bt_1_count_and_coverage(bt_dev, corpus, stacked_p_dev):
    """F-BT-1: «de hormigón» for the gold's «hormigonada» (closed upstream); and BT is the gentler rendering."""
    loose = [r for r in bt_dev if "de hormigón" in r["text"] and "hormigonada" in corpus[r["gold_item_key"]]["text"]]
    fbt1 = [r for r in loose if "hormigonada" not in r["text"]]
    # The design's 1,498 is the substring count; 5 OEB130$ queries keep «canalización hormigonada» and say «de hormigón»
    # only where their gold does («paramentos de hormigón»): not a substitution (audit F6). A4.
    assert len(loose) == 1498 and len(fbt1) == 1493
    assert {r["parent_key"] for r in fbt1} == {"OEB020$", "OEB030$", "OEB230$", "OEB290$"}
    assert {r["parent_key"] for r in loose} - {r["parent_key"] for r in fbt1} == {"OEB130$"}
    cov_bt = statistics.median(lexical_coverage(r["text"], corpus[r["gold_item_key"]]["text"]) for r in bt_dev)
    cov_sp = statistics.median(lexical_coverage(q["text"], corpus[g]["text"]) for g, q in stacked_p_dev.items()
                               if g != "OEB160a")
    assert cov_bt > cov_sp
    assert 0.70 < cov_bt < 0.90 and 0.60 < cov_sp < 0.80
