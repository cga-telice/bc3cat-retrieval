"""Cross-encoder blend reranking of a base run's top-100 (S4 work item 1, frozen at `dd407c6`).

    blended = λ·ĉ + (1 − λ)·ŝ          λ = 0.6

where ĉ and ŝ are the cross-encoder and base scores **min–max normalised per query** over the
base's candidates (a zero range normalises to 0). Ties in `blended` are broken by base rank.

This departs from `cross_encoder.ipynb`, which blends the two scores on their raw scales —
a BM25 score in the tens against a CE logit — so its λ meant a different thing on every base.
The design fixes the normalised form; the previous study's CE rows are therefore not a
reference for these.

Model: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, the model the code names (D-035's
precedent), pinned by Hub revision in the config. Query text is the query table's raw `text`
column, document text the corpus table's, as the neural arms read them.

Scores are cached by (sha1 of the query text, document key) per (model, revision,
`max_length`), because the three bases' candidate sets overlap heavily. A cache entry is a
function of its key alone, so reusing it cannot change a score.

    python -m utils.rerank_ce --config /work/configs/<ce config>.yaml --queryset texto --split dev
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from utils.derived_runs import (
    Timer, check_aligned, expected_queries, resolve, write_run,
)

Scorer = Callable[[Sequence[tuple[str, str]]], np.ndarray]


def minmax(values: Sequence[float]) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    span = x.max() - x.min()
    if span == 0:
        return np.zeros_like(x)
    return (x - x.min()) / span


def blend(
    keys: Sequence[str], base_scores: Sequence[float], ce_scores: Sequence[float], lam: float
) -> list[tuple[str, float]]:
    """Blend one query's candidates. `keys` is in base-rank order; ties keep that order."""
    if not (len(keys) == len(base_scores) == len(ce_scores)):
        raise ValueError("keys, base scores and CE scores differ in length")
    blended = lam * minmax(ce_scores) + (1.0 - lam) * minmax(base_scores)
    order = sorted(range(len(keys)), key=lambda i: (-blended[i], i))
    return [(keys[i], float(blended[i])) for i in order]


def query_sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class ScoreCache:
    """(query sha1, doc key) -> CE score, persisted as one parquet per model setting."""

    def __init__(self, path: Path | None):
        self.path = path
        self.scores: dict[tuple[str, str], float] = {}
        if path is not None and path.exists():
            frame = pd.read_parquet(path)
            self.scores = dict(zip(zip(frame["q_sha1"], frame["doc_key"]), frame["score"]))
        self.added = 0

    def save(self) -> None:
        if self.path is None or not self.added:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        keys = list(self.scores)
        frame = pd.DataFrame({
            "q_sha1": [k[0] for k in keys], "doc_key": [k[1] for k in keys],
            "score": [self.scores[k] for k in keys],
        })
        tmp = self.path.with_suffix(".tmp.parquet")
        frame.to_parquet(tmp, index=False)
        tmp.replace(self.path)


def score_all(
    requests: list[tuple[str, str, str, str]], scorer: Scorer, cache: ScoreCache, chunk: int = 20000
) -> None:
    """Fill the cache for every (q_sha1, doc_key, query text, doc text) not yet in it."""
    missing, seen = [], set()
    for q_sha1, doc_key, q_text, d_text in requests:
        key = (q_sha1, doc_key)
        if key not in cache.scores and key not in seen:
            seen.add(key)
            missing.append((key, q_text, d_text))
    for start in range(0, len(missing), chunk):
        block = missing[start : start + chunk]
        scores = np.asarray(scorer([(q, d) for _, q, d in block]), dtype=float)
        if scores.shape != (len(block),):
            raise RuntimeError(f"scorer returned shape {scores.shape} for {len(block)} pairs")
        for (key, _, _), s in zip(block, scores):
            cache.scores[key] = float(s)
        cache.added += len(block)
        cache.save()  # a crash loses at most one chunk


def sentence_transformers_scorer(params: dict) -> tuple[Scorer, dict]:
    """The real scorer, and the ML stack it ran on (defect H4: indexes do not record it)."""
    import sentence_transformers
    import torch
    import transformers
    from sentence_transformers import CrossEncoder

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CrossEncoder(
        params["model"], max_length=int(params["max_length"]), device=device,
        revision=params["revision"],
    )
    if params.get("precision", "fp32") != "fp32":
        raise ValueError("the design runs the cross-encoder in fp32 only")
    batch = int(params["batch_size"])

    def scorer(pairs):
        return model.predict(list(pairs), batch_size=batch, show_progress_bar=False,
                             convert_to_numpy=True)

    stack = {
        "torch": torch.__version__, "transformers": transformers.__version__,
        "sentence_transformers": sentence_transformers.__version__,
        "cuda": torch.version.cuda, "device": device,
        "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
        "model": params["model"], "revision": params["revision"],
    }
    return scorer, stack


def cache_path(work_root, collection: str, params: dict) -> Path:
    slug = params["model"].replace("/", "__")
    return (Path(work_root) / "index" / collection / "_ce_cache"
            / f"{slug}__{params['revision'][:12]}__len{int(params['max_length'])}.parquet")


def run(
    config_path, queryset: str, *, split: str = "dev", work_root="/work", allow_dirty=False,
    scorer: Scorer | None = None, stack: dict | None = None, use_cache: bool = True,
):
    ctx, cfg, components = resolve(config_path, queryset, work_root=work_root)
    if len(components) != 1:
        raise ValueError(f"a CE blend reranks exactly one base run, got {len(components)}")
    base = components[0]
    params = cfg["method"]["params"]
    expected, n_before = expected_queries(ctx, split)
    check_aligned(
        [base], list(zip(expected["_query_key"], expected["_gold_key"])),
        split=split, queryset=queryset,
    )
    if scorer is None:
        scorer, stack = sentence_transformers_scorer(params)

    corpus = pd.read_parquet(ctx.corpus_path, columns=["item_key", "text"])
    doc_text = dict(zip(corpus["item_key"].astype(str), corpus["text"].astype(str)))
    q_texts = expected["text"].astype(str).tolist()
    depth = int(params["depth"])

    cache = ScoreCache(cache_path(work_root, ctx.collection, params) if use_cache else None)
    n_cached_before = len(cache.scores)
    with Timer() as timer:
        requests = []
        for i, record in enumerate(base.records):
            sha = query_sha(q_texts[i])
            for c in record["candidates"][:depth]:
                key = c["index_item_key"]
                requests.append((sha, key, q_texts[i], doc_text[key]))
        score_all(requests, scorer, cache)

        ranked = []
        for i, record in enumerate(base.records):
            sha = query_sha(q_texts[i])
            cands = record["candidates"][:depth]
            keys = [c["index_item_key"] for c in cands]
            ranked.append(blend(
                keys, [float(c["score"]) for c in cands],
                [cache.scores[(sha, k)] for k in keys], float(params["lambda"]),
            ))

    return write_run(
        ctx, split=split, expected=expected, n_before=n_before, ranked=ranked,
        components=components,
        extra_meta={
            "family": "ce_blend", "ce_params": params, "ml_stack": stack,
            "ce_pairs_scored": cache.added, "ce_pairs_from_cache": len(requests) - cache.added,
            "ce_cache_entries_before": n_cached_before,
        },
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
