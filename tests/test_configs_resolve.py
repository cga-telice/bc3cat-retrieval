"""The resolver against the repository's real configs, not a fixture.

S0 left 77 configs that name their collection and their retriever. If any of them cannot be
resolved, the harness cannot be migrated onto the resolver, so this is checked as a whole
rather than one config at a time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.run_context import QUERY_SETS, load_run_context

REPO = Path(__file__).resolve().parents[1]
CONFIGS = sorted((REPO / "configs").glob("*.yaml"))


def test_the_repository_has_configs_to_resolve():
    assert CONFIGS, "no configs found — the rest of this module would pass vacuously"


@pytest.mark.parametrize("config_path", CONFIGS, ids=lambda p: p.stem)
def test_every_config_resolves(config_path):
    ctx = load_run_context(
        config_path, queryset="resumen", work_root=REPO, require_inputs=False
    )

    assert ctx.collection
    assert ctx.index_dir == REPO / "index" / ctx.collection / ctx.method
    assert ctx.run_dir == REPO / "runs" / ctx.collection / "resumen" / ctx.method


@pytest.mark.parametrize("config_path", CONFIGS, ids=lambda p: p.stem)
def test_every_declared_retriever_module_exists_on_disk(config_path):
    """Checked as a file, not by importing: the neural modules pull heavy dependencies that
    a bare checkout need not have, and existence is what the config contract promises."""
    ctx = load_run_context(
        config_path, queryset="resumen", work_root=REPO, require_inputs=False
    )
    module_file = REPO / "src" / Path(*ctx.retriever_module.split(".")).with_suffix(".py")

    assert module_file.exists(), f"{config_path.name} declares {ctx.retriever_module}"


@pytest.mark.parametrize("queryset", QUERY_SETS)
def test_the_two_collections_never_share_a_run_directory(queryset):
    """The same method on OEB and on OE must not write to the same place (D-008)."""
    oeb = load_run_context(
        REPO / "configs" / "bm25_unigram_params__k1-0.60__b-0.35.yaml",
        queryset=queryset,
        work_root=REPO,
        require_inputs=False,
    )
    oe = load_run_context(
        REPO / "configs" / "bm25_unigram_params__k1-0.60__b-0.35__OE.yaml",
        queryset=queryset,
        work_root=REPO,
        require_inputs=False,
    )

    assert oeb.collection == "OEB" and oe.collection == "OE"
    assert oeb.run_dir != oe.run_dir
    assert oeb.index_dir != oe.index_dir
    assert oeb.corpus_path != oe.corpus_path
