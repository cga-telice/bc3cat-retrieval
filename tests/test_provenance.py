"""Every run carries the four-part stamp, or its numbers do not exist.

The branch's first operating rule: `{run_id, config SHA, code commit, query-set SHA-256}`.
The previous submission failed on exactly this, so the stamp is produced by the harness and
checked here, not assembled by hand when a report is written.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from utils.provenance import STAMP_FIELDS, provenance_stamp

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"


def test_the_stamp_has_the_four_parts_the_rule_names():
    assert set(STAMP_FIELDS) == {"run_id", "config_sha256", "code_commit", "query_set_sha256"}


def test_the_stamp_digests_the_files_it_names(tmp_path):
    config = tmp_path / "cfg.yaml"
    config.write_text("collection: OE\n", encoding="utf-8")
    queries = tmp_path / "q.parquet"
    queries.write_bytes(b"not really a parquet, but it has bytes")

    stamp = provenance_stamp(
        run_id="OE/single_texto/method", config_path=config, query_path=queries, repo=REPO
    )

    assert stamp["config_sha256"] == hashlib.sha256(config.read_bytes()).hexdigest()
    assert stamp["query_set_sha256"] == hashlib.sha256(queries.read_bytes()).hexdigest()


def test_the_code_commit_is_the_real_head(tmp_path):
    config = tmp_path / "cfg.yaml"
    config.write_text("x", encoding="utf-8")
    queries = tmp_path / "q"
    queries.write_bytes(b"y")

    stamp = provenance_stamp(run_id="r", config_path=config, query_path=queries, repo=REPO)

    assert len(stamp["code_commit"]) == 40
    assert set(stamp["code_commit"]) <= set("0123456789abcdef")


def test_a_dirty_tree_is_recorded_rather_than_hidden(tmp_path):
    config = tmp_path / "cfg.yaml"
    config.write_text("x", encoding="utf-8")
    queries = tmp_path / "q"
    queries.write_bytes(b"y")

    stamp = provenance_stamp(run_id="r", config_path=config, query_path=queries, repo=REPO)

    assert "code_dirty" in stamp
    assert isinstance(stamp["code_dirty"], bool)


def test_a_missing_file_is_an_error_not_a_null(tmp_path):
    """A stamp with a null digest would look stamped and prove nothing."""
    with pytest.raises(FileNotFoundError):
        provenance_stamp(
            run_id="r", config_path=tmp_path / "absent.yaml", query_path=tmp_path, repo=REPO
        )


# --- the runs on disk -------------------------------------------------------------------

RUN_METAS = sorted(RUNS.glob("*/*/*/run_meta.json"))


@pytest.mark.skipif(not RUN_METAS, reason="no runs in this checkout (runs/ is git-ignored)")
@pytest.mark.parametrize("meta_path", RUN_METAS, ids=lambda p: str(p.parent.relative_to(RUNS)))
def test_every_run_on_disk_is_stamped(meta_path):
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    missing = [field for field in STAMP_FIELDS if not meta.get(field)]

    assert missing == [], f"{meta_path.parent.name} is missing {missing}"


@pytest.mark.skipif(not RUN_METAS, reason="no runs in this checkout (runs/ is git-ignored)")
@pytest.mark.parametrize("meta_path", RUN_METAS, ids=lambda p: str(p.parent.relative_to(RUNS)))
def test_every_run_records_what_it_dropped(meta_path):
    """Zero is the only acceptable value, and it is recorded rather than assumed."""
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    assert meta["dropped"] == 0
    assert meta["queries"] > 0
