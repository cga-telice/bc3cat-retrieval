"""The rule-based structured pipeline, ported from `research/structured-retrieval` (D-026).

Three kinds of guarantee. The port did not change the pipeline's behaviour where it claims not
to (ranking tiers, `search` ≡ `search_batch`). It refuses what it does not support instead of
falling back (LLM, oracle, a Stage-1 index over different documents). And, against the real OE
files, its Stages 2 and 3 can read an unmodified leaf back — the structured half of the S2
identity control, checked before any GPU is involved.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from index_builders import structured_pipeline_oracleparams as oracle_builder
from index_builders import structured_pipeline_rules as builder
from pipeline.catalog_lookup import CatalogLookup
from pipeline.param_extractor_oracle import OracleParamsExtractor
from pipeline.param_extractor_rules import RuleBasedParamExtractor
from retrievers import structured_pipeline as sp

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

PORTED = [
    REPO / "src" / "pipeline" / "catalog_lookup.py",
    REPO / "src" / "pipeline" / "param_extractor_rules.py",
    REPO / "src" / "retrievers" / "structured_pipeline.py",
    REPO / "src" / "retrievers" / "structured_pipeline_rules.py",
    REPO / "src" / "index_builders" / "structured_pipeline_rules.py",
]

needs_oe = pytest.mark.skipif(
    not (PROCESSED / "OE_long_norm.parquet").exists(),
    reason="data/processed is git-ignored and absent in this checkout",
)


# ── The port itself ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", PORTED, ids=lambda p: p.name)
def test_ported_code_names_no_collection_file_and_no_src_package(path):
    code = "\n".join(
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    )
    # Strip docstrings, which legitimately describe what the source did.
    code = re.sub(r'"""(.|\n)*?"""', "", code)
    assert not re.search(r"OEB_\w+", code), f"{path.name} still names an OEB file"
    assert "from src." not in code and "import src." not in code


# ── A synthetic three-concept catalogue, no data needed ──────────────────────

SCHEMA = {
    "AAA010$": {
        "concept": "TUBO",
        "axes": {"DIAMETRO": ["20 mm", "40 mm"], "TRABAJO": ["Diurno", "Nocturno"]},
        "item_keys": ["AAA010aa", "AAA010ab", "AAA010ba", "AAA010bb"],
        "num_items": 4,
    },
    "AAA020$": {
        "concept": "ARQUETA",
        "axes": {"TIPO": ["Registro", "Paso"]},
        "item_keys": ["AAA020a", "AAA020b"],
        "num_items": 2,
    },
}
DOCS = ["AAA010aa", "AAA010ab", "AAA010ba", "AAA010bb", "AAA020a", "AAA020b"]


def _axis(label, value):
    return {"label": label, "label_norm": label.lower(),
            "values": [{"label": "a", "value": value, "value_norm": value.lower()}]}


def _long_norm() -> pd.DataFrame:
    rows = []
    for key, (d, t) in zip(DOCS[:4], [("20 mm", "Diurno"), ("20 mm", "Nocturno"),
                                      ("40 mm", "Diurno"), ("40 mm", "Nocturno")]):
        rows.append({"item_key": key, "parent_key": "AAA010$",
                     "parameters_norm": {"A": _axis("DIAMETRO", d), "B": _axis("TRABAJO", t),
                                         "C": None, "D": None, "F": None}})
    for key, t in zip(DOCS[4:], ["Registro", "Paso"]):
        rows.append({"item_key": key, "parent_key": "AAA020$",
                     "parameters_norm": {"A": _axis("TIPO", t),
                                         "B": None, "C": None, "D": None, "F": None}})
    return pd.DataFrame(rows)


class FakeE5:
    """Deterministic Stage 1: scores are fixed per query, so batch and loop must agree."""

    def __init__(self, scores: dict[str, list[float]]):
        self.external_ids = np.asarray(DOCS, dtype=object)
        self._scores = scores

    def _one(self, q, k):
        s = np.asarray(self._scores[q], dtype=np.float32)
        top = np.argsort(-s, kind="stable")[:k]
        return top, s[top]

    def search(self, q, k=100):
        return self._one(q, k)

    def search_batch(self, qs, k=100):
        pairs = [self._one(q, k) for q in qs]
        return np.stack([p[0] for p in pairs]), np.stack([p[1] for p in pairs])


@pytest.fixture()
def catalogue(tmp_path):
    schema = tmp_path / "X_concept_schema.json"
    schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
    long_norm = tmp_path / "X_long_norm.parquet"
    _long_norm().to_parquet(long_norm)
    return schema, long_norm


def _searcher(catalogue, scores):
    schema_path, long_norm = catalogue
    return sp.StructuredPipelineSearcher(
        e5_searcher=FakeE5(scores),
        param_extractor=RuleBasedParamExtractor(schema_path),
        catalog_lookup=CatalogLookup(schema_path, long_norm),
        item_to_parent={k: ("AAA010$" if k.startswith("AAA010") else "AAA020$") for k in DOCS},
        schema=SCHEMA,
    )


QUERIES = {
    "tubo de 40 mm en trabajo nocturno": [0.9, 0.1, 0.2, 0.3, 0.05, 0.04],
    "tubo diurno": [0.2, 0.8, 0.1, 0.3, 0.05, 0.04],
    "arqueta sin mas": [0.1, 0.1, 0.1, 0.1, 0.2, 0.9],
}


def test_ranking_keeps_the_source_three_tiers(catalogue):
    s = _searcher(catalogue, QUERIES)
    idx, sc = s.search("tubo de 40 mm en trabajo nocturno", k=6)
    keys = [DOCS[i] for i in idx]
    assert keys[0] == "AAA010bb" and sc[0] == pytest.approx(1.0)       # tier 1: full match
    assert set(keys[1:4]) == {"AAA010aa", "AAA010ab", "AAA010ba"}       # tier 2: the family
    assert all(0.49 < x <= 0.5 for x in sc[1:4])
    assert set(keys[4:]) == {"AAA020a", "AAA020b"} and all(x < 0.5 for x in sc[4:])

    idx, _ = s.search("tubo diurno", k=6)
    assert {DOCS[i] for i in idx[:2]} == {"AAA010aa", "AAA010ba"}       # partial match → subgroup


def test_search_batch_equals_search_query_by_query(catalogue):
    s = _searcher(catalogue, QUERIES)
    qs = list(QUERIES)
    b_idx, b_sc = s.search_batch(qs, k=5)
    for i, q in enumerate(qs):
        idx, sc = s.search(q, k=5)
        np.testing.assert_array_equal(b_idx[i], idx)
        np.testing.assert_array_equal(b_sc[i], sc)


def _index_tree(tmp_path, *, params, collection="X", e5_docs=DOCS, own_docs=DOCS):
    """A work root laid out the way the resolver lays it out."""
    root = tmp_path / "work"
    data = root / "data" / "processed"
    data.mkdir(parents=True)
    for name in (f"{collection}_resumen.json", f"{collection}_texto.json"):
        (data / name).write_text("[]", encoding="utf-8")
    (data / f"{collection}_concept_schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    _long_norm().to_parquet(data / f"{collection}_long_norm.parquet")

    def mapping(d, docs):
        with open(d / "mapping.jsonl", "w", encoding="utf-8") as f:
            for i, k in enumerate(docs):
                f.write(json.dumps({"doc_id": i, "external_id": k}) + "\n")

    e5 = root / "index" / collection / "e5"
    (e5 / "data").mkdir(parents=True)
    np.save(e5 / "data" / "embeddings.npy", np.eye(len(e5_docs), 4, dtype=np.float32))
    (e5 / "meta.json").write_text(json.dumps({"params": {}}), encoding="utf-8")
    (e5 / "fields.json").write_text(json.dumps({"text_field": "text"}), encoding="utf-8")
    mapping(e5, e5_docs)

    idx = root / "index" / collection / "sp"
    (idx / "data").mkdir(parents=True)
    (idx / "meta.json").write_text(
        json.dumps({"collection": collection, "variant": "sp", "params": params}), encoding="utf-8"
    )
    mapping(idx, own_docs)
    return idx


RULES = {"stage2_method": "rules", "oracle": False, "stage1_index": "e5"}


def test_load_resolves_everything_from_the_index_directory(tmp_path):
    s = sp.load(_index_tree(tmp_path, params=RULES))
    assert list(s.external_ids) == DOCS
    assert s._catalog.value_match == "literal"  # absent means the source's comparison


def test_load_passes_stage3_value_match_to_the_catalogue(tmp_path):
    s = sp.load(_index_tree(tmp_path, params={**RULES, "stage3_value_match": "normalized"}))
    assert s._catalog.value_match == "normalized"


@pytest.mark.parametrize(
    "params, error",
    [
        # S9 work item 4 ports the LLM extractor; what is refused now is any model or mode the
        # design does not fix.
        ({**RULES, "stage2_method": "llm"}, ValueError),
        ({**RULES, "stage2_method": "llm", "llm_model": "llama3.1:8b", "llm_prompt_mode": "extract"}, ValueError),
        ({**RULES, "stage2_method": "gpt"}, NotImplementedError),
        ({**RULES, "oracle": True}, NotImplementedError),
        ({"stage2_method": "rules"}, KeyError),
    ],
    ids=["llm-unfixed", "llm-other-model", "unknown", "oracle", "no-stage1"],
)
def test_load_refuses_what_is_not_ported(tmp_path, params, error):
    with pytest.raises(error):
        sp.load(_index_tree(tmp_path, params=params))


def test_load_fails_loud_when_stage1_lists_other_documents(tmp_path):
    idx = _index_tree(tmp_path, params=RULES, own_docs=list(reversed(DOCS)))
    with pytest.raises(ValueError, match="same order"):
        sp.load(idx)


@pytest.mark.parametrize(
    "params",
    [{**RULES, "stage2_method": "gpt"}, {**RULES, "oracle": True}, {"stage2_method": "rules"},
     {**RULES, "stage3_value_match": "fuzzy"}],
    ids=["unknown-stage2", "oracle", "no-stage1", "unknown-value-match"],
)
def test_builder_refuses_what_is_not_ported(params):
    with pytest.raises(ValueError):
        builder.build({"method": {"params": params}}, pd.DataFrame({"item_key": DOCS}), "text_norm")


# ── Against the real OE files ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def oe():
    long_norm = pd.read_parquet(
        PROCESSED / "OE_long_norm.parquet",
        columns=["item_key", "parent_key", "parameters", "text_norm"],
    )
    schema_path = PROCESSED / "OE_concept_schema.json"
    return long_norm, schema_path


def _gold(parameters) -> dict[str, str]:
    """Axis label → original value, from a corpus row's nested `parameters`."""
    gold = {}
    for axis in parameters.values():
        if axis is None:
            continue
        gold[axis["label"].strip()] = axis["values"][0]["value"].strip()
    return gold


