"""Where a superseded run now lives (S5 amendment A1, César 2026-09-30).

A run directory is `runs/{collection}/{queryset}/{method}` (D-008), so re-running a method on a
query set overwrites the earlier run. When a later sprint must re-run one, the earlier run is
copied first, checksum-verified, to `runs/_archive/{sprint}/…` (S2 A5's procedure for S1's runs),
and every reader that reports the earlier sprint's numbers is routed here, so its generated tables
still regenerate byte-identically from the runs they were made from.

S5 re-ran the two rules arms on `texto` and `single_texto`, because their Stage 1 reads the E5
index that S3 rebuilt on a newer stack (D-034); the oracle-extraction arm must share its Stage 1.
S2's stacked runs were not re-run then.

S7 re-runs every arm on the corrected stacked set (`SPRINT_S7_DESIGN.md` work item 2, D-047), so S2's
five stacked runs move to the archive too. Two of them, the BM25 operating points, are also cells of
S3's 150-cell sweep and are read by `build_results_e0.py` as S3's: that reader is routed to the same
archive copy, which is where the run S3 read now lives.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_RULES = ("structured_pipeline_rules__OE", "structured_pipeline_rules_valuenorm__OE")
_BM25_POINTS = ("bm25_unigram__k1-0.60__b-0.35__OE", "bm25_unigram_params__k1-0.60__b-0.35__OE")

#: (reading sprint, collection, queryset, method) of every run moved out of `runs/` by a later
#: sprint, mapped to the sprint whose archive holds it (the sprint that made the run).
ARCHIVED_IN = {
    # S5 A1: S2's rules runs on texto and single_texto.
    **{("S2", "OE", q, m): "S2" for q in ("texto", "single_texto") for m in _RULES},
    # S7 work item 2: S2's five stacked runs.
    **{("S2", "OE", "stacked_texto", m): "S2"
       for m in (*_RULES, *_BM25_POINTS, "bge_m3_colbert__OE")},
    # ... two of which are S3 sweep cells.
    **{("S3", "OE", "stacked_texto", m): "S2" for m in _BM25_POINTS},
}

#: The keys alone, for readers that only ask whether a run was moved.
ARCHIVED = set(ARCHIVED_IN)


def run_dir_as_of(sprint: str, collection: str, queryset: str, method: str,
                  repo: Path = REPO) -> Path:
    """The run directory `sprint` read: its archive copy if a later sprint superseded it."""
    home = ARCHIVED_IN.get((sprint, collection, queryset, method))
    if home is not None:
        return repo / "runs" / "_archive" / home / collection / queryset / method
    return repo / "runs" / collection / queryset / method
