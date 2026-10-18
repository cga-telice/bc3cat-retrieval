"""The 2026-10-16 delivery, asserted rather than trusted: v2 of the four query sets, and `bt_texto`.

Upstream's handoff note (`bc3cat-dataset/docs/synthetic/HANDOFF_retrieval_2026-10-16.md`, `2677ced6`) makes
claims that are load-bearing for every amendment that re-runs a closed sprint on v2, and for the BT sprint:

**v2 moves only `text`, and only where it says.** Same n, same `id` / `item_key` / `gold_item_key` in the same
order as v1; `text` differs exactly on the queries `OE_v2_changes.jsonl` lists (STACKED 2,039 of 4,998, SINGLE
241 of 4,439, dose 547 of 3,000, isolated 348 of 5,400), where the file's `old` is v1's text and `new` is v2's.
Every changed query carries `template_paraphrase`. If any of this failed, a v2 table could not be read as v1
with 163 paraphrases repaired, and the v1 / v2 sensitivity reading (D-061) would compare two populations.

**The derived tables inherit that exactly.** `build_v2_query_tables.py` proves the v1 path on every v1 set
before writing; here the v2 tables are required to equal the v1 tables on every unchanged row, column for
column, and to differ on the changed rows only in columns derived from `text`.

**BT is paired to STACKED-P leaf for leaf.** 4,670 queries, one per leaf, each the back-translation of the
gold `texto` whose SHA-256 the record stamps — checked against this tree's corpus, not against the upstream
copy the BT was built from (that copy, `54c83faa…`, carries the `duplicate_texto_group` field refused here
under D-033; its texts are the same, which is what the per-record digest shows). All 4,670 golds are
STACKED-P leaves; 4 STACKED-P leaves have no BT query; 79 concepts, 40 dev / 39 test.

**STACKED-P is a filter on `item_key`**, the same 324 keys on v1 and v2: 321 carry one of the 14 known drift
rewrites, 2 duplicate a delivered query, 1 is degenerate. 189 are dev, 135 test.

Text is read on both splits here only to compare v1 with v2 and BT with its own gold (operating rule 2 forbids
*reading test queries to tune*; a byte comparison tunes nothing). `data/processed` is git-ignored, so every
test skips in a checkout that lacks it.
"""

from __future__ import annotations

import collections
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import pytest

from utils.exclusions import stacked_p, stacked_p_excluded
from utils.run_context import BT_QUERY_SETS, QUERY_SETS, STACKED_P_SETS, V2_QUERY_SETS, data_paths
from utils.splits import load_split

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

#: Digests from the handoff note §1 and upstream's `MANIFEST.md`, re-hashed here at copy time.
EXPECTED = {
    "OE_stacked_texto_v2.json": "bc1ed968f60933d9c63270e6050de0f4cf3ed758614e7d8549256f1fd9fcb7f1",
    "OE_single_texto_v2.json": "b3c58fcb38fd294f817b90a206f2b5ca73644af6987ac3c24d9edd65379af1ae",
    "OE_dose_texto_v2.json": "8becd49ad0fd1f37a18f060c66af46438ea7f530ade15f53ac88c05ce40a1985",
    "OE_isolated_texto_v2.json": "95c0c2edaef0c7dc54721533feae97c8dd9d3159a572bd7cb11315190514b271",
    "OE_v2_changes.jsonl": "981896771092f6a957fa4c3dc507c7d715e88933814753df58ee2adbe75cfe0e",
    "OE_v2_provenance.json": "1c9e4d6db1a7569b20789c0a52fa98bd1706cfe3b7c8ca0cae6af8ece6d4e96e",
    "OE_bt_texto.json": "421b3ca3a3d3f61f26d4653b3f84e4a614ff2dc6ade7acfb4a8f3da1da7d408c",
    "OE_bt_modifications.jsonl": "c1ffe3bfafa2736dcc7ab2444bfdedc046fc0a42a3ac9e7ffa14f715b109738a",
    "OE_bt_provenance.json": "d17653030a0b0cc320babffad9e0322a3259bc9ee07db608b97751516da01f33",
    "OE_stacked_P_exclusion.json": "bbe36522fdccb4fabb526a8ee029ccd5494c2f60c4b5dd87d036ab3e3f9c69c1",
    "OE_known_drift_rewrites.json": "1431f19dfb4791f22ac4a1b8be6779ff6f6d0fe89c12362932474d6cae0dc759",
}
#: The v1 files the v2 sets are compared with; unchanged by the delivery (`MANIFEST.md`).
V1 = {
    "stacked": ("OE_stacked_texto", 4998, 2039),
    "single": ("OE_single_texto", 4439, 241),
    "dose": ("OE_dose_texto", 3000, 547),
    "isolated": ("OE_isolated_texto", 5400, 348),
}
#: Columns a `text` change must not touch in a derived table.
TEXT_INDEPENDENT = {
    "id", "item_key", "parent_key", "ud", "concept", "parameters", "gold_item_key", "modification_types",
    "modification_count", "texto_modification_types", "texto_modification_count", "applicable_types",
    "parameters_norm", "param_values_multi_norm", "param_tokens", "param_phrases",
}