LITERAL_DEFECT = (
    "S2 finding, kept by design (amendment 2026-09-17): value_match='literal' is the source's "
    "comparison, schema 'hasta 0,80 m' against corpus value_norm 'hasta 0.80 m'. 1,640 OE leaves "
    "in OEB190$, OEB200$, OED180$, OEG050$, OEG020$ can never be a Stage-3 match. Inherited from "
    "85c3359, where it already hit 1,080 OEB leaves. structured_pipeline_rules_valuenorm__OE runs "
    "the fixed comparison beside it."
)


@needs_oe
@pytest.mark.parametrize(
    "value_match",
    [pytest.param("literal", marks=pytest.mark.xfail(strict=True, reason=LITERAL_DEFECT)),
     "normalized"],
)
def test_catalogue_lookup_reads_every_leaf_back_from_its_own_values(oe, value_match):
    """Stage 3's identity: a leaf's own schema values select that leaf and nothing else."""
    long_norm, schema_path = oe
    catalog = CatalogLookup(schema_path, PROCESSED / "OE_long_norm.parquet", value_match=value_match)
    wrong = []
    for row in long_norm.itertuples(index=False):
        got = catalog.lookup(row.parent_key, _gold(row.parameters))
        if got != [row.item_key]:
            wrong.append((row.item_key, len(got)))
    assert not wrong, f"{len(wrong)} of {len(long_norm)} leaves not read back, e.g. {wrong[:5]}"


