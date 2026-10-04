"""S11 work item 1: the harness pieces the two-stage arms stand on.

(a) D-056's label stripping. The tolerant key match S9 added for A7 (`llm_key_match: tolerant`) is the rule S11
registers. Pinned here: it resolves padded schema names, and, on the cached generations, the harness's own
`_lookup` resolves exactly the axes A7's table counts as exact + trimmed + renamed, per base
(`results/S9/extraction.md`). The comparison runs through `_lookup` itself, not a re-implementation of it.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from pipeline.param_extractor import LLMParamExtractor
from pipeline.prompts import build_extraction_prompt

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "processed"
RUNS = REPO / "runs" / "OE"
EXTRACTION_MD = REPO / "docs" / "synthetic-oe" / "results" / "S9" / "extraction.md"
LLM_ARM = "structured_pipeline_llm_valuenorm__OE"
BASES = ("texto_u", "resumen_u", "single_texto", "single_l2_texto", "stacked_texto")

needs_data = pytest.mark.skipif(
    not (DATA / "llm_cache" / "structured_llm_extract.jsonl").exists() or not (RUNS / "texto_u" / LLM_ARM).exists(),
    reason="data/processed or runs absent",
)

_FOUND = object()


def resolves(parsed: dict, axis: str) -> bool:
    """Whether the tolerant extractor finds `axis` among the response's keys, whatever the value is."""
    ex = LLMParamExtractor.__new__(LLMParamExtractor)
    ex._key_match = "tolerant"
    return ex._lookup({k: _FOUND for k in parsed}, axis) is _FOUND


def test_tolerant_match_resolves_padded_and_renamed_axis_names():
    parsed = {"BANDA_DE_MANTENIMIENTO": "x", "condiciones de ejecución": "y", "DIMENSIONES": "z"}
    assert resolves(parsed, " BANDA DE MANTENIMIENTO ")
    assert resolves(parsed, "CONDICIONES DE EJECUCION ")
    assert resolves(parsed, "DIMENSIONES")
    assert not resolves(parsed, "TRABAJO")


def a7_counts() -> dict[str, int]:
    """exact + trimmed + renamed per base, read from the generated S9 table."""
    out = {}
    for line in EXTRACTION_MD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| `(\w+)` \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| [\d,]+ \(", line)
        if m and m.group(1) in BASES:
            n = [int(x.replace(",", "")) for x in m.groups()[1:]]
            out[m.group(1)] = n[1] + n[2] + n[3]
    return out


@needs_data
def test_harness_resolves_the_axes_a7_counted():
    import pandas as pd
    from query_rewrite import llm as L
    from utils.build_results_s7 import iter_top100
    from utils.build_results_s9 import PHI4_DIGEST

    expected = a7_counts()
    assert set(expected) == set(BASES)
    schema = json.loads((DATA / "OE_concept_schema.json").read_text(encoding="utf-8"))
    parents = {r["item_key"]: r["parent_key"] for r in json.loads((DATA / "OE_texto.json").read_text(encoding="utf-8"))}
    cache = {}
    for line in (DATA / "llm_cache" / "structured_llm_extract.jsonl").read_text(encoding="utf-8").splitlines():
        if line:
            r = json.loads(line)
            cache[r["cache_key"]] = r["response"]
    got = Counter()
    for base in BASES:
        feats = pd.read_parquet(DATA / f"OE_{base}_feats.parquet", columns=["item_key", "text_norm"]).set_index("item_key")
        for r in iter_top100(RUNS / base / LLM_ARM):
            k = str(r["query_item_key"])
            g = schema[parents[str(r["candidates"][0]["index_item_key"])]]
            prompt = build_extraction_prompt(g["concept"], g["axes"], feats.loc[k, "text_norm"])
            ck = L.sha256_text(json.dumps([PHI4_DIGEST, L.OPTIONS, None, prompt], ensure_ascii=False, sort_keys=True))
            parsed = LLMParamExtractor._parse_json_response(cache[ck]) or {}
            got[base] += sum(resolves(parsed, axis) for axis in g["axes"])
    assert dict(got) == expected


# (b) the within-family ColBERT scorer, without a server or a GPU.

import numpy as np  # noqa: E402

from rerankers import colbert_family as cf  # noqa: E402


class FakeSearcher:
    """Encodes a text as a 1x2 matrix that depends on the block it is encoded in, as the server's does."""

    def __init__(self, docs):
        self.docs = docs
        self.blocks = []

    def _encode_queries(self, texts):
        self.blocks.append(list(texts))
        return [np.array([[float(len(t)), float(len(texts))]], dtype=np.float32) for t in texts]

    def _maxsim_cpu_one(self, Q, doc_ids):
        return np.array([float((Q @ self.docs[int(d)].T).max(axis=1).sum()) for d in doc_ids], dtype=np.float32)


def fake():
    docs = {i: np.array([[1.0, float(i)]], dtype=np.float32) for i in range(6)}
    return FakeSearcher(docs), {"A$": np.array([0, 1, 2]), "B$": np.array([3, 4, 5])}


def test_families_from_mapping_is_doc_id_order():
    fams = cf.families_from_mapping(["a1", "b1", "a2"], {"a1": "A$", "a2": "A$", "b1": "B$"})
    assert fams["A$"].tolist() == [0, 2] and fams["B$"].tolist() == [1]


def test_queries_are_encoded_in_the_run_blocks_even_when_skipped():
    s, fams = fake()
    texts = ["q0", "q11", "q222", "q3333", "q4"]
    concepts = [("A$",), (), ("A$", "B$"), (), ()]
    out = cf.score_in_run_blocks(s, fams, texts, concepts, block=2, use_gpu=False)
    assert s.blocks == [["q0", "q11"], ["q222", "q3333"]]          # the last block has nothing to score
    assert out[1] is None and out[3] is None and out[4] is None
    assert set(out[2]) == {"A$", "B$"}
    q2 = np.array([[4.0, 2.0]], dtype=np.float32)                 # encoded inside its block of two
    assert out[2]["B$"][1].tolist() == s._maxsim_cpu_one(q2, [3, 4, 5]).tolist()


def test_store_round_trip_and_fail_loud(tmp_path):
    s, fams = fake()
    texts = ["q0", "q11"]
    out = cf.score_in_run_blocks(s, fams, texts, [("A$", "B$"), ("B$",)], use_gpu=False)
    assert cf.write_store(tmp_path / "x.npz", texts, out) == 3
    store = cf.FamilyScoreStore(tmp_path, fams)
    fam, sc = store.require("q11", "B$")
    assert fam.tolist() == [3, 4, 5] and sc.tolist() == out[1]["B$"][1].tolist()
    with pytest.raises(KeyError):
        store.require("q11", "A$")
    with pytest.raises(ValueError):
        cf.FamilyScoreStore(tmp_path, {"A$": np.array([0, 1]), "B$": fams["B$"]}).require("q0", "A$")


def test_verify_counts_every_family_leaf_in_the_run_top100():
    scored = [{"A$": (np.array([0, 1, 2]), np.array([1.0, 2.0, 3.0], dtype=np.float32))}, None]
    run = [{"candidates": [{"doc_id": 2, "score": 3.0}, {"doc_id": 1, "score": 2.5}, {"doc_id": 9, "score": 9.0}]},
           {"candidates": []}]
    assert cf.verify_against_run(scored, run) == {"queries": 1, "compared": 2, "mismatched": 1, "max_abs_diff": 0.5}
