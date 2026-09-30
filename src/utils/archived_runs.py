"""Where a superseded run now lives (S5 amendment A1, César 2026-09-30).

A run directory is `runs/{collection}/{queryset}/{method}` (D-008), so re-running a method on a
query set overwrites the earlier run. When a later sprint must re-run one, the earlier run is
copied first, checksum-verified, to `runs/_archive/{sprint}/…` (S2 A5's procedure for S1's runs),
and every reader that reports the earlier sprint's numbers is routed here, so its generated tables
still regenerate byte-identically from the runs they were made from.

S5 re-ran the two rules arms on `texto` and `single_texto`, because their Stage 1 reads the E5
index that S3 rebuilt on a newer stack (D-034); the oracle-extraction arm must share its Stage 1.
S2's stacked runs were not re-run and stay in place.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: (sprint, collection, queryset, method) of every run moved out of `runs/` by a later sprint.
ARCHIVED = {
    ("S2", "OE", queryset, method)
    for queryset in ("texto", "single_texto")
    for method in ("structured_pipeline_rules__OE", "structured_pipeline_rules_valuenorm__OE")
}


def run_dir_as_of(sprint: str, collection: str, queryset: str, method: str,
                  repo: Path = REPO) -> Path:
    """The run directory `sprint` read: its archive copy if a later sprint superseded it."""
    if (sprint, collection, queryset, method) in ARCHIVED:
        return repo / "runs" / "_archive" / sprint / collection / queryset / method
    return repo / "runs" / collection / queryset / method