@needs_oe
def test_extractor_on_20_dev_texto_leaves_abstains_but_never_misreads(oe):
    """S2 work item 1, as amended 2026-09-17.

    The frozen test asked for exact recovery. On `texto` that is not attainable by a rules
    extractor — TIPO DE TERRENO is not written literally, ALVEOLOS has no context rule — so
    recovery is *measured* in the stage table (work item 5). What is asserted here is the
    property the port must not break: when the extractor commits to a value on an unmodified
    leaf, it is that leaf's value. Abstaining (None) is allowed; misreading is not.
    """
    from utils.splits import load_split

    long_norm, schema_path = oe
    dev = long_norm[long_norm["parent_key"].isin(load_split("dev"))]
    rows = dev.iloc[sorted(random.Random(20260917).sample(range(len(dev)), 20))]

    extractor = RuleBasedParamExtractor(schema_path)
    misread, abstained = [], 0
    for row in rows.itertuples(index=False):
        # The schema keeps BC3's padding (' Nº TUBOS ', ' i >= 5 horas'); the extractor returns
        # it verbatim and the lookup strips it, so compare stripped.
        got = {a.strip(): (v.strip() if v is not None else None)
               for a, v in extractor.extract(row.parent_key, row.text_norm).items()}
        gold = _gold(row.parameters)
        assert set(got) == set(gold), f"{row.item_key}: axes {set(got)} != {set(gold)}"
        for axis, value in got.items():
            if value is None:
                abstained += 1
            elif value != gold[axis]:
                misread.append((row.item_key, axis, gold[axis], value))
    assert not misread, f"misread axes: {misread}"
    assert abstained > 0  # the finding the amendment rests on; if this flips, re-read it


