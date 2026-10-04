"""Does a ColBERT query's score depend on which texts share its encoding request? — logged re-measurement for D-060.

S11 A2 measured this once on `stacked_texto` and did not log it (S11 audit, unverifiable item). This script repeats
it with the protocol fixed here and writes everything it saw to `logs/S11/colbert_batch_dependence.json`.

Protocol. Reference: `runs/OE/{base}/bge_m3_colbert__OE`. `n` queries are drawn from the run with a fixed seed.
Each is encoded under four conditions, and for each the query's stored top-100 documents are re-scored with
`colbert_family`'s GPU arithmetic (padded document blocks, as the S11 caches):

- `in_run_block`: inside its own block of the run's query list, in run order (`DEFAULT_BATCH_SIZE`) — how the run
  encoded it. It must reproduce every stored score exactly, or the measurement is invalid and says so.
- `in_run_block_again`: the same block, encoded a second time (is the server repeatable at all?).
- `alone`: the query by itself.
- `sampled_together`: the `n` sampled queries as one request (another batch composition).

Reported per condition, against the stored scores: scores compared, scores that moved, the largest move, and the
queries whose rank 1 or top-10 set changes when their top 100 is re-ordered by the new scores. Per query vector,
the largest per-component difference from `in_run_block`.

    BGE_M3_API=http://172.17.0.1:8800 python src/utils/measure_colbert_batch_dependence.py
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from rerankers.colbert_family import _FamilyOnGPU  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402

RUNS = REPO / "runs" / "OE"
INDEX = REPO / "index" / "OE" / "bge_m3_colbert__OE"
COLBERT = "bge_m3_colbert__OE"
OUT = REPO / "logs" / "S11" / "colbert_batch_dependence.json"
SEED = 20261004
CONDITIONS = ("in_run_block", "in_run_block_again", "alone", "sampled_together")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="stacked_texto")
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()
    if git("status", "--porcelain", "src"):
        raise SystemExit("src/ has uncommitted changes; commit first")
    if not os.getenv("BGE_M3_API"):
        raise SystemExit("set BGE_M3_API to the server the ColBERT runs used")

    run_dir = RUNS / args.base / COLBERT
    with gzip.open(run_dir / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh]
    texts = [r["query_text"] for r in rows]

    from retrievers import bge_m3_colbert as cb
    t0 = time.time()
    searcher = cb.load(INDEX)
    block = cb.DEFAULT_BATCH_SIZE
    picks = sorted(np.random.default_rng(SEED).choice(len(rows), size=args.n, replace=False).tolist())

    # Encodings, by condition, for the sampled run positions.
    enc: dict[str, dict[int, np.ndarray]] = {c: {} for c in CONDITIONS}
    for name in ("in_run_block", "in_run_block_again"):
        for s in sorted({(i // block) * block for i in picks}):
            got = searcher._encode_queries(texts[s : s + block])
            for i in picks:
                if s <= i < s + block:
                    enc[name][i] = got[i - s]
    for i in picks:
        enc["alone"][i] = searcher._encode_queries([texts[i]])[0]
    together = searcher._encode_queries([texts[i] for i in picks])
    for j, i in enumerate(picks):
        enc["sampled_together"][i] = together[j]

    per_query, summary = [], {}
    for c in CONDITIONS:
        summary[c] = {"compared": 0, "moved": 0, "max_abs_score_diff": 0.0, "rank1_changed": 0, "top10_changed": 0,
                      "max_abs_component_diff_vs_in_run_block": 0.0, "shape_differs_from_in_run_block": 0}
    for i in picks:
        row = rows[i]
        doc_ids = np.asarray([int(x["doc_id"]) for x in row["candidates"]], dtype=np.int64)
        stored = np.asarray([float(x["score"]) for x in row["candidates"]], dtype=np.float64)
        fam = _FamilyOnGPU(searcher, doc_ids)
        rec = {"run_position": i, "query_item_key": row["query_item_key"], "candidates": len(doc_ids)}
        base_q = enc["in_run_block"][i]
        for c in CONDITIONS:
            Q = enc[c][i]
            sc = fam.score(searcher, Q).astype(np.float64)
            d = np.abs(sc - stored)
            r1 = int(doc_ids[int(np.argmax(sc))]) != int(doc_ids[int(np.argmax(stored))])
            t10 = set(doc_ids[np.argsort(-sc, kind="stable")[:10]].tolist()) != set(
                doc_ids[np.argsort(-stored, kind="stable")[:10]].tolist())
            same_shape = Q.shape == base_q.shape
            comp = float(np.max(np.abs(Q.astype(np.float64) - base_q.astype(np.float64)))) if same_shape else None
            rec[c] = {"moved": int((d > 0).sum()), "max_abs_score_diff": float(d.max()), "rank1_changed": r1,
                      "top10_changed": t10, "shape": list(Q.shape), "max_abs_component_diff_vs_in_run_block": comp}
            s = summary[c]
            s["compared"] += len(d); s["moved"] += int((d > 0).sum())
            s["max_abs_score_diff"] = max(s["max_abs_score_diff"], float(d.max()))
            s["rank1_changed"] += int(r1); s["top10_changed"] += int(t10)
            if same_shape:
                s["max_abs_component_diff_vs_in_run_block"] = max(s["max_abs_component_diff_vs_in_run_block"], comp)
            else:
                s["shape_differs_from_in_run_block"] += 1
        del fam
        per_query.append(rec)
    cb.torch.cuda.empty_cache()

    valid = summary["in_run_block"]["moved"] == 0
    import torch
    out = {
        "what": "ColBERT query-encoding batch dependence, logged re-measurement of S11 A2 (D-060 condition)",
        "valid": valid,
        "validity_rule": "in_run_block must reproduce every stored score exactly",
        "base": args.base, "reference_run": f"runs/OE/{args.base}/{COLBERT}",
        "reference_results_sha256": sha256_file(run_dir / "results_top100.jsonl.gz"),
        "run_queries": len(rows), "n": args.n, "seed": SEED, "encode_block": block,
        "doc_block": cb.DOC_BLOCK, "dtype": str(cb.DTYPE), "tq_cap": cb.TQ_CAP, "td_cap": cb.TD_CAP,
        "bge_m3_api": os.getenv("BGE_M3_API"), "code_commit": git("rev-parse", "HEAD"),
        "torch": torch.__version__, "cuda_device": torch.cuda.get_device_name(0), "python": platform.python_version(),
        "seconds": round(time.time() - t0, 1),
        "summary": summary, "per_query": per_query,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"valid: {valid}")
    for c in CONDITIONS:
        s = summary[c]
        print(f"{c:20s} moved {s['moved']:5d} of {s['compared']:5d}  max |Δscore| {s['max_abs_score_diff']:.4f}  "
              f"rank-1 changed {s['rank1_changed']:2d}  top-10 changed {s['top10_changed']:2d}  "
              f"max |Δcomponent| {s['max_abs_component_diff_vs_in_run_block']:.4f}  "
              f"shape differs {s['shape_differs_from_in_run_block']}")
    print(f"wrote {OUT.relative_to(REPO)} (sha256 {sha256_file(OUT)})")
    if not valid:
        raise SystemExit("in_run_block did not reproduce the stored scores: the measurement is invalid")


if __name__ == "__main__":
    main()
