"""S91's two `resumen` renderings, asserted before any run (S91 work item 4).

The probe measures one thing: what the catalogue's parameter-code suffix does to each arm.
That reading holds only if **nothing but the suffix** differs between the coded, stripped and
decoded query sets. So these tests pin that, at every layer a run reads: the JSON the neural arms
read, and the `_norm` / `_feats` tables the lexical and hybrid arms read.

They also pin the decoder's two properties that make it a deployable component rather than an
oracle: it is keyed on (position, code) alone, never on a concept, and it was fitted on dev only.

`data/processed` is git-ignored, so every test skips in a checkout that lacks it.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from utils.build_resumen_renderings import AXES, MIN_SHARE, dev_concepts, split_suffix
from utils.run_context import QUERY_SETS, load_run_context

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"
MANIFEST = REPO / "docs" / "synthetic-oe" / "MANIFEST.md"

CODED = PROCESSED / "OE_resumen.json"
RENDERINGS = {
    "resumen_decoded": PROCESSED / "OE_resumen_decoded.json",
    "resumen_stripped": PROCESSED / "OE_resumen_stripped.json",
}
TABLE = PROCESSED / "OE_resumen_decoder.json"

#: Columns computed from `text`. Every other column must be identical to the coded tables.
TEXT_DERIVED = {
    "text", "text_norm", "tokens_word", "text_word", "text_char", "numbers", "text_word_params",
    "text_word_phrases_add", "text_word_phrases_replace", "tokens_bigram", "text_word_uni_bi",
    "has_numbers", "tokens_word_bi",
}

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in [CODED, TABLE, *RENDERINGS.values()]),
    reason="data/processed is git-ignored; run build_resumen_renderings.py to create the renderings",
)


def records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def coded() -> list[dict]:
    return records(CODED)


@pytest.fixture(scope="module", params=sorted(RENDERINGS))
def rendering(request) -> tuple[str, list[dict]]:
    return request.param, records(RENDERINGS[request.param])


@pytest.fixture(scope="module")
def table() -> dict:
    return json.loads(TABLE.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- the JSON


def test_every_field_but_the_text_is_the_coded_record(coded, rendering):
    name, rendered = rendering
    assert len(rendered) == len(coded)
    for c, r in zip(coded, rendered):
        assert r["gold_item_key"] == r["item_key"], f"{name}: gold is the leaf itself"
        assert {k: v for k, v in r.items() if k not in ("text", "gold_item_key")} == \
               {k: v for k, v in c.items() if k != "text"}, f"{name}: {c['item_key']} differs off the text"


def test_a_leaf_without_a_suffix_is_identical_in_every_rendering(coded, rendering):
    name, rendered = rendering
    plain = [(c, r) for c, r in zip(coded, rendered) if split_suffix(c["text"]) is None]
    assert plain, "the corpus has leaves without a suffix"
    assert all(c["text"] == r["text"] for c, r in plain), name


def test_the_suffix_is_the_only_thing_that_changes(coded, rendering):
    name, rendered = rendering
    for c, r in zip(coded, rendered):
        parts = split_suffix(c["text"])
        if parts is None:
            continue
        head = parts[0].rstrip()
        assert r["text"].startswith(head), f"{name}: {c['item_key']} changed before its suffix"
        if name == "resumen_stripped":
            assert r["text"] == head


def test_a_decoded_suffix_holds_only_decoder_output(coded, table):
    decoded = records(RENDERINGS["resumen_decoded"])
    outputs = {e["decodes_to"] for e in table["entries"].values()} - {""}
    for c, d in zip(coded, decoded):
        parts = split_suffix(c["text"])
        if parts is None or d["text"] == parts[0].rstrip():
            continue
        suffix = re.search(r"\(([^()]*)\)\s*$", d["text"]).group(1)
        assert set(suffix.split("/")) <= outputs, c["item_key"]


# --------------------------------------------------------------------------- the decoder


def test_the_decoder_is_keyed_on_position_and_code_alone(table):
    for key, entry in table["entries"].items():
        assert key == f"{entry['position']}|{entry['code']}"
        assert entry["axis"] == AXES[entry["position"]]
    assert not re.search(r"OE[A-G]\d{3}", json.dumps(table)), "a concept key in the decoder"


def test_the_decoder_was_fitted_on_dev_only(coded, table):
    """Every dev leaf with a suffix is counted once per position, and nothing else is."""
    dev = dev_concepts()
    dev_with_suffix = sum(
        1 for r in coded if r["parent_key"] in dev and split_suffix(r["text"]) is not None
    )
    for position in range(len(AXES)):
        entries = [e for e in table["entries"].values() if e["position"] == position]
        seen = sum(sum(e["values_on_dev"].values()) + e["axis_absent_on_dev"] for e in entries)
        assert seen == dev_with_suffix, f"position {position}"


def test_amendment_a1_drops_only_oeb160s_two_values(table):
    assert table["min_share"] == MIN_SHARE == 0.01
    ignored = {k: e["ignored_below_min_share"] for k, e in table["entries"].items()
               if e["ignored_below_min_share"]}
    assert ignored == {"2|-": ["Volumen escaso", "Volumen relevante"]}
    assert table["entries"]["2|-"]["decodes_to"] == "Cualquier condición de ejecución"
    assert table["entries"]["0|-"]["decodes_to"] == "Cualquier franja horaria"


# --------------------------------------------------------------------------- the derived tables


@pytest.mark.parametrize("kind,coded_table", [("norm", "OE_short_norm"), ("feats", "OE_short_feats")])
@pytest.mark.parametrize("queryset", sorted(RENDERINGS))
def test_only_text_derived_columns_differ_and_only_on_suffixed_leaves(kind, coded_table, queryset):
    path = PROCESSED / f"OE_{queryset}_{kind}.parquet"
    if not path.exists():
        pytest.skip(f"{path.name} not derived yet; run build_s91_query_tables.py")
    stored = pd.read_parquet(PROCESSED / f"{coded_table}.parquet")
    derived = pd.read_parquet(path)

    assert list(derived["item_key"]) == list(stored["item_key"])
    assert (derived["gold_item_key"] == derived["item_key"]).all()
    assert set(stored.columns) <= set(derived.columns)

    # Off the text, identical: this is what keeps `bm25_unigram_params` the same oracle in every
    # condition (D-010) — its query-side `param_tokens` must not move.
    for column in sorted(set(stored.columns) - TEXT_DERIVED):
        pd.testing.assert_series_equal(derived[column], stored[column], check_names=False, obj=column)

    # On the text, identical wherever the leaf has no suffix.
    plain = derived["text"].map(lambda t: split_suffix(t) is None) & (derived["text"] == stored["text"])
    assert plain.any()
    for column in sorted(set(stored.columns) & TEXT_DERIVED):
        pd.testing.assert_series_equal(derived.loc[plain, column], stored.loc[plain, column],
                                       check_names=False, obj=column)


# --------------------------------------------------------------------------- resolution


@pytest.mark.parametrize("queryset", sorted(RENDERINGS))
@pytest.mark.parametrize("config", [
    "bm25_unigram_params__k1-0.60__b-0.35__OE.yaml",
    "bge_m3_colbert__OE.yaml",
    "dense_es_hiiamsid__OE.yaml",
])
def test_each_arm_resolves_the_renderings_feature_table(queryset, config):
    """Every OE config declares the `feats` input shape, so a rendering resolves to its
    `_feats` table — including for the two BGE-M3 arms, whose declared inputs are `_norm`
    tables. That is how S2's synthetic sets resolved too; the next test is what makes it safe."""
    assert queryset in QUERY_SETS
    ctx = load_run_context(REPO / "configs" / config, queryset=queryset, work_root=REPO,
                           require_inputs=False)
    assert ctx.query_path.name == f"OE_{queryset}_feats.parquet"
    assert ctx.run_dir == REPO / "runs" / "OE" / queryset / ctx.method


