"""D-018, enforced instead of merely written down (S3).

D-018 has said since 2026-09-15 that work happens in the main checkout. Nothing checked it, and
on 2026-09-27 the gap showed: a container was found mounting `.claude/worktrees/…` as `/work`
while binding the main checkout's `data/`, `index/` and `runs/` in over it. Another branch's code
held the write end of this branch's artefacts. Had `data.ipynb` run there, it would have rebuilt
the feature tables S2's runs are stamped against using a `corpus_prep` without this branch's
changes — and every resulting digest would have looked entirely plausible.

So the resolver everything routes through (D-022) now refuses a linked worktree, and these tests
hold that refusal in place. They also hold the escape hatch open: STATE.md contemplates a
deliberate parallel worktree for S9–S11, created with its junctions, and a guard with no
override would simply be worked around.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from utils.run_context import (
    WORKTREE_OVERRIDE_ENV,
    assert_work_root_is_the_main_checkout,
    data_paths,
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def no_override(monkeypatch):
    monkeypatch.delenv(WORKTREE_OVERRIDE_ENV, raising=False)


# --- the main checkout is accepted -----------------------------------------------------


def test_the_main_checkout_passes(no_override):
    """`.git` is a directory here, so there is nothing to refuse."""
    assert (REPO / ".git").is_dir()
    assert_work_root_is_the_main_checkout(REPO)


def test_a_directory_that_is_not_a_git_tree_passes(tmp_path, no_override):
    """Tests and containers legitimately resolve against a tmp dir with no git at all."""
    assert_work_root_is_the_main_checkout(tmp_path)


# --- a linked worktree is refused ------------------------------------------------------


@pytest.fixture
def linked_worktree(tmp_path):
    """A real linked worktree, made by git, removed afterwards.

    Built rather than faked: the guard's whole value is recognising what git actually writes,
    and a hand-made `.git` file would let the guard and the test agree on a fiction.
    """
    path = tmp_path / "wt"
    subprocess.run(
        ["git", "-C", str(REPO), "worktree", "add", "--detach", str(path), "HEAD"],
        check=True,
        capture_output=True,
    )
    try:
        yield path
    finally:
        subprocess.run(
            ["git", "-C", str(REPO), "worktree", "remove", "--force", str(path)],
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(REPO), "worktree", "prune"], check=False, capture_output=True
        )


def test_git_really_does_write_dot_git_as_a_file(linked_worktree):
    """The premise the guard rests on."""
    assert (linked_worktree / ".git").is_file()


def test_a_linked_worktree_is_refused(linked_worktree, no_override):
    with pytest.raises(RuntimeError) as excinfo:
        assert_work_root_is_the_main_checkout(linked_worktree)
    message = str(excinfo.value)
    assert "linked git worktree" in message
    assert "D-018" in message, "the refusal must name the decision it enforces"
    assert WORKTREE_OVERRIDE_ENV in message, "the refusal must say how to proceed deliberately"


def test_the_override_lets_a_deliberate_worktree_through(linked_worktree, monkeypatch):
    monkeypatch.setenv(WORKTREE_OVERRIDE_ENV, "1")
    assert_work_root_is_the_main_checkout(linked_worktree)


def test_only_exactly_one_opens_the_gate(linked_worktree, monkeypatch):
    """A truthy-looking value is not consent; the override is a switch, not a hint."""
    for value in ("0", "true", "yes", ""):
        monkeypatch.setenv(WORKTREE_OVERRIDE_ENV, value)
        with pytest.raises(RuntimeError):
            assert_work_root_is_the_main_checkout(linked_worktree)


# --- the guard is wired into the resolver, not just available ---------------------------


def test_data_paths_refuses_a_linked_worktree(linked_worktree, no_override):
    """The entry `data.ipynb` uses. This is the call that would have done the damage."""
    with pytest.raises(RuntimeError, match="linked git worktree"):
        data_paths("OE", work_root=linked_worktree)


def test_load_run_context_refuses_a_linked_worktree(linked_worktree, no_override):
    from utils.run_context import load_run_context

    config = REPO / "configs" / "bm25_unigram_params__k1-0.60__b-0.35__OE.yaml"
    if not config.exists():
        pytest.skip("OE config absent in this checkout")
    with pytest.raises(RuntimeError, match="linked git worktree"):
        load_run_context(config, queryset="texto", work_root=linked_worktree)


def test_the_guard_runs_before_anything_is_read(linked_worktree, no_override):
    """It must refuse on the worktree itself, not on a missing file inside it.

    If the guard ran after the corpus check, a worktree that *did* have the data junctions —
    exactly the dangerous container's shape — would sail past it.
    """
    with pytest.raises(RuntimeError, match="linked git worktree"):
        data_paths("OE", work_root=linked_worktree)
    # and the same call without the guard would have complained about something else entirely
    os.environ[WORKTREE_OVERRIDE_ENV] = "1"
    try:
        with pytest.raises(FileNotFoundError):
            data_paths("OE", work_root=linked_worktree)
    finally:
        del os.environ[WORKTREE_OVERRIDE_ENV]
