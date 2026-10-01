"""Superseded runs stay where their readers look for them (D-047).

A later sprint re-runs a method by overwriting `runs/{collection}/{queryset}/{method}`, so the earlier
run is copied to `runs/_archive/{sprint}/…` first and its readers are routed there by
`utils/archived_runs.py`. These tests pin both halves: every routed key has an archive copy whose
checksums still verify, and the copies are the earlier sprint's runs — stamped against the query set
that sprint read — not a later run that landed in the wrong place.

First applied by S5 A1 (S2's rules runs on `texto` / `single_texto`); extended by S7 work item 2 to
S2's five stacked runs, two of which S3's sweep also reads.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from utils.archived_runs import ARCHIVED, ARCHIVED_IN, run_dir_as_of

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = REPO / "runs" / "_archive"

pytestmark = pytest.mark.skipif(
    not ARCHIVE.is_dir(), reason="runs/ is git-ignored and absent in this checkout"
)

#: The superseded stacked feature table S2's stacked runs were stamped against (D-033 intake).
S2_STACKED_TABLE = "7b0894e6bc5c82d38ccf007e8bb86edfdaf0ffc2f4a1e849b8a6dd4d8ea9fef3"

S7_MOVED = {
    "bm25_unigram__k1-0.60__b-0.35__OE",
    "bm25_unigram_params__k1-0.60__b-0.35__OE",
    "bge_m3_colbert__OE",
    "structured_pipeline_rules__OE",
    "structured_pipeline_rules_valuenorm__OE",
}


def test_archived_is_the_key_set_of_archived_in():
    assert ARCHIVED == set(ARCHIVED_IN)


@pytest.mark.parametrize("key", sorted(ARCHIVED_IN), ids=lambda k: "/".join(k))
def test_every_routed_run_resolves_into_the_archive(key):
    sprint, collection, queryset, method = key
    path = run_dir_as_of(sprint, collection, queryset, method, repo=REPO)
    assert path.relative_to(ARCHIVE).parts[0] == ARCHIVED_IN[key]
    assert (path / "run_meta.json").is_file(), path
    assert (path / "results_perquery.parquet").is_file(), path


def test_an_unrouted_run_resolves_to_the_live_tree():
    path = run_dir_as_of("S6", "OE", "single_l2_texto", "bge_m3_colbert__OE", repo=REPO)
    assert path == REPO / "runs" / "OE" / "single_l2_texto" / "bge_m3_colbert__OE"


def test_s7_moves_s2s_five_stacked_runs_for_s2_and_two_for_s3():
    s2 = {m for (s, _, q, m) in ARCHIVED_IN if s == "S2" and q == "stacked_texto"}
    s3 = {m for (s, _, q, m) in ARCHIVED_IN if s == "S3" and q == "stacked_texto"}
    assert s2 == S7_MOVED
    assert s3 == {m for m in S7_MOVED if m.startswith("bm25_")}


@pytest.mark.parametrize("method", sorted(S7_MOVED))
def test_the_archived_stacked_runs_are_s2s(method):
    meta = json.loads(
        (ARCHIVE / "S2" / "OE" / "stacked_texto" / method / "run_meta.json").read_text(encoding="utf-8")
    )
    assert meta["query_set_sha256"] == S2_STACKED_TABLE
    assert meta["code_commit"].startswith("31bf1a1")
    assert meta["code_dirty"] is False


def test_s2_archive_checksums_verify():
    sums = ARCHIVE / "S2" / "SHA256SUMS"
    lines = [ln.split(" *", 1) for ln in sums.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 90, "40 files from S5 A1 plus 50 from S7 work item 2"
    bad = []
    for digest, rel in lines:
        h = hashlib.sha256((ARCHIVE / "S2" / rel).read_bytes()).hexdigest()
        if h != digest:
            bad.append(rel)
    assert not bad, f"archive copies changed: {bad[:5]}"