# ── S5: the oracle-extraction bound ──────────────────────────────────────────


def _record(**axes):
    """A `parameters_norm` row: letter → axis, as on the corpus and query tables."""
    letters = iter("ABCDF")
    rec = {k: None for k in "ABCDF"}
    for label, value in axes.items():
        rec[next(letters)] = _axis(label, value)
    return rec


def _oracle_searcher(catalogue, scores):
    schema_path, long_norm = catalogue
    return sp.StructuredPipelineSearcher(
        e5_searcher=FakeE5(scores),
        param_extractor=OracleParamsExtractor(schema_path),
        catalog_lookup=CatalogLookup(schema_path, long_norm, value_match="normalized"),
        item_to_parent={k: ("AAA010$" if k.startswith("AAA010") else "AAA020$") for k in DOCS},
        schema=SCHEMA,
    )


def _bound(texts, records):
    return pd.DataFrame({"text_norm": texts, "parameters_norm": records})


def test_oracle_reads_the_record_not_the_text(catalogue):
    s = _oracle_searcher(catalogue, QUERIES)
    qs = list(QUERIES)
    # The first query's text says 40 mm / nocturno; its record says 20 mm / diurno. The record wins.
    recs = [_record(DIAMETRO="20 mm", TRABAJO="Diurno"),
            _record(DIAMETRO="2 cm", TRABAJO="Diurno"),        # a rewritten value: abstains
            _record(TIPO="Paso")]
    s.bind_queries(_bound(qs, recs))
    idx, sc = s.search_batch(qs, k=6)
    assert DOCS[idx[0][0]] == "AAA010aa" and sc[0][0] == pytest.approx(1.0)
    assert {DOCS[i] for i in idx[1][:2]} == {"AAA010aa", "AAA010ba"}   # DIAMETRO abstained
    assert all(sc[1][:2] > 0.9)
    assert DOCS[idx[2][0]] == "AAA020b"


def test_oracle_extractor_keeps_schema_spelling_and_abstains_off_schema(catalogue):
    schema_path, _ = catalogue
    o = OracleParamsExtractor(schema_path)
    assert o.extract("AAA010$", _record(DIAMETRO="20 MM", TRABAJO="nocturno")) == {
        "DIAMETRO": "20 mm", "TRABAJO": "Nocturno"}
    assert o.extract("AAA010$", _record(DIAMETRO="veinte mm")) == {"DIAMETRO": None, "TRABAJO": None}
    # Stage 1 chose another concept: labels it lacks contribute nothing.
    assert o.extract("AAA020$", _record(DIAMETRO="20 mm")) == {"TIPO": None}


