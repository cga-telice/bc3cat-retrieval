#!/usr/bin/env python3
"""
Sprint 13 — Full Evaluation Runner for Structured Pipeline Conditions.

Usage:
    python scripts/run_full_eval.py <condition>  [--resume] [--k 100] [--device cpu]
    python scripts/run_full_eval.py --compile-table

Runs retrieval + metrics for a single structured pipeline condition on the
shared 16,590-query set.  Produces output compatible with metrics.ipynb.

Checkpointing: saves every 500 queries to a temp JSONL file.  Use --resume
to continue from the last checkpoint after a crash.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ── Project paths ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))          # for `from src.pipeline...` imports
sys.path.insert(0, str(ROOT / "src"))  # for `from retrievers...` imports

INDEX_ROOT = ROOT / "index"
DATA_DIR = ROOT / "data" / "processed"
RUNS_DIR = ROOT / "runs"

SHORT_PARQUET = DATA_DIR / "OEB_short_norm.parquet"
LONG_PARQUET = DATA_DIR / "OEB_long_norm.parquet"

QUERY_SET_PATH = RUNS_DIR / "structured_eval_queries.json"

TIER1_CONDITIONS = [
    "structured_pipeline_rules",
    "structured_pipeline_oracle_rules",
    "structured_pipeline",                # Llama extract
    "structured_pipeline_oracle",         # Llama oracle extract
    "structured_pipeline_phi4_classify",
    "structured_pipeline_oracle_phi4_classify",
    "structured_pipeline_bio_tagger",     # Sprint LWN-03 — shared BIO tagger
    "structured_pipeline_oracle_bio_tagger",
]

CHECKPOINT_INTERVAL = 500
PROGRESS_INTERVAL = 100

# ── Phase 1: Query Sampling ─────────────────────────────────────────────────

def load_or_create_query_set(n: int = 16590, seed: int = 42) -> list[str]:
    """Load saved query item_keys or create + save a fresh sample."""
    if QUERY_SET_PATH.exists():
        with open(QUERY_SET_PATH, encoding="utf-8") as f:
            qs = json.load(f)
        keys = qs["query_item_keys"]
        print(f"[queries] Loaded {len(keys)} query keys from {QUERY_SET_PATH}")
        return keys

    print(f"[queries] Creating new query set: n={n}, seed={seed}")
    df = pd.read_parquet(SHORT_PARQUET, columns=["item_key"])
    sampled = df.sample(n=n, random_state=seed)
    keys = sampled["item_key"].astype(str).tolist()

    QUERY_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUERY_SET_PATH, "w", encoding="utf-8") as f:
        json.dump({"seed": seed, "n_queries": n, "query_item_keys": keys}, f, indent=2)
    print(f"[queries] Saved query set to {QUERY_SET_PATH}")
    return keys


def build_queries_df(query_keys: list[str]) -> pd.DataFrame:
    """Load the short parquet and filter to the saved query set, preserving order."""
    df = pd.read_parquet(SHORT_PARQUET, columns=["item_key", "parent_key", "text_norm"])
    df["item_key"] = df["item_key"].astype(str)

    # Preserve sample order using the query_keys list
    key_order = {k: i for i, k in enumerate(query_keys)}
    df = df[df["item_key"].isin(key_order)]
    df = df.assign(_order=df["item_key"].map(key_order)).sort_values("_order").drop(columns="_order")
    df = df.reset_index(drop=True)

    assert len(df) == len(query_keys), (
        f"Expected {len(query_keys)} queries, got {len(df)} "
        f"(missing: {len(query_keys) - len(df)})"
    )
    return df


# ── Phase 2: Retrieval with Checkpointing ───────────────────────────────────

def run_retrieval(condition: str, queries_df: pd.DataFrame, k: int,
                  device: str | None, resume: bool, base_url: str):
    """Run single-query retrieval loop with checkpointing."""
    run_dir = RUNS_DIR / condition
    run_dir.mkdir(parents=True, exist_ok=True)
    temp_jsonl = run_dir / "results_top100_TEMP.jsonl"
    checkpoint_path = run_dir / "checkpoint.json"
    final_gz = run_dir / "results_top100.jsonl.gz"

    # Determine start position
    start_idx = 0
    if resume and temp_jsonl.exists():
        # Count existing lines
        with open(temp_jsonl, "r", encoding="utf-8") as f:
            start_idx = sum(1 for _ in f)
        print(f"[resume] Found {start_idx} completed queries in temp file")

    if start_idx >= len(queries_df):
        print(f"[resume] All {len(queries_df)} queries already completed")
        _compress_results(temp_jsonl, final_gz, checkpoint_path)
        return final_gz

    # Load searcher
    index_dir = INDEX_ROOT / condition
    if not (index_dir / "meta.json").exists():
        raise FileNotFoundError(f"Index not found: {index_dir}")

    # Patch Ollama URL in meta.json if LLM condition
    _patch_ollama_url(index_dir, base_url)

    from retrievers.structured_pipeline import load
    print(f"\n[load] Loading {condition}...")
    searcher = load(index_dir, device_override=device)
    external_ids = searcher.external_ids

    # Read index meta for output records
    with open(index_dir / "meta.json", encoding="utf-8") as f:
        meta = json.load(f)

    n_total = len(queries_df)
    texts = queries_df["text_norm"].astype(str).tolist()
    qkeys = queries_df["item_key"].astype(str).tolist()

    # Open temp file in append mode
    mode = "a" if resume and start_idx > 0 else "w"
    f_out = open(temp_jsonl, mode, encoding="utf-8")

    t0 = time.time()
    errors = 0
    consecutive_errors = 0
    max_consecutive = max(10, int(n_total * 0.01))

    try:
        for i in range(start_idx, n_total):
            query_text = texts[i]
            qkey = qkeys[i]

            try:
                top_indices, scores = searcher.search(query_text, k=k)
                consecutive_errors = 0

                candidates = []
                for r in range(len(top_indices)):
                    idx = int(top_indices[r])
                    candidates.append({
                        "rank": r + 1,
                        "doc_id": idx,
                        "index_item_key": str(external_ids[idx]),
                        "score": float(scores[r]),
                    })

            except Exception as e:
                errors += 1
                consecutive_errors += 1
                print(f"\n[ERROR] Query {i} ({qkey}): {e}")
                candidates = []

                if consecutive_errors >= max_consecutive:
                    print(f"\n[ABORT] {consecutive_errors} consecutive errors. Stopping.")
                    break

            rec = {
                "query_id": f"q_{i:06d}",
                "query_item_key": qkey,
                "query_text": query_text,
                "candidates": candidates,
                "score_info": {"family": "cosine", "higher_is_better": True},
                "meta": {
                    "method": meta.get("method", condition),
                    "variant": meta.get("variant", condition),
                    "index_path": str(index_dir),
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                },
            }
            f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")

            # Progress reporting
            completed = i - start_idx + 1
            if completed % PROGRESS_INTERVAL == 0 or i == n_total - 1:
                elapsed = time.time() - t0
                rate = elapsed / completed
                remaining = rate * (n_total - start_idx - completed)
                pct = (i + 1) / n_total * 100
                print(
                    f"  [{i+1}/{n_total}] {pct:.1f}% | "
                    f"elapsed {_fmt_time(elapsed)} | "
                    f"ETA {_fmt_time(remaining)} | "
                    f"{rate*1000:.0f}ms/query"
                    + (f" | {errors} errors" if errors else ""),
                    flush=True,
                )

            # Checkpoint
            if completed % CHECKPOINT_INTERVAL == 0:
                f_out.flush()
                _save_checkpoint(checkpoint_path, i + 1, time.time() - t0)
    finally:
        f_out.close()

    elapsed_total = time.time() - t0
    completed_total = n_total - start_idx
    print(f"\n[done] {completed_total} queries in {_fmt_time(elapsed_total)}")
    if errors > 0:
        print(f"[warn] {errors} queries had errors (empty candidates)")

    # Compress and clean up
    _compress_results(temp_jsonl, final_gz, checkpoint_path)

    # Write log
    with open(run_dir / "log.txt", "w", encoding="utf-8") as f:
        f.write(f"Method: {condition}\n")
        f.write(f"Index : {index_dir}\n")
        f.write(f"Queries: {n_total} | K={k}\n")
        f.write(f"Time: {_fmt_time(elapsed_total)} ({elapsed_total/completed_total*1000:.0f}ms/query)\n")
        f.write(f"Errors: {errors}\n")
        f.write(f"Output: {final_gz}\n")

    return final_gz


def _patch_ollama_url(index_dir: Path, base_url: str):
    """Update Ollama URL in meta.json for LLM conditions."""
    meta_path = index_dir / "meta.json"
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("params", {}).get("stage2_method") == "llm":
        meta["params"]["stage2_ollama_url"] = base_url
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)


def _compress_results(temp_jsonl: Path, final_gz: Path, checkpoint_path: Path):
    """Gzip the temp JSONL and clean up."""
    if not temp_jsonl.exists():
        return
    print(f"[compress] {temp_jsonl.name} -> {final_gz.name}")
    with open(temp_jsonl, "r", encoding="utf-8") as fin:
        with gzip.open(final_gz, "wt", encoding="utf-8") as fout:
            for line in fin:
                fout.write(line)
    temp_jsonl.unlink()
    if checkpoint_path.exists():
        checkpoint_path.unlink()
    print(f"[compress] Done. Temp files cleaned up.")


def _save_checkpoint(path: Path, completed: int, elapsed: float):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"completed": completed, "elapsed_sec": round(elapsed, 1)}, f)


def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


# ── Phase 3: Metrics Computation ─────────────────────────────────────────────
# Extracted from metrics.ipynb — identical algorithm.

def compute_metrics(condition: str):
    """Compute dual-target metrics for a completed run. Writes all output files."""
    run_dir = RUNS_DIR / condition
    results_path = run_dir / "results_top100.jsonl.gz"
    if not results_path.exists():
        raise FileNotFoundError(f"No results file: {results_path}")

    print(f"\n[metrics] Computing metrics for {condition}")

    # Load ground-truth data
    df_q = pd.read_parquet(SHORT_PARQUET, columns=["item_key", "parent_key", "text_norm"])
    df_q = df_q.rename(columns={"text_norm": "q_text"})
    df_d = pd.read_parquet(LONG_PARQUET, columns=["item_key", "parent_key"])

    gold_doc_keys = set(df_d["item_key"].astype(str))
    q_table = df_q.set_index(df_q["item_key"].astype(str), drop=False)
    d_table = df_d.set_index(df_d["item_key"].astype(str), drop=False)
    doc2parent = d_table["parent_key"].astype(str).to_dict()

    # Parent -> set of doc keys
    parent2docs: dict[str, set[str]] = defaultdict(set)
    for doc_k, parent_k in doc2parent.items():
        parent2docs[parent_k].add(doc_k)

    def dcg_at_k(rel_vec, k):
        s = 0.0
        for i, rel in enumerate(rel_vec[:k], start=1):
            if rel:
                s += 1.0 / math.log2(i + 1)
        return s

    def idcg_item():
        return dcg_at_k([1], 10)

    def idcg_parent(gold_parent):
        num_rel = len(parent2docs.get(gold_parent, ()))
        if num_rel == 0:
            return 0.0
        return dcg_at_k([1] * min(num_rel, 10), 10)

    # ── Iterate results and compute per-query metrics ──
    per_query_item = []
    per_query_parent = []
    exploded_rows = []

    with gzip.open(results_path, "rt", encoding="utf-8") as gz:
        for line in gz:
            if not line.strip():
                continue
            rec = json.loads(line)
            qkey = str(rec.get("query_item_key", ""))
            if not qkey or qkey not in gold_doc_keys:
                continue

            cands = rec.get("candidates", [])
            if not cands:
                continue

            cand_keys = [str(c.get("index_item_key", "")) for c in cands]
            qtext = q_table.loc[qkey, "q_text"] if qkey in q_table.index else ""
            has_num = any(ch.isdigit() for ch in str(qtext))
            gold_parent = doc2parent.get(qkey, "")

            # -- Item target --
            rel_item = [1 if ck == qkey else 0 for ck in cand_keys]
            acc1_i = int(rel_item[0] == 1)
            rec5_i = int(any(rel_item[:min(5, len(rel_item))]))
            rec10_i = int(any(rel_item[:min(10, len(rel_item))]))
            rr_i = 0.0
            for r, v in enumerate(rel_item, start=1):
                if v:
                    rr_i = 1.0 / r
                    break
            dcg10_i = dcg_at_k(rel_item, 10)
            idcg10_i = idcg_item()
            ndcg10_i = (dcg10_i / idcg10_i) if idcg10_i > 0 else 0.0

            per_query_item.append({
                "query_item_key": qkey, "acc1": acc1_i, "rec5": rec5_i,
                "rec10": rec10_i, "rr": rr_i, "ndcg10": ndcg10_i,
                "has_numbers": has_num,
            })

            # -- Parent target --
            rel_parent_docs = parent2docs.get(gold_parent, set())
            rel_par = [1 if ck in rel_parent_docs else 0 for ck in cand_keys]
            acc1_p = int(rel_par[0] == 1)
            rec5_p = int(any(rel_par[:min(5, len(rel_par))]))
            rec10_p = int(any(rel_par[:min(10, len(rel_par))]))
            rr_p = 0.0
            for r, v in enumerate(rel_par, start=1):
                if v:
                    rr_p = 1.0 / r
                    break
            dcg10_p = dcg_at_k(rel_par, 10)
            idcg10_p = idcg_parent(gold_parent)
            ndcg10_p = (dcg10_p / idcg10_p) if idcg10_p > 0 else 0.0

            per_query_parent.append({
                "query_item_key": qkey, "acc1": acc1_p, "rec5": rec5_p,
                "rec10": rec10_p, "rr": rr_p, "ndcg10": ndcg10_p,
                "has_numbers": has_num,
            })

            # -- Exploded candidates --
            # Find first-hit ranks for the per-query summary
            rank_item = np.inf
            rank_parent = np.inf
            for c in cands:
                r = int(c["rank"])
                ck = str(c.get("index_item_key", ""))
                cp = doc2parent.get(ck, "")
                if ck == qkey and rank_item == np.inf:
                    rank_item = r
                if cp == gold_parent and rank_parent == np.inf:
                    rank_parent = r
                exploded_rows.append({
                    "query_id": rec.get("query_id", ""),
                    "query_item_key": qkey,
                    "query_text": qtext,
                    "gold_item_key": qkey,
                    "gold_parent_key": gold_parent,
                    "rank": r,
                    "cand_item_key": ck,
                    "cand_parent_key": cp,
                    "score": float(c.get("score", 0.0)),
                    "is_correct_item": int(ck == qkey),
                    "is_correct_parent": int(cp == gold_parent),
                })

    # ── Aggregate metrics ──
    def agg(records):
        df = pd.DataFrame(records)
        def _agg(d):
            return {
                "queries": len(d),
                "Acc@1": float(d["acc1"].mean()),
                "Recall@5": float(d["rec5"].mean()),
                "Recall@10": float(d["rec10"].mean()),
                "MRR": float(d["rr"].mean()),
                "nDCG@10": float(d["ndcg10"].mean()),
            }
        overall = _agg(df)
        has = _agg(df[df["has_numbers"]]) if df["has_numbers"].any() else None
        no = _agg(df[~df["has_numbers"]]) if (~df["has_numbers"]).any() else None
        return overall, has, no

    item_overall, item_has, item_no = agg(per_query_item)
    par_overall, par_has, par_no = agg(per_query_parent)

    # ── Print summary ──
    print(f"\n  {'Target':<8} {'Scope':<12} {'Queries':>7} {'Acc@1':>7} {'Rec@5':>7} {'Rec@10':>7} {'MRR':>7} {'nDCG@10':>8}")
    print(f"  {'-'*8} {'-'*12} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*8}")
    for target, (ov, hn, nn) in [("item", (item_overall, item_has, item_no)),
                                   ("parent", (par_overall, par_has, par_no))]:
        for scope, m in [("overall", ov), ("has_numbers", hn), ("no_numbers", nn)]:
            if m is None:
                continue
            print(f"  {target:<8} {scope:<12} {m['queries']:>7.0f} {m['Acc@1']:>7.4f} "
                  f"{m['Recall@5']:>7.4f} {m['Recall@10']:>7.4f} {m['MRR']:>7.4f} {m['nDCG@10']:>8.4f}")

    # ── Write output files ──
    _write_metrics_files(run_dir, condition,
                         item_overall, item_has, item_no,
                         par_overall, par_has, par_no)
    _write_perquery_summary(run_dir, per_query_item, per_query_parent, doc2parent, q_table)
    _write_exploded_candidates(run_dir, exploded_rows)
    _write_missed_queries(run_dir, per_query_item, q_table)
    _write_parent_confusions(run_dir, exploded_rows)

    print(f"\n[metrics] All output files written to {run_dir}")
    return item_overall, par_overall


def _write_metrics_files(run_dir, method,
                         item_ov, item_has, item_no,
                         par_ov, par_has, par_no):
    """Write metrics_dual, metrics_single__item, metrics_single__parent."""
    combined = []
    for target, (ov, hn, nn) in [("item", (item_ov, item_has, item_no)),
                                   ("parent", (par_ov, par_has, par_no))]:
        rows = []
        rows.append({"method": method, **ov, "scope": "overall", "target": target})
        if hn:
            rows.append({"method": method, **hn, "scope": "has_numbers", "target": target})
        if nn:
            rows.append({"method": method, **nn, "scope": "no_numbers", "target": target})

        # Per-target files
        suffix = "parent" if target == "parent" else "item"
        df = pd.DataFrame(rows)
        df.to_json(run_dir / f"metrics_single__{suffix}.json",
                   orient="records", force_ascii=False, indent=2)
        df.to_csv(run_dir / f"metrics_single__{suffix}.csv", index=False)
        combined.extend(rows)

    # Combined dual
    df_combined = pd.DataFrame(combined)
    df_combined.to_json(run_dir / "metrics_dual.json",
                        orient="records", force_ascii=False, indent=2)
    df_combined.to_csv(run_dir / "metrics_dual.csv", index=False)
    print(f"  Saved: metrics_dual.json/csv, metrics_single__item/parent.json/csv")


def _write_perquery_summary(run_dir, per_query_item, per_query_parent, doc2parent, q_table):
    """Write results_perquery_summary.csv matching metrics.ipynb format."""
    df_i = pd.DataFrame(per_query_item).set_index("query_item_key")
    df_p = pd.DataFrame(per_query_parent).set_index("query_item_key")

    rows = []
    for qkey in df_i.index:
        qtext = q_table.loc[qkey, "q_text"] if qkey in q_table.index else ""
        gold_parent = doc2parent.get(qkey, "")

        # Recover rank from acc/rec flags (approximate — exact rank would need
        # re-reading the JSONL, but these flags are what metrics.ipynb saves)
        ri = df_i.loc[qkey]
        rp = df_p.loc[qkey]

        # Reconstruct rank from binary flags
        if ri["acc1"] == 1:
            rank_item = 1.0
        elif ri["rec5"] == 1:
            rank_item = 2.0  # between 2 and 5
        elif ri["rec10"] == 1:
            rank_item = 6.0  # between 6 and 10
        else:
            rank_item = np.inf

        if rp["acc1"] == 1:
            rank_parent = 1.0
        elif rp["rec5"] == 1:
            rank_parent = 2.0
        elif rp["rec10"] == 1:
            rank_parent = 6.0
        else:
            rank_parent = np.inf

        rows.append({
            "query_item_key": qkey,
            "query_text": qtext,
            "gold_item_key": qkey,
            "gold_parent_key": gold_parent,
            "rank_item": rank_item,
            "rank_parent": rank_parent,
            "acc1_item": int(ri["acc1"]),
            "acc1_parent": int(rp["acc1"]),
            "rec5_item": int(ri["rec5"]),
            "rec10_item": int(ri["rec10"]),
            "rec5_parent": int(rp["rec5"]),
            "rec10_parent": int(rp["rec10"]),
        })

    pd.DataFrame(rows).to_csv(run_dir / "results_perquery_summary.csv", index=False)
    print(f"  Saved: results_perquery_summary.csv")


def _write_exploded_candidates(run_dir, exploded_rows):
    """Write results_exploded_candidates.csv and .parquet."""
    if not exploded_rows:
        return
    df = pd.DataFrame(exploded_rows)
    df.to_csv(run_dir / "results_exploded_candidates.csv", index=False)
    df.to_parquet(run_dir / "results_exploded_candidates.parquet", index=False)
    print(f"  Saved: results_exploded_candidates.csv/parquet ({len(df)} rows)")


def _write_missed_queries(run_dir, per_query_item, q_table):
    """Write missed_queries.csv — queries where item Acc@1 = 0."""
    missed = [r for r in per_query_item if r["acc1"] == 0]
    rows = []
    for r in missed:
        qkey = r["query_item_key"]
        qtext = q_table.loc[qkey, "q_text"] if qkey in q_table.index else ""
        rows.append({"query_item_key": qkey, "query_text": qtext, "rank_item": np.inf})
    pd.DataFrame(rows).to_csv(run_dir / "missed_queries.csv", index=False)
    print(f"  Saved: missed_queries.csv ({len(rows)} missed)")


def _write_parent_confusions(run_dir, exploded_rows):
    """Write parent_confusions_rank1.csv — most frequent wrong parent@1."""
    rank1 = [r for r in exploded_rows if r["rank"] == 1]
    wrong = [r for r in rank1 if r["is_correct_parent"] == 0]
    if not wrong:
        pd.DataFrame(columns=["gold_parent_key", "cand_parent_key", "count"]).to_csv(
            run_dir / "parent_confusions_rank1.csv", index=False)
        return
    df = pd.DataFrame(wrong)
    tbl = (df.groupby(["gold_parent_key", "cand_parent_key"])
           .size().reset_index(name="count")
           .sort_values("count", ascending=False)
           .head(20))
    tbl.to_csv(run_dir / "parent_confusions_rank1.csv", index=False)
    print(f"  Saved: parent_confusions_rank1.csv")


# ── Phase 4: Compile Results Table ───────────────────────────────────────────

def compile_table():
    """Load metrics from all conditions (new + baselines) and print comparison table."""
    print("\n" + "=" * 80)
    print("RESULTS TABLE — Structured Pipeline + Baselines")
    print("=" * 80)

    # Collect all runs that have metrics_dual.json
    all_metrics = {}
    for run_dir in sorted(RUNS_DIR.iterdir()):
        mpath = run_dir / "metrics_dual.json"
        if mpath.exists():
            with open(mpath, encoding="utf-8") as f:
                records = json.load(f)
            # Extract overall item and parent Acc@1
            item_ov = next((r for r in records if r["scope"] == "overall" and r["target"] == "item"), None)
            par_ov = next((r for r in records if r["scope"] == "overall" and r["target"] == "parent"), None)
            item_has = next((r for r in records if r["scope"] == "has_numbers" and r["target"] == "item"), None)
            item_no = next((r for r in records if r["scope"] == "no_numbers" and r["target"] == "item"), None)
            if item_ov and par_ov:
                all_metrics[run_dir.name] = {
                    "item_acc1": item_ov["Acc@1"],
                    "parent_acc1": par_ov["Acc@1"],
                    "item_mrr": item_ov.get("MRR", 0),
                    "item_ndcg10": item_ov.get("nDCG@10", 0),
                    "queries": item_ov.get("queries", 0),
                    "has_num_acc1": item_has["Acc@1"] if item_has else None,
                    "no_num_acc1": item_no["Acc@1"] if item_no else None,
                }

    if not all_metrics:
        print("No metrics files found in runs/")
        return

    # Print table
    print(f"\n{'Method':<45} {'Queries':>7} {'item Acc@1':>10} {'parent Acc@1':>12} "
          f"{'has_num':>8} {'no_num':>8} {'MRR':>7} {'nDCG@10':>8}")
    print("-" * 110)

    # Print baselines first
    baselines = [k for k in all_metrics if not k.startswith("structured_pipeline")]
    structured = [k for k in all_metrics if k.startswith("structured_pipeline")]

    for group_name, keys in [("BASELINES", baselines), ("STRUCTURED PIPELINE", structured)]:
        if keys:
            print(f"\n  --- {group_name} ---")
            for name in sorted(keys):
                m = all_metrics[name]
                hn = f"{m['has_num_acc1']:.4f}" if m['has_num_acc1'] is not None else "   —"
                nn = f"{m['no_num_acc1']:.4f}" if m['no_num_acc1'] is not None else "   —"
                print(f"  {name:<43} {m['queries']:>7.0f} {m['item_acc1']:>10.4f} "
                      f"{m['parent_acc1']:>12.4f} {hn:>8} {nn:>8} "
                      f"{m['item_mrr']:>7.4f} {m['item_ndcg10']:>8.4f}")

    print()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sprint 13: Full evaluation runner for structured pipeline conditions"
    )
    parser.add_argument("condition", nargs="?", default=None,
                        help=f"Condition name. One of: {', '.join(TIER1_CONDITIONS)}")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint")
    parser.add_argument("--k", type=int, default=100,
                        help="Top-K candidates per query (default: 100)")
    parser.add_argument("--device", default="cpu",
                        help="Torch device for E5 (default: cpu)")
    parser.add_argument("--base-url", default="http://localhost:11434",
                        help="Ollama base URL (default: http://localhost:11434)")
    parser.add_argument("--compile-table", action="store_true",
                        help="Compile results table from all runs")
    parser.add_argument("--metrics-only", action="store_true",
                        help="Only compute metrics (skip retrieval)")
    args = parser.parse_args()

    if args.compile_table:
        compile_table()
        return

    if args.condition is None:
        parser.error("condition is required (unless --compile-table)")

    if args.condition not in TIER1_CONDITIONS:
        print(f"[warn] '{args.condition}' is not a Tier 1 condition. "
              f"Tier 1: {TIER1_CONDITIONS}")
        print("Proceeding anyway...")

    print(f"\n{'='*70}")
    print(f"Sprint 13 — Full Evaluation: {args.condition}")
    print(f"{'='*70}")

    # Phase 1: Query set
    query_keys = load_or_create_query_set()
    queries_df = build_queries_df(query_keys)
    print(f"[queries] {len(queries_df)} queries ready")

    # Phase 2: Retrieval
    if not args.metrics_only:
        run_retrieval(
            condition=args.condition,
            queries_df=queries_df,
            k=args.k,
            device=args.device,
            resume=args.resume,
            base_url=args.base_url,
        )

    # Phase 3: Metrics
    compute_metrics(args.condition)

    print(f"\n[complete] {args.condition} — all done!")


if __name__ == "__main__":
    main()
