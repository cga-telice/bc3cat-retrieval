"""Runs computed from other runs: fusion and reranking (S4 work item 2).

A derived run does no first-stage retrieval. It reads the `results_top100.jsonl.gz` of its
component runs and writes a run of the same shape, so `metrics.ipynb`, `check_run_inputs.py`
and every generator read it exactly as they read a retrieval run.

What makes this dangerous is pairing. A fused list is only meaningful if row *i* of every
component is the same query with the same gold, and the components were made at different
commits, from different query tables (ColBERT reads `OE_long_norm`, BM25 `OE_long_feats`, so
their `texto` digests differ although their queries do not). So alignment is checked on what
matters — split, query set, and the ordered `(query key, gold key)` sequence, against the
derived run's own query table — and each component's stamp is copied into the derived run,
where `check_run_inputs.py` verifies it still matches the component on disk.

A config names its components by **method**; the run ID follows from the query set, as
`{collection}/{queryset}/{method}`, because the same derived arm runs on several query sets.
"""

from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from utils.provenance import assert_clean_stamp, provenance_stamp, sha256_file
from utils.run_context import RunContext, load_run_context
from utils.splits import select_split

#: What is copied from a component's `run_meta.json` into the derived run's.
COMPONENT_STAMP_FIELDS = (
    "run_id", "config", "config_sha256", "code_commit", "code_dirty",
    "query_set_sha256", "corpus_sha256", "split", "queryset", "queries",
)

RESULTS_NAME = "results_top100.jsonl.gz"


@dataclass(frozen=True)
class ComponentRun:
    run_dir: Path
    meta: dict
    records: list[dict]

    @property
    def keys(self) -> list[tuple[str, str]]:
        return [(str(r["query_item_key"]), str(r["gold_item_key"])) for r in self.records]


def load_config(config_path: str | Path) -> dict:
    return yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))


def component_methods(cfg: dict, config_path: Path) -> list[str]:
    components = (cfg.get("derived") or {}).get("components")
    if not components:
        raise KeyError(f"{Path(config_path).name}: a derived config declares derived.components")
    return [str(c) for c in components]


def _iter_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def load_component(run_dir: str | Path) -> ComponentRun:
    """Read one component run, and refuse one that could not be reported itself."""
    run_dir = Path(run_dir)
    meta_path = run_dir / "run_meta.json"
    results_path = run_dir / RESULTS_NAME
    for required in (meta_path, results_path):
        if not required.exists():
            raise FileNotFoundError(f"component run incomplete: {required} is missing")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("code_dirty"):
        raise ValueError(f"component {meta.get('run_id')} was made from a dirty tree")

    records = list(_iter_jsonl_gz(results_path))
    for record in records:
        candidates = record.get("candidates") or []
        if not candidates:
            raise ValueError(f"{run_dir}: query {record.get('query_item_key')} has no candidates")
        ranks = [c["rank"] for c in candidates]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError(f"{run_dir}: query {record.get('query_item_key')} ranks are not 1..n")
        scores = [float(c["score"]) for c in candidates]
        # Every retriever here sorts higher-is-better; blending min-max-normalised scores
        # silently inverts a list that does not, so a violation is an error.
        if any(b > a for a, b in zip(scores, scores[1:])):
            raise ValueError(
                f"{run_dir}: query {record.get('query_item_key')} scores increase with rank"
            )
    if len(records) != meta.get("queries"):
        raise ValueError(
            f"{run_dir}: {len(records)} records but run_meta says {meta.get('queries')} queries"
        )
    return ComponentRun(run_dir=run_dir, meta=meta, records=records)


def expected_queries(ctx: RunContext, split: str) -> tuple[pd.DataFrame, int]:
    """The derived run's own query table, split-selected, and its size before the split."""
    frame = pd.read_parquet(ctx.query_path)
    n_before = len(frame)
    frame = select_split(frame, split)
    gold = "gold_item_key" if "gold_item_key" in frame.columns else "item_key"
    frame = frame.assign(_query_key=frame["item_key"].astype(str), _gold_key=frame[gold].astype(str))
    return frame.reset_index(drop=True), n_before


