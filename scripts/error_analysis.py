#!/usr/bin/env python3
"""
Sprint D1 — Error Analysis for Structured Pipeline.

Classifies every failed query (item Acc@1 = 0) across 6 Tier 1 conditions
into error categories, produces distribution tables and qualitative examples.

Usage:
    python scripts/error_analysis.py
    python scripts/error_analysis.py --rerun-llm
    python scripts/error_analysis.py --conditions structured_pipeline_rules structured_pipeline_oracle_rules
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# ── Project paths ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

DATA_DIR = ROOT / "data" / "processed"
RUNS_DIR = ROOT / "runs"
SHORT_PARQUET = DATA_DIR / "OEB_short_norm.parquet"
LONG_PARQUET = DATA_DIR / "OEB_long_norm.parquet"
SCHEMA_PATH = DATA_DIR / "OEB_concept_schema.json"

TIER1_CONDITIONS = [
    "structured_pipeline_rules",
    "structured_pipeline_oracle_rules",
    "structured_pipeline",
    "structured_pipeline_oracle",
    "structured_pipeline_phi4_classify",
    "structured_pipeline_oracle_phi4_classify",
]


@dataclass
class ConditionConfig:
    name: str
    is_oracle: bool
    stage2_method: str       # "rules" | "llm"
    stage2_model: str | None
    stage2_prompt_mode: str | None


CONDITION_CONFIGS = {
    "structured_pipeline_rules": ConditionConfig(
        "structured_pipeline_rules", False, "rules", None, None),
    "structured_pipeline_oracle_rules": ConditionConfig(
        "structured_pipeline_oracle_rules", True, "rules", None, None),
    "structured_pipeline": ConditionConfig(
        "structured_pipeline", False, "llm", "llama3.1:8b", "extract"),
    "structured_pipeline_oracle": ConditionConfig(
        "structured_pipeline_oracle", True, "llm", "llama3.1:8b", "extract"),
    "structured_pipeline_phi4_classify": ConditionConfig(
        "structured_pipeline_phi4_classify", False, "llm", "phi4:latest", "classify"),
    "structured_pipeline_oracle_phi4_classify": ConditionConfig(
        "structured_pipeline_oracle_phi4_classify", True, "llm", "phi4:latest", "classify"),
}

# Error type constants
E1_WRONG_CONCEPT = "E1-WRONG_CONCEPT"
E2_PARTIAL_EXTRACT = "E2-PARTIAL_EXTRACT"
E2_WRONG_VALUE = "E2-WRONG_VALUE"
E2_ALL_NULL = "E2-ALL_NULL"
E2_UNSPECIFIED = "E2-UNSPECIFIED"
E3_SCHEMA_MISMATCH = "E3-SCHEMA_MISMATCH"
ALL_ERROR_TYPES = [E1_WRONG_CONCEPT, E2_PARTIAL_EXTRACT, E2_WRONG_VALUE,
                   E2_ALL_NULL, E2_UNSPECIFIED, E3_SCHEMA_MISMATCH]


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Data Loading
# ═══════════════════════════════════════════════════════════════════════════════

def get_ground_truth_params(row) -> dict[str, str]:
    """Extract ground-truth {axis_label: value} from a parquet row's parameters column."""
    params = row["parameters"]
    gt = {}
    for axis_key, axis_data in params.items():
        if axis_data is None:
            continue
        label = axis_data["label"].strip()
        value = axis_data["values"][0]["value"].strip()
        gt[label] = value
    return gt


