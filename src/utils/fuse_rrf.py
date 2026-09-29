"""Reciprocal-rank fusion of component runs (S4 work item 1, design frozen at `dd407c6`).

    score(d) = Σ_c w_c / (k + rank_c(d))       k = 60, w_c = 1, over each component's top-100

A document absent from a component's list contributes 0 from it. Nothing here is tuned on OE:
`k`, the weights and the depth are fixed by the design and read from the config only so that
the config is the record of what ran.

Ties are common in RRF — a document at rank 1 in one list and absent from the other scores
exactly what the other list's rank-1 document scores — so the order among equal fused scores
is fixed here rather than left to a sort's stability: the better rank in the **first**
component, then in the second, and so on, then the item key. Absent counts as worse than any
rank.

    python -m utils.fuse_rrf --config /work/configs/<rrf config>.yaml --queryset texto --split dev
"""

from __future__ import annotations

import argparse
from pathlib import Path

from utils.derived_runs import (
    Timer, check_aligned, expected_queries, resolve, write_run,
)

ABSENT = 10**9


def rrf_fuse(
    lists: list[list[str]], *, k: int = 60, weights: list[float] | None = None, depth: int = 100,
    k_final: int = 100,
) -> list[tuple[str, float]]:
    """Fuse ranked lists of item keys; return the top `k_final` as (key, score)."""
    weights = weights or [1.0] * len(lists)
    if len(weights) != len(lists):
        raise ValueError(f"{len(weights)} weights for {len(lists)} lists")
    ranks: dict[str, list[int]] = {}
    for c, ranked in enumerate(lists):
        seen = set()
        for r, key in enumerate(ranked[:depth], start=1):
            if key in seen:
                raise ValueError(f"list {c} holds {key} twice")
            seen.add(key)
            ranks.setdefault(key, [ABSENT] * len(lists))[c] = r
    scored = [
        (key, sum(w / (k + r) for w, r in zip(weights, rs) if r != ABSENT), rs)
        for key, rs in ranks.items()
    ]
    scored.sort(key=lambda t: (-t[1], *t[2], t[0]))
    return [(key, score) for key, score, _ in scored[:k_final]]


def run(config_path, queryset: str, *, split: str = "dev", work_root="/work", allow_dirty=False):
    ctx, cfg, components = resolve(config_path, queryset, work_root=work_root)
    params = cfg["method"]["params"]
    expected, n_before = expected_queries(ctx, split)
    check_aligned(
        components, list(zip(expected["_query_key"], expected["_gold_key"])),
        split=split, queryset=queryset,
    )
    with Timer() as timer:
        ranked = [
            rrf_fuse(
                [[c["index_item_key"] for c in comp.records[i]["candidates"]] for comp in components],
                k=int(params["k_rrf"]),
                weights=[float(w) for w in params["weights"]],
                depth=int(params["depth"]),
                k_final=int(params["k_final"]),
            )
            for i in range(len(expected))
        ]
    return write_run(
        ctx, split=split, expected=expected, n_before=n_before, ranked=ranked,
        components=components, extra_meta={"family": "rrf", "rrf_params": params},
        elapsed_s=timer.elapsed, work_root=work_root, allow_dirty=allow_dirty,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--queryset", required=True)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--work-root", default="/work")
    args = ap.parse_args()
    out = run(args.config, args.queryset, split=args.split, work_root=args.work_root)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