def check_aligned(
    components: list[ComponentRun], expected: list[tuple[str, str]], *, split: str, queryset: str
) -> None:
    """Fail loud unless every component covers exactly the expected queries, in order."""
    for comp in components:
        name = comp.meta.get("run_id", str(comp.run_dir))
        if comp.meta.get("split") != split:
            raise ValueError(f"{name}: split {comp.meta.get('split')!r}, expected {split!r}")
        if comp.meta.get("queryset") != queryset:
            raise ValueError(f"{name}: query set {comp.meta.get('queryset')!r}, expected {queryset!r}")
        keys = comp.keys
        if len(keys) != len(expected):
            raise ValueError(f"{name}: {len(keys)} queries, expected {len(expected)}")
        for i, (got, want) in enumerate(zip(keys, expected)):
            if got != want:
                raise ValueError(
                    f"{name}: row {i} is {got}, expected {want}. Components must pair by row."
                )


def resolve(config_path: str | Path, queryset: str, *, work_root: str | Path):
    """Context, config and loaded, aligned components for one derived run."""
    config_path = Path(config_path)
    ctx = load_run_context(config_path, queryset=queryset, work_root=work_root)
    cfg = load_config(config_path)
    methods = component_methods(cfg, config_path)
    runs_root = Path(work_root) / "runs" / ctx.collection / queryset
    components = [load_component(runs_root / m) for m in methods]
    return ctx, cfg, components


def corpus_positions(ctx: RunContext) -> dict[str, int]:
    """item_key -> row in the corpus table: a `doc_id` independent of any one index's order."""
    keys = pd.read_parquet(ctx.corpus_path, columns=["item_key"])["item_key"].astype(str)
    return {k: i for i, k in enumerate(keys)}


def write_run(
    ctx: RunContext,
    *,
    split: str,
    expected: pd.DataFrame,
    n_before: int,
    ranked: list[list[tuple[str, float]]],
    components: list[ComponentRun],
    extra_meta: dict,
    elapsed_s: float,
    work_root: str | Path,
    allow_dirty: bool = False,
) -> Path:
    """Write `results_top100.jsonl.gz` and `run_meta.json` in `retrieve.ipynb`'s shape.

    The stamp is computed and checked **before** anything is written, so a refused run leaves
    no partial directory behind.
    """
    stamp = provenance_stamp(
        run_id=f"{ctx.collection}/{ctx.queryset}/{ctx.method}",
        config_path=ctx.config_path,
        query_path=ctx.query_path,
        repo=Path(work_root),
    )
    if not allow_dirty:
        assert_clean_stamp(stamp)

    if len(ranked) != len(expected):
        raise RuntimeError(f"{len(ranked)} ranked lists for {len(expected)} queries")

    positions = corpus_positions(ctx)
    ctx.run_dir.mkdir(parents=True, exist_ok=True)
    k = max(len(r) for r in ranked)
    parents = expected["parent_key"].astype(str).tolist()
    texts = expected["text"].astype(str).tolist() if "text" in expected.columns else [""] * len(expected)

    with gzip.open(ctx.run_dir / RESULTS_NAME, "wt", encoding="utf-8") as gz:
        for i, (qkey, gkey, parent, text, cands) in enumerate(
            zip(expected["_query_key"], expected["_gold_key"], parents, texts, ranked)
        ):
            gz.write(json.dumps({
                "query_id": f"q_{i:06d}",
                "query_item_key": qkey,
                "gold_item_key": gkey,
                "gold_parent_key": parent,
                "query_text": text,
                "candidates": [
                    {"rank": r + 1, "doc_id": positions[doc], "index_item_key": doc, "score": float(s)}
                    for r, (doc, s) in enumerate(cands)
                ],
                "score_info": {"family": extra_meta.get("family", "derived"), "higher_is_better": True},
            }, ensure_ascii=False) + "\n")

    meta = {
        **stamp,
        "corpus_sha256": sha256_file(ctx.corpus_path),
        "collection": ctx.collection,
        "queryset": ctx.queryset,
        "split": split,
        "method": ctx.method,
        "config": str(ctx.config_path),
        # metrics.ipynb reads this key; a derived run has no index of its own.
        "index_dir": "derived: no index of its own",
        "query_path": str(ctx.query_path),
        "gold_column": "gold_item_key" if "gold_item_key" in expected.columns else "item_key",
        "queries": len(ranked),
        "queries_before_split": int(n_before),
        "queries_after_split": len(expected),
        "queries_selected": len(expected),
        "dropped": int(len(expected) - len(ranked)),
        "K": k,
        "retriever_module": ctx.retriever_module,
        "derived": True,
        "components": [
            {f: c.meta.get(f) for f in COMPONENT_STAMP_FIELDS} for c in components
        ],
        **extra_meta,
        "elapsed_s": round(elapsed_s, 3),
        "created_utc": pd.Timestamp.utcnow().isoformat(),
    }
    with open(ctx.run_dir / "run_meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return ctx.run_dir


class Timer:
    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.time() - self.t0
        return False