pytestmark = pytest.mark.skipif(
    not all((PROCESSED / n).exists() for n in EXPECTED) or not (PROCESSED / "OE_texto.json").exists(),
    reason="data/processed is git-ignored and absent in this checkout",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(name: str):
    return json.loads((PROCESSED / name).read_text(encoding="utf-8"))


def round_trip(frame: pd.DataFrame) -> pd.DataFrame:
    """As `same_content` compares: after a parquet round trip, so nested dicts serialise the same way."""
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    buffer.seek(0)
    return pd.read_parquet(buffer).reset_index(drop=True)


@pytest.fixture(scope="module")
def dev() -> frozenset[str]:
    return load_split("dev")


@pytest.fixture(scope="module")
def test_split() -> frozenset[str]:
    return load_split("test")


@pytest.fixture(scope="module")
def corpus() -> dict[str, dict]:
    return {r["item_key"]: r for r in load("OE_texto.json")}


@pytest.fixture(scope="module")
def changes() -> list[dict]:
    return [json.loads(l) for l in (PROCESSED / "OE_v2_changes.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture(scope="module")
def sets() -> dict[str, tuple[list[dict], list[dict]]]:
    return {s: (load(f"{stem}.json"), load(f"{stem}_v2.json")) for s, (stem, _, _) in V1.items()}


@pytest.fixture(scope="module")
def bt() -> list[dict]:
    return load("OE_bt_texto.json")


@pytest.fixture(scope="module")
def stacked_v2(sets) -> list[dict]:
    return sets["stacked"][1]


@pytest.fixture(scope="module")
def exclusion() -> dict:
    return load("OE_stacked_P_exclusion.json")


# --------------------------------------------------------------------------- the files are what they say


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_digest_matches_the_handoff_note(name):
    assert sha256(PROCESSED / name) == EXPECTED[name]


def test_the_v1_files_are_unchanged():
    """The handoff rule: delivered files are immutable, v1 stays byte for byte (`MANIFEST.md` prefixes)."""
    for stem, prefix in [
        ("OE_stacked_texto", "c34a222ae2af05a0"), ("OE_single_texto", "b6a43961295cc2ca"),
        ("OE_dose_texto", "555fab84d134886f"), ("OE_isolated_texto", "054041ff05349fae"),
        ("OE_texto", "02a2c270d7ffe147"),
    ]:
        assert sha256(PROCESSED / f"{stem}.json").startswith(prefix), stem


def test_the_provenance_files_name_these_digests():
    v2 = load("OE_v2_provenance.json")
    for name, digest in v2["files"].items():
        assert EXPECTED[name] == digest, name
    for name, digest in v2["inputs_sha256"].items():
        assert sha256(PROCESSED / name) == digest, name
    assert v2["changed_queries"] == {"stacked": 2039, "single": 241, "dose": 547, "isolated": 348}
    assert v2["repaired"]["paraphrases"] == 163
    bt_prov = load("OE_bt_provenance.json")
    for name, digest in bt_prov["files"].items():
        assert EXPECTED[name] == digest, name
    assert bt_prov["counts"] == {"queries": 4670, "concepts": 79, "with_value_bt": 3787, "with_glossary_synonym": 2898}
    assert bt_prov["inputs_sha256"]["OE_stacked_texto.json"].startswith("c34a222ae2af05a0")


# --------------------------------------------------------------------------- registration


def test_the_new_sets_are_registered_and_resolve():
    assert V2_QUERY_SETS == ("stacked_texto_v2", "single_texto_v2", "dose_texto_v2", "isolated_texto_v2")
    assert BT_QUERY_SETS == ("bt_texto",)
    assert set(V2_QUERY_SETS) | set(BT_QUERY_SETS) <= set(QUERY_SETS)
    assert len(set(QUERY_SETS)) == len(QUERY_SETS)
    assert STACKED_P_SETS == ("stacked_texto", "stacked_texto_v2")
    paths = data_paths("OE", work_root=REPO)
    for name in V2_QUERY_SETS + BT_QUERY_SETS:
        assert paths.query_json[name] == PROCESSED / f"OE_{name}.json"
        assert paths.query_norm[name].exists() and paths.query_feats[name].exists(), name


# --------------------------------------------------------------------------- v2: only `text`, only where listed


@pytest.mark.parametrize("s", sorted(V1))
def test_v2_keeps_every_record_in_order_and_changes_only_text(s, sets):
    v1, v2 = sets[s]
    _, n, _ = V1[s]
    assert len(v1) == len(v2) == n
    for field in ("id", "item_key", "gold_item_key", "parent_key"):
        assert [r[field] for r in v1] == [r[field] for r in v2], field
    not_text = [i for i, (a, b) in enumerate(zip(v1, v2))
                if {k: v for k, v in a.items() if k != "text"} != {k: v for k, v in b.items() if k != "text"}]
    assert not_text == [], f"{s}: a field other than text differs in {len(not_text)} records"
    assert set(v1[0]) == set(v2[0])


@pytest.mark.parametrize("s", sorted(V1))
def test_text_changes_exactly_on_the_listed_queries(s, sets, changes):
    v1, v2 = sets[s]
    _, _, expected = V1[s]
    listed = {c["item_key"]: c for c in changes if c["set"] == s}
    assert len(listed) == expected
    changed = [(a, b) for a, b in zip(v1, v2) if a["text"] != b["text"]]
    assert {b["item_key"] for _, b in changed} == set(listed)
    for a, b in changed:
        assert listed[b["item_key"]]["old"] == a["text"] and listed[b["item_key"]]["new"] == b["text"], b["item_key"]
        assert "template_paraphrase" in b["modification_types"], b["item_key"]
        assert "�" not in b["text"]


def test_the_change_file_names_163_paraphrases_and_3175_queries(changes):
    assert len(changes) == 3175
    assert len({c["paraphrase_id"] for c in changes}) == 163
    assert collections.Counter(c["set"] for c in changes) == {"stacked": 2039, "single": 241, "dose": 547, "isolated": 348}


def test_where_the_changes_fall(sets, changes, dev):
    """Pinned for the amendments: dev / test counts, the SINGLE cell, the E3 rungs and concepts."""
    changed = {s: {c["item_key"] for c in changes if c["set"] == s} for s in V1}
    by_split = {s: collections.Counter("dev" if r["parent_key"] in dev else "test" for r in v2 if r["item_key"] in changed[s])
                for s, (_, v2) in sets.items()}
    assert by_split["stacked"] == {"dev": 1183, "test": 856}
    assert by_split["single"] == {"dev": 145, "test": 96}
    assert by_split["dose"] == {"dev": 337, "test": 210}
    assert by_split["isolated"] == {"dev": 214, "test": 134}
    # SINGLE: the changed queries are all the `template_paraphrase` cell's (241 of 600; 145 of 302 on dev).
    single = sets["single"][1]
    assert all(r["modification_types"] == ["template_paraphrase"] for r in single if r["item_key"] in changed["single"])
    assert sum(r["modification_types"] == ["template_paraphrase"] for r in single) == 600
    assert sum(r["modification_types"] == ["template_paraphrase"] and r["parent_key"] in dev for r in single) == 302
    # isolated: all `template_paraphrase` (348 of 600; 214 of 328 on dev).
    iso = sets["isolated"][1]
    assert all(r["modification_types"] == ["template_paraphrase"] for r in iso if r["item_key"] in changed["isolated"])
    assert sum(r["modification_types"] == ["template_paraphrase"] and r["parent_key"] in dev for r in iso) == 328
    # dose: changed per rung 34 / 69 / 114 / 158 / 172 of 70 / 140 / 211 / 279 / 300 with the type.
    dose = sets["dose"][1]
    assert sorted(collections.Counter(r["modification_count"] for r in dose if r["item_key"] in changed["dose"]).items()) == \
        [(1, 34), (2, 69), (3, 114), (4, 158), (5, 172)]
    assert sorted(collections.Counter(r["modification_count"] for r in dose if "template_paraphrase" in r["modification_types"]).items()) == \
        [(1, 70), (2, 140), (3, 211), (4, 279), (5, 300)]
    assert sorted(collections.Counter(r["modification_count"] for r in dose if r["item_key"] in changed["dose"] and r["parent_key"] in dev).items()) == \
        [(1, 23), (2, 46), (3, 72), (4, 95), (5, 101)]
    # the E3 concepts: all seven, 4 dev / 3 test.
    for s in ("dose", "isolated"):
        concepts = {r["parent_key"] for r in sets[s][1] if r["item_key"] in changed[s]}
        assert concepts == {"OEB020$", "OEB030$", "OEB040$", "OEB230$", "OEB280$", "OEB290$", "OEB300$"}
    assert len({r["parent_key"] for r in sets["stacked"][1] if r["item_key"] in changed["stacked"]}) == 46
    assert len({r["parent_key"] for r in single if r["item_key"] in changed["single"]}) == 31


@pytest.mark.parametrize("s", sorted(V1))
def test_no_v2_dev_query_is_undecidable(s, sets, corpus, dev):
    """S4 work item 4's test, on v2: no dev query equals a leaf's `texto`, none shares its text with a query of
    another gold (a repair could in principle have produced a sibling's rendering, as P7 did)."""
    v2 = [r for r in sets[s][1] if r["parent_key"] in dev]
    texts = {r["text"] for r in corpus.values()}
    # P7 (`DATASET_DEFECTS.md`): the one `reorder` query of v1 that renders a sibling's `texto` is untouched by
    # the repair, since it carries no template paraphrase; it stays excluded at item level, and is the only one.
    assert [r["item_key"] for r in v2 if r["text"] in texts] == (["OEC140baa_syn_74d5dd2c9da3"] if s == "single" else [])
    golds_by_text = collections.defaultdict(set)
    for r in v2:
        golds_by_text[r["text"]].add(r["gold_item_key"])
    assert sum(len(g) > 1 for g in golds_by_text.values()) == 0


# --------------------------------------------------------------------------- v2 tables


@pytest.mark.parametrize("s", sorted(V1))
def test_v2_tables_equal_v1_tables_on_every_unchanged_row(s, changes):
    stem, n, expected = V1[s]
    changed = {c["item_key"] for c in changes if c["set"] == s}
    for kind in ("norm", "feats"):
        v1 = round_trip(pd.read_parquet(PROCESSED / f"{stem}_{kind}.parquet"))
        v2 = round_trip(pd.read_parquet(PROCESSED / f"{stem}_v2_{kind}.parquet"))
        assert len(v1) == len(v2) == n and list(v1.columns) == list(v2.columns)
        assert list(v1["item_key"]) == list(v2["item_key"])
        mask = v2["item_key"].isin(changed)
        assert int(mask.sum()) == expected
        pd.testing.assert_frame_equal(v1[~mask].reset_index(drop=True), v2[~mask].reset_index(drop=True), check_dtype=False)
        moved = {c for c in v1.columns if not v1.loc[mask, c].astype(str).equals(v2.loc[mask, c].astype(str))}
        assert "text" in moved and not moved & TEXT_INDEPENDENT, f"{stem}_{kind}: changed rows moved {sorted(moved)}"


# --------------------------------------------------------------------------- STACKED-P


def test_stacked_p_is_324_keys_of_stacked_with_the_stated_reasons(exclusion, stacked_v2, dev, test_split):
    keys = exclusion["item_keys"]
    assert len(keys) == len(set(keys)) == 324 and stacked_p_excluded() == frozenset(keys)
    stacked_keys = {r["item_key"] for r in stacked_v2}
    assert set(keys) <= stacked_keys
    reasons = collections.Counter(v["reason"] for v in exclusion["details"].values())
    assert reasons["known_drift"] == 321 and reasons["duplicate_of_delivered"] == 2 and sum(reasons.values()) == 324
    by_split = collections.Counter("dev" if r["parent_key"] in dev else "test" for r in stacked_v2 if r["item_key"] in set(keys))
    assert by_split == {"dev": 189, "test": 135}
    kept = [r for r, keep in zip(stacked_v2, stacked_p(r["item_key"] for r in stacked_v2)) if keep]
    assert len(kept) == 4674 == len({r["gold_item_key"] for r in kept})
    assert len({r["parent_key"] for r in kept}) == 81


def test_the_14_drift_rewrites_are_the_321_drift_exclusions(exclusion, stacked_v2):
    drift = load("OE_known_drift_rewrites.json")
    assert len(drift) == 14 and collections.Counter(d["type"] for d in drift) == {"paraphrase": 8, "expansion": 6}
    queries = [q for d in drift for q in d["queries"]]
    assert len(queries) == len(set(queries)) == 321
    assert set(queries) == {k for k, v in exclusion["details"].items() if v["reason"] == "known_drift"}
    text_of = {r["item_key"]: r["text"] for r in stacked_v2}
    assert all(d["new"] in text_of[q] for d in drift for q in d["queries"]), "a drift rewrite is not in its v2 query"


# --------------------------------------------------------------------------- BT


def test_bt_is_one_query_per_stacked_p_leaf_paired_by_gold(bt, stacked_v2, corpus, dev, test_split):
    assert len(bt) == 4670
    assert len({r["id"] for r in bt}) == len({r["item_key"] for r in bt}) == len({r["gold_item_key"] for r in bt}) == 4670
    for r in bt:
        assert r["gold_item_key"] in corpus and corpus[r["gold_item_key"]]["parent_key"] == r["parent_key"]
        assert r["source_item_key"] == r["gold_item_key"] and r["item_key"] == r["gold_item_key"] + "_btorigv_en"
        assert r["condition"] == "bt_origv_en"
        assert hashlib.sha256(corpus[r["gold_item_key"]]["text"].encode("utf-8")).hexdigest() == r["source_text_sha256"]
    kept = [r for r, keep in zip(stacked_v2, stacked_p(r["item_key"] for r in stacked_v2)) if keep]
    p_leaves = {r["gold_item_key"] for r in kept}
    bt_leaves = {r["gold_item_key"] for r in bt}
    assert bt_leaves <= p_leaves
    assert sorted(p_leaves - bt_leaves) == ["OEB160a", "OEE020bca", "OEE020bda", "OEE020cab"]
    concepts = {r["parent_key"] for r in bt}
    assert len(concepts) == 79 and len(concepts & dev) == 40 and len(concepts & test_split) == 39
    assert sorted({r["parent_key"] for r in corpus.values()} - concepts) == ["OEB160$", "OEB310$", "OEC140$", "OEE020$"]
    assert collections.Counter("dev" if r["parent_key"] in dev else "test" for r in bt) == {"dev": 2331, "test": 2339}


def test_bt_text_is_new_and_decidable(bt, corpus, sets):
    texts = {r["text"] for r in corpus.values()}
    delivered = {r["text"] for v1, v2 in sets.values() for r in v1 + v2} | {r["text"] for r in load("OE_single_l2_texto.json")}
    assert sum(r["text"] in texts for r in bt) == 0
    assert sum(r["text"] in delivered for r in bt) == 0
    assert len({r["text"] for r in bt}) == 4670
    assert sum("�" in r["text"] for r in bt) == 0


def test_bt_modifications_and_sidecar(bt):
    allowed = {"back_translation", "value_back_translation", "glossary_synonym"}
    for r in bt:
        assert set(r["modification_types"]) <= allowed and "back_translation" in r["modification_types"]
        assert r["modification_count"] == len(r["modification_types"])
        assert r["texto_modification_types"] == r["modification_types"]
        assert r["texto_modification_count"] == r["modification_count"]
        assert 0 <= r["bt_sentences"]["fraction"] <= 1 and r["bt_sentences"]["total"] > 0
        assert all(not isinstance(v, (dict, list)) for v in r["parameters"].values()), "BT parameters are flat, as STACKED's"
    assert sum("value_back_translation" in r["modification_types"] for r in bt) == 3787
    assert sum("glossary_synonym" in r["modification_types"] for r in bt) == 2898
    mean_fraction = sum(r["bt_sentences"]["fraction"] for r in bt) / len(bt)
    assert abs(mean_fraction - 0.48) < 0.01
    sidecar = [json.loads(l) for l in (PROCESSED / "OE_bt_modifications.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert [s["item_key"] for s in sidecar] == [r["item_key"] for r in bt]
    for s, r in zip(sidecar, bt):
        assert {m["type"] for m in s["modifications"]} == set(r["modification_types"])


def test_bt_table_is_the_json_row_for_row(bt):
    for kind in ("norm", "feats"):
        frame = pd.read_parquet(PROCESSED / f"OE_bt_texto_{kind}.parquet")
        assert len(frame) == 4670
        assert list(frame["item_key"]) == [r["item_key"] for r in bt]
        assert list(frame["gold_item_key"]) == [r["gold_item_key"] for r in bt]
        assert list(frame["text"]) == [r["text"] for r in bt]
        assert list(frame["source_item_key"]) == [r["source_item_key"] for r in bt]
        assert set(frame["condition"]) == {"bt_origv_en"}
        assert list(frame["modification_count"]) == [r["modification_count"] for r in bt]


def test_bt_carries_the_55_duplicate_golds_and_no_p7_p8_key(bt):
    """D-033 applies as everywhere: those 55 are excluded at item level, kept at parent level."""
    groups = load("OE_duplicate_texto_groups.json")["groups"]
    flagged = {m for members in groups.values() for m in members}
    assert len({r["gold_item_key"] for r in bt} & flagged) == 55
    listed = set(load("OE_P7_test_exclusion.json")["item_keys"]) | set(load("OE_P8_test_exclusion.json")["item_keys"])
    assert not listed & {r["item_key"] for r in bt}