@pytest.mark.parametrize("queryset", ["resumen", *sorted(RENDERINGS)])
def test_a_norm_table_is_its_feats_table_minus_columns(queryset):
    """`bge_m3_colbert` and `bge_m3_dense` read `OE_short_norm` for coded `resumen` and a
    `_feats` table for each rendering. The pairing holds only if, for any one rendering, the two
    tables agree on every column `_norm` has: `_feats` must add columns and change none."""
    stem = "OE_short" if queryset == "resumen" else f"OE_{queryset}"
    norm_path, feats_path = PROCESSED / f"{stem}_norm.parquet", PROCESSED / f"{stem}_feats.parquet"
    if not (norm_path.exists() and feats_path.exists()):
        pytest.skip(f"{stem} tables not derived")
    norm, feats = pd.read_parquet(norm_path), pd.read_parquet(feats_path)
    assert set(norm.columns) <= set(feats.columns)
    for column in norm.columns:
        pd.testing.assert_series_equal(feats[column], norm[column], check_names=False, obj=column)


# --------------------------------------------------------------------------- provenance


@pytest.mark.parametrize("name", [
    "OE_resumen_decoded.json", "OE_resumen_stripped.json", "OE_resumen_decoder.json",
    "OE_resumen_decoded_norm.parquet", "OE_resumen_decoded_feats.parquet",
    "OE_resumen_stripped_norm.parquet", "OE_resumen_stripped_feats.parquet",
])
def test_each_s91_input_matches_its_manifest_digest(name):
    path = PROCESSED / name
    if not path.exists():
        pytest.skip(f"{name} not generated")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    row = next((line for line in MANIFEST.read_text(encoding="utf-8").splitlines()
                if line.startswith(f"| `{name}` |")), None)
    assert row is not None, f"{name} has no MANIFEST row"
    assert digest in row, f"{name} is {digest[:16]}, MANIFEST records another digest"