def load_shared_data():
    """Load all shared data needed for error analysis."""
    print("[load] Loading shared data...")

    # Query data
    short_df = pd.read_parquet(SHORT_PARQUET)
    short_df["item_key"] = short_df["item_key"].astype(str)
    short_df["parent_key"] = short_df["parent_key"].astype(str)

    # Schema
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)

    # Doc-to-parent mapping
    long_df = pd.read_parquet(LONG_PARQUET, columns=["item_key", "parent_key"])
    long_df["item_key"] = long_df["item_key"].astype(str)
    long_df["parent_key"] = long_df["parent_key"].astype(str)
    doc2parent = long_df.set_index("item_key")["parent_key"].to_dict()

    # Pre-compute ground-truth parameters for all queries
    gt_params = {}
    for _, row in short_df.iterrows():
        ik = row["item_key"]
        gt_params[ik] = get_ground_truth_params(row)

    # Build schema valid values (lowercased) for E3 check
    schema_valid = {}  # {pk: {axis_label_lower: set(value_lower)}}
    for pk, group in schema.items():
        schema_valid[pk] = {}
        for axis_label, values in group["axes"].items():
            schema_valid[pk][axis_label.strip().lower()] = {
                v.strip().lower() for v in values
            }

    # E3: Find items whose GT parameter values are not in the schema
    schema_mismatch_items = set()
    for ik, gt in gt_params.items():
        pk = doc2parent.get(ik)
        if pk is None or pk not in schema_valid:
            continue
        for axis_label, value in gt.items():
            al = axis_label.strip().lower()
            vl = value.strip().lower()
            valid_set = schema_valid.get(pk, {}).get(al, set())
            if valid_set and vl not in valid_set:
                schema_mismatch_items.add(ik)
                break

    # Query counts per parent_key (for Table B)
    query_counts_by_parent = short_df.groupby("parent_key").size().to_dict()

    print(f"  Queries: {len(short_df)}")
    print(f"  Concept groups: {len(schema)}")
    print(f"  Schema mismatches: {len(schema_mismatch_items)}")

    return {
        "short_df": short_df,
        "schema": schema,
        "doc2parent": doc2parent,
        "gt_params": gt_params,
        "schema_valid": schema_valid,
        "schema_mismatch_items": schema_mismatch_items,
        "query_counts_by_parent": query_counts_by_parent,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: Error Classification
# ═══════════════════════════════════════════════════════════════════════════════

def _compare_params(extracted: dict[str, str | None],
                    ground_truth: dict[str, str]) -> tuple[str, list[str]]:
    """Compare extracted params to ground truth, return (error_type, mismatched_axes)."""
    if not ground_truth:
        return E2_ALL_NULL, []

    non_null_count = sum(1 for v in extracted.values() if v is not None)
    if non_null_count == 0:
        return E2_ALL_NULL, list(ground_truth.keys())

    mismatched = []
    has_wrong_value = False
    for axis_label, gt_val in ground_truth.items():
        ext_val = extracted.get(axis_label)
        if ext_val is None:
            mismatched.append(axis_label)
        elif ext_val.strip().lower() != gt_val.strip().lower():
            mismatched.append(axis_label)
            has_wrong_value = True

    if not mismatched:
        # All axes match — shouldn't happen for a failed query, but safety net
        return E2_PARTIAL_EXTRACT, []

    if has_wrong_value:
        return E2_WRONG_VALUE, mismatched

    return E2_PARTIAL_EXTRACT, mismatched


def classify_errors_for_condition(
    config: ConditionConfig,
    shared: dict,
    rerun_llm: bool = False,
    ollama_url: str = "http://localhost:11434",
) -> pd.DataFrame:
    """Classify all failed queries for one condition."""
    run_dir = RUNS_DIR / config.name
    print(f"\n[classify] {config.name}")

    # Load per-query summary to find failed queries
    summary_path = run_dir / "results_perquery_summary.csv"
    if not summary_path.exists():
        print(f"  WARNING: {summary_path} not found, skipping")
        return pd.DataFrame()

    summary = pd.read_csv(summary_path)
    summary["query_item_key"] = summary["query_item_key"].astype(str)
    failed = summary[summary["acc1_item"] == 0].copy()
    print(f"  Total queries: {len(summary)}, failed: {len(failed)}")

    if len(failed) == 0:
        return pd.DataFrame()

    # Load exploded candidates for rank-1 info
    exploded_path = run_dir / "results_exploded_candidates.csv"
    if exploded_path.exists():
        exploded = pd.read_csv(exploded_path)
        exploded["query_item_key"] = exploded["query_item_key"].astype(str)
        exploded["cand_parent_key"] = exploded["cand_parent_key"].astype(str)
        exploded["cand_item_key"] = exploded["cand_item_key"].astype(str)
        rank1 = exploded[exploded["rank"] == 1].set_index("query_item_key")
    else:
        # Fall back to parquet
        exploded_pq = run_dir / "results_exploded_candidates.parquet"
        exploded = pd.read_parquet(exploded_pq)
        exploded["query_item_key"] = exploded["query_item_key"].astype(str)
        exploded["cand_parent_key"] = exploded["cand_parent_key"].astype(str)
        exploded["cand_item_key"] = exploded["cand_item_key"].astype(str)
        rank1 = exploded[exploded["rank"] == 1].set_index("query_item_key")

    # Initialize extractor for rules conditions (or LLM if --rerun-llm)
    extractor = None
    can_sub_classify = False

    if config.stage2_method == "rules":
        from src.pipeline.param_extractor_rules import RuleBasedParamExtractor
        extractor = RuleBasedParamExtractor(SCHEMA_PATH)
        can_sub_classify = True
    elif config.stage2_method == "llm" and rerun_llm:
        try:
            import requests
            resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
            resp.raise_for_status()
            from src.pipeline.param_extractor import LLMParamExtractor
            extractor = LLMParamExtractor(
                ollama_base_url=ollama_url,
                model=config.stage2_model,
                prompt_mode=config.stage2_prompt_mode,
            )
            can_sub_classify = True
            print(f"  LLM extractor loaded: {config.stage2_model} ({config.stage2_prompt_mode})")
        except Exception as e:
            print(f"  WARNING: Could not load LLM extractor: {e}")
            print(f"  Falling back to E2-UNSPECIFIED for this condition")

    gt_params = shared["gt_params"]
    doc2parent = shared["doc2parent"]
    schema_mismatch_items = shared["schema_mismatch_items"]
    short_df = shared["short_df"]

    # Build query text lookup
    text_lookup = short_df.set_index("item_key")["text_norm"].astype(str).to_dict()
    # Also keep raw text for LLM extraction
    if "text" in short_df.columns:
        text_raw_lookup = short_df.set_index("item_key")["text"].astype(str).to_dict()
    else:
        text_raw_lookup = text_lookup

    rows = []
    e2_rerun_count = 0

    for _, frow in failed.iterrows():
        qik = str(frow["query_item_key"])
        gold_pk = str(frow["gold_parent_key"])
        qtext = text_lookup.get(qik, str(frow.get("query_text", "")))

        # Get rank-1 candidate info
        if qik in rank1.index:
            r1 = rank1.loc[qik]
            # Handle potential duplicate index
            if isinstance(r1, pd.DataFrame):
                r1 = r1.iloc[0]
            rank1_pk = str(r1["cand_parent_key"])
            rank1_ik = str(r1["cand_item_key"])
        else:
            rank1_pk = ""
            rank1_ik = ""

        gt = gt_params.get(qik, {})
        extracted = None
        mismatched_axes = []

        # E1 check: wrong concept group at rank 1
        if rank1_pk and rank1_pk != gold_pk:
            error_type = E1_WRONG_CONCEPT
        # E3 check: schema mismatch
        elif qik in schema_mismatch_items:
            error_type = E3_SCHEMA_MISMATCH
        # E2: extraction error — sub-classify if possible
        elif can_sub_classify and extractor is not None:
            # Pipeline used text_norm for all methods (see run_full_eval.py line 140)
            extract_text = qtext
            extracted = extractor.extract(gold_pk, extract_text)
            error_type, mismatched_axes = _compare_params(extracted, gt)
            e2_rerun_count += 1
        else:
            error_type = E2_UNSPECIFIED

        rows.append({
            "query_item_key": qik,
            "query_text": qtext,
            "gold_parent_key": gold_pk,
            "error_type": error_type,
            "rank1_parent_key": rank1_pk,
            "rank1_item_key": rank1_ik,
            "extracted_params": json.dumps(extracted, ensure_ascii=False) if extracted else None,
            "gt_params": json.dumps(gt, ensure_ascii=False),
            "mismatched_axes": json.dumps(mismatched_axes, ensure_ascii=False),
        })

    if e2_rerun_count > 0:
        print(f"  Re-ran extraction for {e2_rerun_count} queries")

    result = pd.DataFrame(rows)
    print(f"  Error distribution:")
    for et in ALL_ERROR_TYPES:
        count = (result["error_type"] == et).sum()
        if count > 0:
            print(f"    {et}: {count}")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: Cross-Condition Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def build_table_a(all_errors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Table A: Error category breakdown by condition."""
    rows = []
    for et in ALL_ERROR_TYPES:
        row = {"error_type": et}
        for cond in TIER1_CONDITIONS:
            if cond in all_errors and len(all_errors[cond]) > 0:
                count = (all_errors[cond]["error_type"] == et).sum()
                row[cond] = int(count)
            else:
                row[cond] = 0
        rows.append(row)

    # Total row
    total_row = {"error_type": "TOTAL"}
    for cond in TIER1_CONDITIONS:
        if cond in all_errors:
            total_row[cond] = len(all_errors[cond])
        else:
            total_row[cond] = 0
    rows.append(total_row)

    return pd.DataFrame(rows)


def build_table_b(all_errors: dict[str, pd.DataFrame],
                  shared: dict) -> pd.DataFrame:
    """Table B: Errors by concept group for rules pipeline."""
    cond = "structured_pipeline_rules"
    if cond not in all_errors or len(all_errors[cond]) == 0:
        return pd.DataFrame()

    errors = all_errors[cond]
    schema = shared["schema"]
    qcounts = shared["query_counts_by_parent"]

    group_errors = errors.groupby("gold_parent_key").agg(
        errors=("error_type", "count"),
    ).reset_index()

    rows = []
    for _, grow in group_errors.iterrows():
        pk = grow["gold_parent_key"]
        if pk not in schema:
            continue
        group = schema[pk]
        rows.append({
            "parent_key": pk,
            "concept": group["concept"][:60],
            "num_items": group["num_items"],
            "num_axes": len(group["axes"]),
            "total_queries": qcounts.get(pk, 0),
            "errors": int(grow["errors"]),
            "error_rate": grow["errors"] / max(qcounts.get(pk, 1), 1),
        })

    df = pd.DataFrame(rows).sort_values("errors", ascending=False)
    return df


def build_table_c(all_errors: dict[str, pd.DataFrame],
                  shared: dict) -> pd.DataFrame:
    """Table C: Per-axis accuracy for rules oracle condition."""
    cond = "structured_pipeline_oracle_rules"
    if cond not in all_errors or len(all_errors[cond]) == 0:
        return pd.DataFrame()

    errors_df = all_errors[cond]
    gt_params = shared["gt_params"]
    short_df = shared["short_df"]
    text_lookup = short_df.set_index("item_key")["text_norm"].astype(str).to_dict()

    # We need per-axis stats across ALL queries, not just failed ones
    # Load the full query set
    summary_path = RUNS_DIR / cond / "results_perquery_summary.csv"
    summary = pd.read_csv(summary_path)
    summary["query_item_key"] = summary["query_item_key"].astype(str)

    # Re-run extraction on ALL queries to get per-axis accuracy
    from src.pipeline.param_extractor_rules import RuleBasedParamExtractor
    extractor = RuleBasedParamExtractor(SCHEMA_PATH)

    # Build query text lookup (use raw text for rules)
    if "text" in short_df.columns:
        text_raw_lookup = short_df.set_index("item_key")["text"].astype(str).to_dict()
    else:
        text_raw_lookup = text_lookup

    axis_stats = defaultdict(lambda: {
        "total": 0, "correct": 0, "wrong_value": 0, "null": 0,
        "total_has_num": 0, "correct_has_num": 0,
        "total_no_num": 0, "correct_no_num": 0,
    })

    doc2parent = shared["doc2parent"]
    n_total = len(summary)
    print(f"\n[table_c] Computing per-axis stats on {n_total} queries...")

    for i, (_, srow) in enumerate(summary.iterrows()):
        qik = str(srow["query_item_key"])
        pk = doc2parent.get(qik)
        if pk is None:
            continue

        gt = gt_params.get(qik, {})
        if not gt:
            continue

        qtext_raw = text_raw_lookup.get(qik, "")
        qtext_norm = text_lookup.get(qik, "")
        has_num = any(ch.isdigit() for ch in str(qtext_norm))

        extracted = extractor.extract(pk, qtext_raw)

        for axis_label, gt_val in gt.items():
            ext_val = extracted.get(axis_label)
            stats = axis_stats[axis_label]
            stats["total"] += 1

            if has_num:
                stats["total_has_num"] += 1
            else:
                stats["total_no_num"] += 1

            if ext_val is None:
                stats["null"] += 1
            elif ext_val.strip().lower() == gt_val.strip().lower():
                stats["correct"] += 1
                if has_num:
                    stats["correct_has_num"] += 1
                else:
                    stats["correct_no_num"] += 1
            else:
                stats["wrong_value"] += 1

        if (i + 1) % 5000 == 0:
            print(f"  [{i+1}/{n_total}]")

    rows = []
    for axis_label, stats in sorted(axis_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        acc = stats["correct"] / max(stats["total"], 1)
        acc_hn = stats["correct_has_num"] / max(stats["total_has_num"], 1)
        acc_nn = stats["correct_no_num"] / max(stats["total_no_num"], 1)
        rows.append({
            "axis_label": axis_label,
            "total_occurrences": stats["total"],
            "correct": stats["correct"],
            "wrong_value": stats["wrong_value"],
            "null_when_present": stats["null"],
            "accuracy": round(acc, 4),
            "accuracy_has_numbers": round(acc_hn, 4),
            "accuracy_no_numbers": round(acc_nn, 4),
        })

    return pd.DataFrame(rows)


def build_has_numbers_analysis(all_errors: dict[str, pd.DataFrame],
                               shared: dict) -> dict:
    """Deep has_numbers vs no_numbers analysis."""
    short_df = shared["short_df"]
    text_lookup = short_df.set_index("item_key")["text_norm"].astype(str).to_dict()

    analysis = {}
    for cond_name, errors_df in all_errors.items():
        if len(errors_df) == 0:
            continue

        # Load total query count from summary
        summary_path = RUNS_DIR / cond_name / "results_perquery_summary.csv"
        summary = pd.read_csv(summary_path)
        summary["query_item_key"] = summary["query_item_key"].astype(str)

        # Add has_numbers flag to all queries
        summary["has_numbers"] = summary["query_item_key"].map(
            lambda ik: any(ch.isdigit() for ch in str(text_lookup.get(str(ik), "")))
        )

        total_hn = summary["has_numbers"].sum()
        total_nn = (~summary["has_numbers"]).sum()
        failed_hn = sum(
            1 for _, r in errors_df.iterrows()
            if any(ch.isdigit() for ch in str(text_lookup.get(str(r["query_item_key"]), "")))
        )
        failed_nn = len(errors_df) - failed_hn

        analysis[cond_name] = {
            "total_has_numbers": int(total_hn),
            "total_no_numbers": int(total_nn),
            "errors_has_numbers": int(failed_hn),
            "errors_no_numbers": int(failed_nn),
            "error_rate_has_numbers": round(failed_hn / max(total_hn, 1), 4),
            "error_rate_no_numbers": round(failed_nn / max(total_nn, 1), 4),
        }

    return analysis


def build_rules_vs_llm(all_errors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compare rules oracle vs LLM oracle conditions."""
    rules_cond = "structured_pipeline_oracle_rules"
    llm_pairs = [
        ("structured_pipeline_oracle", "Llama extract"),
        ("structured_pipeline_oracle_phi4_classify", "Phi-4 classify"),
    ]

    if rules_cond not in all_errors or len(all_errors[rules_cond]) == 0:
        return pd.DataFrame()

    rules_errors = all_errors[rules_cond]
    rules_failed = set(rules_errors["query_item_key"])

    # Load rules oracle summary for the full query set
    summary_path = RUNS_DIR / rules_cond / "results_perquery_summary.csv"
    rules_summary = pd.read_csv(summary_path)
    rules_summary["query_item_key"] = rules_summary["query_item_key"].astype(str)
    all_qkeys = set(rules_summary["query_item_key"])

    rows = []
    for llm_cond, llm_label in llm_pairs:
        if llm_cond not in all_errors:
            continue

        llm_errors = all_errors[llm_cond]
        llm_failed = set(llm_errors["query_item_key"])

        # Categories
        both_fail = rules_failed & llm_failed
        rules_only = rules_failed - llm_failed  # rules wrong, LLM right
        llm_only = llm_failed - rules_failed    # LLM wrong, rules right
        both_ok = all_qkeys - rules_failed - llm_failed

        rows.append({
            "comparison": f"Rules vs {llm_label}",
            "both_correct": len(both_ok),
            "both_fail": len(both_fail),
            "rules_wrong_llm_right": len(rules_only),
            "rules_right_llm_wrong": len(llm_only),
            "total_queries": len(all_qkeys),
        })

        # Build detailed disagreement list
        for qik in sorted(rules_only | llm_only):
            rules_et = ""
            llm_et = ""
            if qik in rules_failed:
                r = rules_errors[rules_errors["query_item_key"] == qik]
                if len(r) > 0:
                    rules_et = r.iloc[0]["error_type"]
            if qik in llm_failed:
                r = llm_errors[llm_errors["query_item_key"] == qik]
                if len(r) > 0:
                    llm_et = r.iloc[0]["error_type"]

    return pd.DataFrame(rows)


def build_rules_vs_llm_detailed(all_errors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Detailed per-query rules vs LLM comparison for disagreements."""
    rules_cond = "structured_pipeline_oracle_rules"
    llm_pairs = [
        ("structured_pipeline_oracle", "llama_extract"),
        ("structured_pipeline_oracle_phi4_classify", "phi4_classify"),
    ]

    if rules_cond not in all_errors or len(all_errors[rules_cond]) == 0:
        return pd.DataFrame()

    rules_errors = all_errors[rules_cond]
    rules_failed = set(rules_errors["query_item_key"])
    rules_error_map = {r["query_item_key"]: r["error_type"]
                       for _, r in rules_errors.iterrows()}

    rows = []
    for llm_cond, llm_label in llm_pairs:
        if llm_cond not in all_errors:
            continue

        llm_errors = all_errors[llm_cond]
        llm_failed = set(llm_errors["query_item_key"])
        llm_error_map = {r["query_item_key"]: r["error_type"]
                         for _, r in llm_errors.iterrows()}

        # Only disagreement queries
        disagree = (rules_failed - llm_failed) | (llm_failed - rules_failed)
        for qik in sorted(disagree):
            rows.append({
                "query_item_key": qik,
                "llm_condition": llm_label,
                "rules_hit": int(qik not in rules_failed),
                "llm_hit": int(qik not in llm_failed),
                "rules_error_type": rules_error_map.get(qik, ""),
                "llm_error_type": llm_error_map.get(qik, ""),
            })

    return pd.DataFrame(rows)


def build_qualitative_examples(all_errors: dict[str, pd.DataFrame],
                                shared: dict) -> dict:
    """Select 3-5 qualitative examples per error type."""
    gt_params = shared["gt_params"]
    schema = shared["schema"]
    examples = {}

    # Prefer oracle_rules for E2/E3 (cleanest signal), pipeline_rules for E1
    e1_cond = "structured_pipeline_rules"
    e2_cond = "structured_pipeline_oracle_rules"

    for error_type in ALL_ERROR_TYPES:
        cond = e1_cond if error_type == E1_WRONG_CONCEPT else e2_cond
        if cond not in all_errors or len(all_errors[cond]) == 0:
            continue

        err_df = all_errors[cond]
        subset = err_df[err_df["error_type"] == error_type]

        if len(subset) == 0:
            continue

        # Select diverse examples (different concept groups)
        # Skip examples where extraction matches GT perfectly (Stage 3 normalization edge cases)
        selected = []
        seen_parents = set()
        for _, row in subset.iterrows():
            pk = row["gold_parent_key"]
            if pk in seen_parents and len(selected) < 5:
                continue

            # For E2 types, skip if extracted params match GT perfectly
            if error_type.startswith("E2") and row.get("extracted_params"):
                try:
                    ext = json.loads(row["extracted_params"])
                    gt = gt_params.get(row["query_item_key"], {})
                    if ext == gt:
                        continue  # Stage 3 edge case, not a real extraction error
                except (json.JSONDecodeError, TypeError):
                    pass

            seen_parents.add(pk)

            gt = gt_params.get(row["query_item_key"], {})
            extracted = None
            if row["extracted_params"]:
                try:
                    extracted = json.loads(row["extracted_params"])
                except (json.JSONDecodeError, TypeError):
                    pass

            mismatched = []
            if row["mismatched_axes"]:
                try:
                    mismatched = json.loads(row["mismatched_axes"])
                except (json.JSONDecodeError, TypeError):
                    pass

            concept_name = schema.get(pk, {}).get("concept", "")

            example = {
                "query_item_key": row["query_item_key"],
                "query_text": row["query_text"],
                "gold_parent_key": pk,
                "concept_name": concept_name[:80],
                "ground_truth_params": gt,
                "condition": cond,
            }

            if error_type == E1_WRONG_CONCEPT:
                example["predicted_parent_key"] = row["rank1_parent_key"]
                pred_concept = schema.get(row["rank1_parent_key"], {}).get("concept", "")
                example["predicted_concept_name"] = pred_concept[:80]
            elif extracted is not None:
                example["extracted_params"] = extracted
                example["mismatched_axes"] = mismatched

            selected.append(example)
            if len(selected) >= 5:
                break

        if selected:
            examples[error_type] = selected

    return examples


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4: Output Generation
# ═══════════════════════════════════════════════════════════════════════════════

def generate_outputs(all_errors: dict[str, pd.DataFrame],
                     shared: dict,
                     output_dir: Path):
    """Generate all output files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[output] Writing to {output_dir}/")

    # Table A
    table_a = build_table_a(all_errors)
    table_a.to_csv(output_dir / "error_distribution.csv", index=False)
    print(f"  error_distribution.csv ({len(table_a)} rows)")

    # Table B
    table_b = build_table_b(all_errors, shared)
    table_b.to_csv(output_dir / "errors_by_concept_group.csv", index=False)
    print(f"  errors_by_concept_group.csv ({len(table_b)} rows)")

    # Table C
    table_c = build_table_c(all_errors, shared)
    table_c.to_csv(output_dir / "errors_by_axis.csv", index=False)
    print(f"  errors_by_axis.csv ({len(table_c)} rows)")

    # has_numbers analysis
    hn_analysis = build_has_numbers_analysis(all_errors, shared)

    # Rules vs LLM
    rvl_summary = build_rules_vs_llm(all_errors)
    rvl_detailed = build_rules_vs_llm_detailed(all_errors)
    if len(rvl_detailed) > 0:
        rvl_detailed.to_csv(output_dir / "rules_vs_llm_comparison.csv", index=False)
        print(f"  rules_vs_llm_comparison.csv ({len(rvl_detailed)} rows)")
    elif len(rvl_summary) > 0:
        rvl_summary.to_csv(output_dir / "rules_vs_llm_comparison.csv", index=False)
        print(f"  rules_vs_llm_comparison.csv ({len(rvl_summary)} rows)")

    # Qualitative examples
    examples = build_qualitative_examples(all_errors, shared)
    with open(output_dir / "error_examples.json", "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)
    total_examples = sum(len(v) for v in examples.values())
    print(f"  error_examples.json ({total_examples} examples across {len(examples)} types)")

    # Summary markdown
    summary_md = _build_summary_md(table_a, table_b, table_c, hn_analysis,
                                    rvl_summary, examples, all_errors, shared)
    with open(output_dir / "error_analysis_summary.md", "w", encoding="utf-8") as f:
        f.write(summary_md)
    print(f"  error_analysis_summary.md")


def _build_summary_md(table_a, table_b, table_c, hn_analysis,
                      rvl_summary, examples, all_errors, shared) -> str:
    """Build the narrative markdown summary."""
    lines = ["# Error Analysis — Structured Pipeline (Sprint D1)\n"]
    lines.append(f"Analysis of {sum(len(e) for e in all_errors.values())} failed queries "
                 f"across {len(all_errors)} Tier 1 conditions.\n")

    # Table A
    lines.append("## Table A — Error Category Breakdown\n")
    if len(table_a) > 0:
        lines.append(table_a.to_markdown(index=False))
        lines.append("")

    # Table B
    lines.append("\n## Table B — Errors by Concept Group (Rules Pipeline, Top 10)\n")
    if len(table_b) > 0:
        top10 = table_b.head(10)
        lines.append(top10.to_markdown(index=False))
        lines.append("")

    # Table C
    lines.append("\n## Table C — Per-Axis Accuracy (Rules Oracle)\n")
    if len(table_c) > 0:
        lines.append(table_c.to_markdown(index=False))
        lines.append("")

    # has_numbers
    lines.append("\n## has_numbers vs no_numbers Breakdown\n")
    if hn_analysis:
        lines.append("| Condition | has_num errors | has_num rate | no_num errors | no_num rate |")
        lines.append("|---|---|---|---|---|")
        for cond, stats in sorted(hn_analysis.items()):
            lines.append(
                f"| {cond} | "
                f"{stats['errors_has_numbers']}/{stats['total_has_numbers']} | "
                f"{stats['error_rate_has_numbers']:.1%} | "
                f"{stats['errors_no_numbers']}/{stats['total_no_numbers']} | "
                f"{stats['error_rate_no_numbers']:.1%} |"
            )
        lines.append("")

    # Rules vs LLM
    lines.append("\n## Rules vs LLM Comparison (Oracle Conditions)\n")
    if len(rvl_summary) > 0:
        lines.append(rvl_summary.to_markdown(index=False))
        lines.append("")

    # Qualitative examples
    lines.append("\n## Qualitative Error Examples\n")
    for error_type, exs in examples.items():
        lines.append(f"\n### {error_type}\n")
        for i, ex in enumerate(exs[:3], 1):
            lines.append(f"**Example {i}:** `{ex['query_item_key']}`")
            lines.append(f"- Query: *{ex['query_text'][:120]}*")
            lines.append(f"- Concept: {ex.get('concept_name', '')}")
            lines.append(f"- GT params: `{json.dumps(ex.get('ground_truth_params', {}), ensure_ascii=False)}`")
            if "extracted_params" in ex:
                lines.append(f"- Extracted: `{json.dumps(ex['extracted_params'], ensure_ascii=False)}`")
                lines.append(f"- Mismatched axes: {ex.get('mismatched_axes', [])}")
            if "predicted_parent_key" in ex:
                lines.append(f"- Predicted parent: {ex['predicted_parent_key']} ({ex.get('predicted_concept_name', '')})")
            lines.append("")

    # Key findings
    lines.append("\n## Key Findings\n")

    # Compute some summary stats
    rules_pipeline = all_errors.get("structured_pipeline_rules", pd.DataFrame())
    rules_oracle = all_errors.get("structured_pipeline_oracle_rules", pd.DataFrame())
    if len(rules_pipeline) > 0:
        e1_count = (rules_pipeline["error_type"] == E1_WRONG_CONCEPT).sum()
        e1_pct = e1_count / len(rules_pipeline) * 100
        lines.append(f"1. **Stage 1 errors (E1) account for {e1_count} ({e1_pct:.1f}%) of rules pipeline errors** — "
                     f"the pipeline→oracle gap.")
    if len(rules_oracle) > 0:
        for et in [E2_PARTIAL_EXTRACT, E2_WRONG_VALUE, E2_ALL_NULL]:
            count = (rules_oracle["error_type"] == et).sum()
            if count > 0:
                pct = count / len(rules_oracle) * 100
                lines.append(f"2. **{et}**: {count} ({pct:.1f}%) of rules oracle errors")

    lines.append("\n---\n*Generated by `scripts/error_analysis.py`*\n")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Sprint D1: Error Analysis")
    parser.add_argument("--rerun-llm", action="store_true",
                        help="Re-run LLM extraction on failed queries (requires Ollama)")
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                        help="Ollama base URL (default: http://localhost:11434)")
    parser.add_argument("--output-dir", default="analysis",
                        help="Output directory (default: analysis/)")
    parser.add_argument("--conditions", nargs="*", default=None,
                        help="Subset of conditions to analyze (default: all Tier 1)")
    args = parser.parse_args()

    output_dir = ROOT / args.output_dir

    # Determine conditions to analyze
    conditions = args.conditions or TIER1_CONDITIONS
    conditions = [c for c in conditions if c in CONDITION_CONFIGS]
    print(f"Analyzing {len(conditions)} conditions: {conditions}")

    # Phase 1: Load shared data
    shared = load_shared_data()

    # Phase 2: Classify errors per condition
    all_errors = {}
    for cond_name in conditions:
        config = CONDITION_CONFIGS[cond_name]
        run_dir = RUNS_DIR / cond_name
        if not run_dir.exists():
            print(f"\n[skip] {cond_name}: run directory not found")
            continue
        errors_df = classify_errors_for_condition(
            config, shared,
            rerun_llm=args.rerun_llm,
            ollama_url=args.ollama_url,
        )
        all_errors[cond_name] = errors_df

    # Phase 3 + 4: Analysis and output
    generate_outputs(all_errors, shared, output_dir)
    print("\n[done] Error analysis complete.")


if __name__ == "__main__":
    main()
