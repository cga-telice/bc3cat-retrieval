"""Verify item-level E5 index as Stage 1 of the structured pipeline.

Loads the existing item-level E5 index (index/dense_e5/, 47,514 vectors),
retrieves top-1 for a sample of queries, derives parent_key from the
item_key, and reports parent-level Acc@1.

Expected: ~98% parent Acc@1 (matching published benchmark).

Usage::

    python -m src.pipeline.verify_stage1
    python -m src.pipeline.verify_stage1 --n-queries 500
"""

import json
import time
import numpy as np
import pandas as pd
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data" / "processed"
INDEX_DIR = ROOT_DIR / "index" / "dense_e5"


def verify_stage1(index_dir=INDEX_DIR, n_queries=200):
    """Verify item-level E5 retrieval as Stage 1.

    1. Loads DenseE5Searcher from the item-level index
    2. Builds {item_key: parent_key} lookup from parquet
    3. Samples n_queries leaf queries
    4. Retrieves top-1, maps to parent_key, checks against ground truth
    5. Reports parent-level Acc@1
    """
    import sys
    sys.path.insert(0, str(ROOT_DIR))
    from src.retrievers.dense_e5 import load as load_searcher

    # --- Load searcher ---
    print(f"[verify_stage1] Loading item-level E5 index from {index_dir}...")
    searcher = load_searcher(index_dir)
    # Override device to CPU if CUDA is not available (index was built on GPU)
    import torch
    if not torch.cuda.is_available():
        searcher.device = "cpu"
    print(f"[verify_stage1] Index loaded: {searcher.X_docs.shape[0]} vectors, dim={searcher.X_docs.shape[1]}")

    # --- Build item_key -> parent_key lookup from parquet ---
    long_path = DATA_DIR / "OEB_long_norm.parquet"
    print(f"[verify_stage1] Loading parquet for item->parent mapping: {long_path}")
    long_df = pd.read_parquet(long_path, columns=["item_key", "parent_key"])
    item_to_parent = dict(zip(long_df["item_key"], long_df["parent_key"]))
    print(f"[verify_stage1] Lookup dict: {len(item_to_parent)} entries")

    # --- Load and sample queries ---
    queries_path = DATA_DIR / "OEB_short_norm.parquet"
    df = pd.read_parquet(queries_path)

    # Keep only leaf queries (parent_key ending with $)
    df = df[df["parent_key"].str.endswith("$")]
    sample = df.sample(n=min(n_queries, len(df)), random_state=42)

    print(f"[verify_stage1] Evaluating {len(sample)} queries...")

    # --- Batch search ---
    queries = sample["text"].tolist()
    gt_parents = sample["parent_key"].tolist()

    t0 = time.time()
    top_idx, top_sco = searcher.search_batch(queries, k=1)
    elapsed = time.time() - t0

    # --- Evaluate ---
    correct = 0
    failures = {}
    for i in range(len(queries)):
        item_key = searcher.external_ids[top_idx[i, 0]]
        pred_parent = item_to_parent.get(item_key, None)

        if pred_parent == gt_parents[i]:
            correct += 1
        else:
            gt = gt_parents[i]
            failures[gt] = failures.get(gt, 0) + 1

    acc = correct / len(queries)
    print(f"\n[verify_stage1] Results:")
    print(f"  Parent Acc@1 = {correct}/{len(queries)} = {acc:.1%}")
    print(f"  Search time: {elapsed:.2f}s ({elapsed/len(queries)*1000:.1f}ms/query)")

    if failures:
        print(f"\n  Failures by ground-truth parent_key:")
        for pk, count in sorted(failures.items(), key=lambda x: -x[1]):
            print(f"    {pk}: {count}")

    # --- Confirm DenseE5Searcher API for pipeline use ---
    print(f"\n[verify_stage1] API check:")
    single_idx, single_sco = searcher.search(queries[0], k=1)
    item_key = searcher.external_ids[single_idx[0]]
    parent_key = item_to_parent.get(item_key, "UNKNOWN")
    print(f"  searcher.search(query, k=1) -> indices shape={single_idx.shape}, scores shape={single_sco.shape}")
    print(f"  external_ids[idx] -> item_key='{item_key}'")
    print(f"  item_to_parent[item_key] -> parent_key='{parent_key}'")
    print(f"  No adapter needed: DenseE5Searcher can be used directly as Stage 1")

    return acc


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Verify item-level E5 as Stage 1")
    parser.add_argument(
        "--n-queries",
        type=int,
        default=200,
        help="Number of queries to sample (default: 200)",
    )
    args = parser.parse_args()

    verify_stage1(n_queries=args.n_queries)
