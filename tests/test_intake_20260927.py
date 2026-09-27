"""The 2026-09-27 delivery, asserted rather than trusted (S3 work item 1, D-033).

Two claims came with the delivery and both are load-bearing, so neither is taken on the
upstream README's word.

**The corrected stacked file does not move a single text.** If that holds, S2's three stacked
runs keep their Acc@1 even though their query-set digest is superseded: the retrieval inputs
are unchanged and only two count fields are added. If it were false, those runs would be
measuring a query set that no longer exists and the sprint would owe a re-run. This is S3's
exit criterion 2, and it is a test because "upstream says the texts are unchanged" is exactly
the kind of assurance the branch's operating rules exist to distrust.

**The duplicate sidecar describes what D-031 measured.** Item-level scoring is about to start
excluding queries on the strength of this file (D-033), so its shape is checked against the
figures the decision was taken on — 292 groups, 776 leaves, never crossing a concept — and
every member is checked to exist in the corpus. A sidecar that disagreed with the decision
would silently change which queries get scored.

The superseded query set survives under a digest-stamped name, so `7b0894e6…` remains findable
in the tree. These tests pin that too: a copy whose name claims a digest it does not carry is
worse than no copy, because it would be trusted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from utils.corpus_prep import QUERY_FIELDS, load_records

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"

STACKED = PROCESSED / "OE_stacked_texto.json"
SUPERSEDED = PROCESSED / "OE_stacked_texto__1bde2115.json"
SIDECAR = PROCESSED / "OE_duplicate_texto_groups.json"

#: Digests upstream's own manifest states, and the ones the versioned names claim.
EXPECTED = {
    "OE_stacked_texto.json": "c34a222ae2af05a0b5335b774cb7fb45f14064cc17234d9d885e809fb29b6f45",
    "OE_duplicate_texto_groups.json": "b3cfcad47c71c5ebaf86b0e77eaa741c8f6111efd4e8543262b4f1b8e4ced0df",
    "OE_stacked_texto__1bde2115.json": "1bde21157ef974218b9e26ae7eecb8f5ba2a25a42b66034143201165ad015116",
    "OE_stacked_texto_norm__81cd501b.parquet": "81cd501b305b17db953d3ab9755c3eeb453c25133dbb29d76ea5381b371b383f",
    "OE_stacked_texto_feats__7b0894e6.parquet": "7b0894e6bc5c82d38ccf007e8bb86edfdaf0ffc2f4a1e849b8a6dd4d8ea9fef3",
}

pytestmark = pytest.mark.skipif(
    not STACKED.exists(),
    reason="data/processed is git-ignored and absent in this checkout",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@pytest.fixture(scope="module")
def corrected():
    return json.loads(STACKED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def superseded():
    return json.loads(SUPERSEDED.read_text(encoding="utf-8"))


# --- the delivery is the file it says it is --------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_digest_matches_what_the_name_or_the_upstream_manifest_claims(name):
    path = PROCESSED / name
    assert path.exists(), f"{name} missing — work item 1 did not complete"
    assert sha256(path) == EXPECTED[name]


# --- exit criterion 2: the corrected file moved no text --------------------------------


def test_record_count_is_unchanged(corrected, superseded):
    assert len(corrected) == len(superseded) == 4998


@pytest.mark.parametrize("field", ["text", "id", "item_key", "gold_item_key"])
def test_field_is_identical_row_for_row(corrected, superseded, field):
    """Row for row, not as a set: order carries the join to the stored top-100 lists."""
    assert [r[field] for r in corrected] == [r[field] for r in superseded]


def test_only_the_two_visible_dose_fields_were_added(corrected, superseded):
    added = set(corrected[0]) - set(superseded[0])
    assert added == {"texto_modification_count", "texto_modification_types"}
    assert not set(superseded[0]) - set(corrected[0]), "the delivery dropped a field"


def test_the_visible_dose_never_exceeds_the_applied_dose(corrected):
    """The TEXTO cannot show more modifications than were applied to the record."""
    offenders = [
        r["item_key"]
        for r in corrected
        if r["texto_modification_count"] > r["modification_count"]
    ]
    assert not offenders, f"visible dose above applied dose in {len(offenders)} records"


def test_the_visible_dose_agrees_with_its_own_type_list(corrected):
    bad = [
        r["item_key"]
        for r in corrected
        if r["texto_modification_count"] != len(set(r["texto_modification_types"]))
    ]
    assert not bad, f"count disagrees with the de-duplicated type list in {len(bad)} records"


def test_the_visible_dose_is_lower_than_the_applied_one_somewhere(corrected):
    """Guards against a delivery that added the field as a copy and fixed nothing.

    D-025 raised this: the stacked set's `modification_count` overstates the dose reaching the
    TEXTO. If the two fields agreed everywhere, the correction would be cosmetic and the
    re-stratification of S2's by-dose table would be pointless.
    """
    lower = sum(
        1 for r in corrected if r["texto_modification_count"] < r["modification_count"]
    )
    assert lower > 0, "texto_modification_count never differs — the field corrects nothing"


# --- the projection carries the new fields without churning the other query sets -------


def test_the_corrected_stacked_set_projects_the_visible_dose():
    df = load_records(STACKED, extra_fields=QUERY_FIELDS)
    assert {"texto_modification_count", "texto_modification_types"} <= set(df.columns)


def test_a_query_set_without_the_field_does_not_gain_a_null_column():
    """Why the projection is conditional.

    `OE_single_texto.json` never carried `texto_modification_*` — SINGLE is exact by
    construction. An unconditional projection would give it two all-null columns, changing that
    table's parquet digest and so invalidating the five S2 runs stamped `e5b79ae4…` for no
    information at all.
    """
    single = PROCESSED / "OE_single_texto.json"
    df = load_records(single, extra_fields=QUERY_FIELDS)
    assert "texto_modification_count" not in df.columns
    assert "texto_modification_types" not in df.columns
    assert "gold_item_key" in df.columns, "the gold must still be projected"


# --- the derived tables: the digest moved, the retrieval inputs did not ----------------
#
# This is the claim that keeps S2's three stacked runs alive. They are stamped against the
# feature table `7b0894e6…`, which the re-derivation superseded with `f34c1798…`. That is only
# harmless if the new table differs from the old one *solely* by the two appended columns — if
# any indexed column had shifted, S2's stacked Acc@1 would be a number about a query set that no
# longer exists, and the sprint would owe a re-run.

FEATS = PROCESSED / "OE_stacked_texto_feats.parquet"
FEATS_SUPERSEDED = PROCESSED / "OE_stacked_texto_feats__7b0894e6.parquet"


@pytest.fixture(scope="module")
def feats_pair():
    pd = pytest.importorskip("pandas")
    if not (FEATS.exists() and FEATS_SUPERSEDED.exists()):
        pytest.skip("stacked feature tables absent; work item 1 not complete")
    return pd.read_parquet(FEATS_SUPERSEDED), pd.read_parquet(FEATS)


def test_the_new_feature_table_only_appends(feats_pair):
    old, new = feats_pair
    assert len(old) == len(new) == 4998
    assert [c for c in old.columns if c not in new.columns] == [], "a column was dropped"
    added = [c for c in new.columns if c not in old.columns]
    assert set(added) == {"texto_modification_count", "texto_modification_types"}


def test_every_pre_existing_column_is_identical_row_for_row(feats_pair):
    old, new = feats_pair
    differing = [
        c for c in old.columns
        if old[c].astype(str).tolist() != new[c].astype(str).tolist()
    ]
    assert not differing, f"the re-derivation moved {differing} — S2's stacked runs are invalid"


@pytest.mark.parametrize(
    "column",
    ["text_norm", "text_word", "text_word_params", "text_char", "numbers", "param_tokens"],
)
def test_the_indexed_columns_are_identical(feats_pair, column):
    """Named one by one, because these are the fields the retrievers actually score."""
    old, new = feats_pair
    assert old[column].astype(str).tolist() == new[column].astype(str).tolist()


def test_the_visible_dose_survived_into_the_feature_table(feats_pair):
    """A1: without the loader change the corrected field would stop at the JSON."""
    _, new = feats_pair
    assert new["texto_modification_count"].tolist() == [
        len(set(t)) for t in new["texto_modification_types"]
    ]
    assert new["texto_modification_count"].between(1, 6).all()


# --- the duplicate sidecar agrees with the decision taken on it ------------------------


@pytest.fixture(scope="module")
def sidecar():
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


def test_sidecar_matches_the_figures_d031_was_decided_on(sidecar):
    groups = sidecar["groups"]
    members = [m for g in groups.values() for m in g]
    assert sidecar["n_groups"] == len(groups) == 292
    assert sidecar["n_leaves"] == len(members) == 776
    assert len(set(members)) == 776, "a leaf appears in two groups"


def test_no_group_crosses_a_concept(sidecar):
    """Why parent-level scoring excludes nothing (D-033)."""
    for group_id, members in sidecar["groups"].items():
        parents = {m[:6] for m in members}
        assert len(parents) == 1, f"group {group_id} spans {parents}"


def test_every_group_is_keyed_on_its_smallest_member(sidecar):
    for group_id, members in sidecar["groups"].items():
        assert group_id == min(members)


def test_every_member_exists_in_the_corpus(sidecar):
    corpus = json.loads((PROCESSED / "OE_texto.json").read_text(encoding="utf-8"))
    keys = {r["item_key"] for r in corpus}
    members = {m for g in sidecar["groups"].values() for m in g}
    missing = sorted(members - keys)
    assert not missing, f"{len(missing)} flagged leaves absent from the corpus: {missing[:5]}"


def test_the_flagged_leaves_really_do_share_a_texto(sidecar):
    """The flag is only usable if it is true of the delivered corpus, not of some other build."""
    corpus = json.loads((PROCESSED / "OE_texto.json").read_text(encoding="utf-8"))
    text_of = {r["item_key"]: r["text"] for r in corpus}
    for group_id, members in sidecar["groups"].items():
        texts = {text_of[m] for m in members}
        assert len(texts) == 1, f"group {group_id} members do not share one texto"
