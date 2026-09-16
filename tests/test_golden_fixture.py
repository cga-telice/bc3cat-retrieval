"""The migration must not move a number (S1 exit criterion 3).

`tests/fixtures/oeb_bm25_pre_migration/` holds the OEB metrics as they were before any
notebook was migrated, with the stamp that says what produced them. Once the migrated
harness has re-run that same config, this compares the two and requires them to be equal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.compare_metrics import diff_metrics

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "oeb_bm25_pre_migration"
METHOD = "bm25_unigram_params__k1-0.60__b-0.35"

#: Where the migrated harness writes the same run, under D-008's layout.
MIGRATED = REPO / "runs" / "OEB" / "resumen" / METHOD / "metrics_dual.json"


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


# --- the comparison itself ------------------------------------------------------------


def test_identical_metrics_have_no_differences():
    rows = load(FIXTURE / "metrics_dual.json")

    assert diff_metrics(rows, rows) == []


def test_a_moved_metric_is_reported_with_both_values():
    rows = load(FIXTURE / "metrics_dual.json")
    moved = json.loads(json.dumps(rows))
    moved[0]["Acc@1"] = moved[0]["Acc@1"] - 0.001

    differences = diff_metrics(rows, moved)

    assert len(differences) == 1
    assert "Acc@1" in differences[0]
    assert "overall" in differences[0] and "item" in differences[0]


def test_a_changed_query_count_is_reported():
    """A different number of queries means a different sample, not a different score."""
    rows = load(FIXTURE / "metrics_dual.json")
    fewer = json.loads(json.dumps(rows))
    fewer[0]["queries"] = 16000.0

    assert any("queries" in d for d in diff_metrics(rows, fewer))


def test_a_missing_scope_is_reported_rather_than_skipped():
    rows = load(FIXTURE / "metrics_dual.json")
    truncated = json.loads(json.dumps(rows))[:-1]

    differences = diff_metrics(rows, truncated)

    assert differences and any("missing" in d for d in differences)


def test_an_added_scope_is_reported():
    rows = load(FIXTURE / "metrics_dual.json")
    extended = json.loads(json.dumps(rows))
    extra = json.loads(json.dumps(rows[0]))
    extra["scope"] = "invented"
    extended.append(extra)

    assert any("unexpected" in d for d in diff_metrics(rows, extended))


# --- the fixture itself ---------------------------------------------------------------


def test_the_fixture_file_matches_its_own_digest():
    """The stamp used to name only the *source* run's digest, so nothing anchored the copy
    the tests actually read — and a CRLF translation on the way out meant the two differed
    (audit F1). Both are recorded now, and this checks the one that matters."""
    import hashlib

    stamp = json.loads((FIXTURE / "STAMP.json").read_text(encoding="utf-8"))
    frozen = (FIXTURE / "metrics_dual.json").read_bytes()

    assert stamp["frozen_metrics_sha256"] == hashlib.sha256(frozen).hexdigest()
    crlf = bytes([13, 10])
    assert crlf not in frozen, "line endings were translated; the digest would not survive"


def test_the_fixture_is_tracked_by_git():
    """.gitignore's blanket *.json rule silently excluded it, so the sprint's only claimed
    finding rested on a file with no version-control history (audit F1)."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "tests/fixtures/oeb_bm25_pre_migration"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.split()

    assert "tests/fixtures/oeb_bm25_pre_migration/metrics_dual.json" in tracked
    assert "tests/fixtures/oeb_bm25_pre_migration/STAMP.json" in tracked


def test_the_fixture_predates_the_migrated_metrics_notebook():
    """Structural proof that the fixture was not produced by today's code: the migrated
    metrics notebook emits the slice rows, and the fixture has none of them."""
    rows = load(FIXTURE / "metrics_dual.json")

    assert {row["scope"] for row in rows} == {"overall", "has_numbers", "no_numbers"}
    assert len(rows) == 6


def test_the_fixture_is_stamped():
    stamp = json.loads((FIXTURE / "STAMP.json").read_text(encoding="utf-8"))

    assert stamp["code_dirty"] is False, "captured from a dirty tree; it proves nothing"
    assert stamp["collection"] == "OEB"
    assert stamp["execution"]["RANDOM_SAMPLE"] == "16590"
    assert all(v["sha256"] for v in stamp["inputs"].values())


# --- the criterion ---------------------------------------------------------------------


@pytest.mark.skipif(not MIGRATED.exists(), reason="the migrated OEB run has not been made yet")
def test_the_migrated_harness_reproduces_the_fixture():
    """Every figure the fixture recorded, reproduced exactly after five notebooks, a new
    resolver, batched scoring and gold decoupled from the query key."""
    differences = diff_metrics(
        load(FIXTURE / "metrics_dual.json"), load(MIGRATED), allow_extra_scopes=True
    )

    assert differences == [], "the migration moved a number:\n" + "\n".join(differences)


@pytest.mark.skipif(not MIGRATED.exists(), reason="the migrated OEB run has not been made yet")
def test_the_migration_only_added_slices():
    """The tolerance above is for added slices, so what was added is named here rather than
    left as whatever happened to appear."""
    before = {row["scope"] for row in load(FIXTURE / "metrics_dual.json")}
    after = {row["scope"] for row in load(MIGRATED)}

    added = after - before

    assert before <= after, "a scope the fixture recorded has disappeared"
    assert added, "the slices S1 adds are missing"
    assert all(scope.split(":")[0] in {
        "condition", "modification_type", "modification_count", "subchapter", "family_tercile"
    } for scope in added), sorted(added)