def test_oracle_refuses_unbound_or_misaligned_queries(catalogue):
    s = _oracle_searcher(catalogue, QUERIES)
    qs = list(QUERIES)
    with pytest.raises(RuntimeError, match="bind_queries"):
        s.search_batch(qs, k=5)
    s.bind_queries(_bound(qs, [_record(TIPO="Paso")] * 3))
    with pytest.raises(ValueError, match="in order"):
        s.search_batch(list(reversed(qs)), k=5)
    with pytest.raises(RuntimeError, match="record"):
        s.search(qs[0], k=5)


def test_bind_queries_is_a_no_op_for_the_rules_arm(catalogue):
    s = _searcher(catalogue, QUERIES)
    s.bind_queries(pd.DataFrame({"unrelated": [1]}))
    s.search_batch(list(QUERIES), k=5)


def test_load_and_builder_accept_oracle_params(tmp_path):
    params = {**RULES, "stage2_method": "oracle_params", "stage3_value_match": "normalized"}
    s = sp.load(_index_tree(tmp_path, params=params))
    assert isinstance(s._extractor, OracleParamsExtractor)
    oracle_builder.build({"method": {"params": params}}, pd.DataFrame({"item_key": DOCS}), "text_norm")


# Four `synonym_label` dev queries differ from their gold only in letter case (DATASET_DEFECTS
# P8, D-044): normalised, their "rewritten" value is the schema value, so nothing abstains.
P8_DEV = {"OED010bkabc_syn_85a4f552cd1b", "OED030babca_syn_609ea3a72274",
          "OED050bcbdc_syn_c59e212d9862", "OED080bhbda_syn_7575e67f784b"}
L1 = {"synonym_label", "num_to_text", "unit_expansion", "unit_conversion"}


@needs_oe
def test_oracle_on_20_dev_texto_leaves_selects_the_gold_alone():
    """S5 work item 3: on identity the record is the gold's fingerprint."""
    from utils.splits import load_split

    feats = pd.read_parquet(PROCESSED / "OE_long_feats.parquet",
                            columns=["item_key", "parent_key", "parameters_norm"])
    dev = feats[feats["parent_key"].isin(load_split("dev"))]
    rows = dev.iloc[sorted(random.Random(20260930).sample(range(len(dev)), 20))]
    schema = PROCESSED / "OE_concept_schema.json"
    o = OracleParamsExtractor(schema)
    catalog = CatalogLookup(schema, PROCESSED / "OE_long_norm.parquet", value_match="normalized")
    for row in rows.itertuples(index=False):
        got = o.extract(row.parent_key, row.parameters_norm)
        assert None not in got.values(), f"{row.item_key}: {got}"
        assert catalog.lookup(row.parent_key, got) == [row.item_key]


@needs_oe
def test_oracle_on_20_dev_l1_queries_abstains_on_exactly_one_axis():
    """S5 work item 3: on L1 the rewritten axis, and only it, abstains; nothing is misread."""
    from utils.splits import load_split

    q = pd.read_parquet(PROCESSED / "OE_single_texto_feats.parquet",
                        columns=["item_key", "gold_item_key", "parent_key", "parameters_norm",
                                 "modification_types"])
    q = q[q["parent_key"].isin(load_split("dev"))
          & q["modification_types"].map(lambda t: set(t) <= L1)
          & ~q["item_key"].isin(P8_DEV)]
    rows = q.iloc[sorted(random.Random(20260930).sample(range(len(q)), 20))]
    gold_rec = pd.read_parquet(PROCESSED / "OE_long_feats.parquet",
                               columns=["item_key", "parameters_norm"]).set_index("item_key")
    schema = PROCESSED / "OE_concept_schema.json"
    o = OracleParamsExtractor(schema)
    catalog = CatalogLookup(schema, PROCESSED / "OE_long_norm.parquet", value_match="normalized")
    for row in rows.itertuples(index=False):
        got = o.extract(row.parent_key, row.parameters_norm)
        gold = o.extract(row.parent_key, gold_rec.loc[row.gold_item_key, "parameters_norm"])
        abstained = [a for a, v in got.items() if v is None and gold[a] is not None]
        misread = [a for a, v in got.items() if v is not None and v != gold[a]]
        assert len(abstained) == 1 and not misread, f"{row.item_key}: {abstained} {misread}"
        assert row.gold_item_key in catalog.lookup(row.parent_key, got)
