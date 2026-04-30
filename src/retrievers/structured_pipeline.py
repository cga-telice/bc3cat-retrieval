# /src/retrievers/structured_pipeline.py
"""
Three-stage structured retriever: dense retrieval → parameter extraction → catalog lookup.

Wires together:
  - Stage 1: DenseE5Searcher (item-level index) → parent_key
  - Stage 2: LLMParamExtractor or RuleBasedParamExtractor → {axis: value|None}
  - Stage 3: CatalogLookup → [item_key, ...]

Follows the standard Searcher contract (search, search_batch, external_ids)
so it integrates with retrieve.ipynb / eval.ipynb unchanged.

Pipeline config is read from meta.json in the pseudo-index directory.
"""

from __future__ import annotations
from pathlib import Path
import json
import time
import logging

import numpy as np
import pandas as pd

from .dense_e5 import DenseE5Searcher
from src.pipeline.catalog_lookup import CatalogLookup

logger = logging.getLogger(__name__)

# ── Project paths (resolved from this file's location) ──────────────────────
ROOT = Path(__file__).resolve().parents[2]
E5_INDEX = ROOT / "index" / "dense_e5"
DATA_DIR = ROOT / "data" / "processed"
SCHEMA_PATH = DATA_DIR / "OEB_concept_schema.json"
PARQUET_PATH = DATA_DIR / "OEB_long_norm.parquet"
SHORT_PARQUET_PATH = DATA_DIR / "OEB_short_norm.parquet"


class StructuredPipelineSearcher:
    """Three-stage retriever: dense retrieval → parameter extraction → catalog lookup.

    Ranking tiers:
      - Tier 1: Matched items from Stage 3 (score ~1.0)
      - Tier 2: Remaining concept-group items (score ~0.5)
      - Tier 3: E5 fallback fill (score <0.5)
    """

    def __init__(
        self,
        e5_searcher: DenseE5Searcher,
        param_extractor,
        catalog_lookup: CatalogLookup,
        item_to_parent: dict[str, str],
        schema: dict,
        oracle_parents: dict[str, str] | None = None,
    ):
        """
        Args:
            e5_searcher: Loaded DenseE5Searcher (item-level index).
            param_extractor: LLMParamExtractor or RuleBasedParamExtractor.
            catalog_lookup: CatalogLookup instance.
            item_to_parent: {item_key → parent_key} mapping.
            schema: Concept schema dict (from OEB_concept_schema.json).
            oracle_parents: Optional {query_text → parent_key} for oracle mode.
        """
        self._e5 = e5_searcher
        self._extractor = param_extractor
        self._catalog = catalog_lookup
        self._item_to_parent = item_to_parent
        self._schema = schema
        self._oracle_parents = oracle_parents

        # Inherit external_ids from E5 (same document space)
        self.external_ids = self._e5.external_ids

        # Reverse mapping: item_key → doc_id (for Stage 3 → doc_id conversion)
        self._key_to_docid = {
            str(self.external_ids[i]): i
            for i in range(len(self.external_ids))
        }

    # ── Search API ───────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 100):
        """Three-stage search.

        1. E5 retrieval → parent_key (or oracle bypass)
        2. Parameter extraction for that concept group
        3. Catalog lookup for matching item(s)

        Returns:
            (top_indices, scores) — np arrays, shape (K,), matching Searcher contract.
        """
        # Always do E5 search — needed for Stage 1 parent_key + Tier 3 fill
        e5_idx, e5_scores = self._e5.search(query, k=k)

        # --- Stage 1: Derive parent_key ---
        if self._oracle_parents is not None and query in self._oracle_parents:
            parent_key = self._oracle_parents[query]
        else:
            top1_key = str(self._e5.external_ids[e5_idx[0]])
            parent_key = self._item_to_parent.get(top1_key)

        # Fallback: unknown parent → raw E5 ranking
        if parent_key is None or parent_key not in self._schema:
            return e5_idx[:k], e5_scores[:k]

        # --- Stage 2: Extract parameters ---
        params = self._extractor.extract(parent_key, query)

        # --- Stage 3: Catalog lookup ---
        matched_keys = self._catalog.lookup(parent_key, params)

        # --- Build three-tier ranking ---
        return self._build_ranking(matched_keys, parent_key, e5_idx, e5_scores, k)

    def search_batch(self, queries: list[str], k: int = 100):
        """Batch search. Calls search() per query.

        Returns:
            (indices[B,K], scores[B,K]) — np arrays.
        """
        B = len(queries)
        all_idx = np.zeros((B, k), dtype=np.int64)
        all_scores = np.zeros((B, k), dtype=np.float32)

        t0 = time.time()
        for i, q in enumerate(queries):
            if i > 0 and i % 100 == 0:
                elapsed = time.time() - t0
                print(f"  [{i}/{B}] {elapsed:.1f}s elapsed")
            idx, scores = self.search(q, k=k)
            all_idx[i] = idx
            all_scores[i] = scores

        return all_idx, all_scores

    # ── Ranking builder ──────────────────────────────────────────────────────

    def _build_ranking(self, matched_keys, parent_key, e5_idx, e5_scores, k):
        """Assemble three-tier ranking from pipeline results.

        Tier 1: Matched items from Stage 3 (score ~1.0, descending by 0.0001)
        Tier 2: Remaining concept-group items (score ~0.5, descending by 0.0001)
        Tier 3: E5 fallback fill (scores scaled to < 0.5)
        """
        # Tier 1: Matched items
        matched_docids = [
            self._key_to_docid[k] for k in matched_keys
            if k in self._key_to_docid
        ]

        # Tier 2: Remaining concept group items
        matched_set = set(matched_keys)
        group_keys = self._schema[parent_key].get("item_keys", [])
        remaining_docids = [
            self._key_to_docid[k] for k in group_keys
            if k in self._key_to_docid and k not in matched_set
        ]

        # Tier 3: E5 fill (excluding already-placed items)
        placed = set(matched_docids + remaining_docids)
        e5_fill = [
            (int(idx), float(sc))
            for idx, sc in zip(e5_idx, e5_scores)
            if int(idx) not in placed
        ]

        # Assemble result arrays
        result_ids = []
        result_scores = []

        for i, did in enumerate(matched_docids):
            result_ids.append(did)
            result_scores.append(1.0 - i * 0.0001)

        for i, did in enumerate(remaining_docids):
            result_ids.append(did)
            result_scores.append(0.5 - i * 0.0001)

        max_e5 = max((sc for _, sc in e5_fill), default=1.0)
        for did, sc in e5_fill:
            if len(result_ids) >= k:
                break
            result_ids.append(did)
            result_scores.append(sc * 0.49 / max_e5 if max_e5 > 0 else 0.0)

        # Truncate to k, pad if needed
        result_ids = result_ids[:k]
        result_scores = result_scores[:k]
        while len(result_ids) < k:
            result_ids.append(0)
            result_scores.append(0.0)

        return (
            np.array(result_ids, dtype=np.int64),
            np.array(result_scores, dtype=np.float32),
        )


# ── Factory ──────────────────────────────────────────────────────────────────

def load(index_dir: str | Path, device_override: str | None = None) -> StructuredPipelineSearcher:
    """Factory following the retriever contract. Reads pipeline config from meta.json.

    The meta.json params section controls:
      - stage2_method: "llm", "rules", "classifier", or "bio_tagger"
      - stage2_prompt_mode: "extract" or "classify" (default: "extract" for backward compat)
      - oracle: true/false (bypass Stage 1 with ground-truth parent_key)
      - stage2_ollama_url, stage2_model (for LLM variant)
      - stage2_model_dir (for "classifier" and "bio_tagger" variants)

    Args:
        device_override: If set, overrides the E5 searcher's device (e.g. "cpu").
    """
    index_dir = Path(index_dir)

    with open(index_dir / "meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    params = meta.get("params", {})
    variant = meta.get("variant", "structured_pipeline")

    print(f"Loading structured pipeline: {variant}")

    # Stage 1: E5 searcher (always loaded -- needed for search + fill)
    print(f"  Loading E5 index from {E5_INDEX}")
    e5 = DenseE5Searcher(E5_INDEX)
    if device_override:
        e5.device = device_override

    # Schema
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)

    # Item-to-parent mapping from parquet
    long_df = pd.read_parquet(PARQUET_PATH, columns=["item_key", "parent_key"])
    item_to_parent = dict(zip(long_df["item_key"], long_df["parent_key"]))
    print(f"  item_to_parent: {len(item_to_parent)} entries")

    # Stage 2: Param extractor (lazy import to avoid unnecessary deps)
    stage2 = params.get("stage2_method", "llm")
    if stage2 == "rules":
        from src.pipeline.param_extractor_rules import RuleBasedParamExtractor
        extractor = RuleBasedParamExtractor(SCHEMA_PATH)
        print("  Stage 2: rule-based extractor")
    elif stage2 == "classifier":
        from src.pipeline.param_extractor_classifier import ClassifierParamExtractor
        model_dir = params.get("stage2_model_dir", str(ROOT / "models" / "e5_classifier"))
        # Resolve Docker path (/work/...) to local path if not running in Docker
        if model_dir.startswith("/work/") and not Path(model_dir).exists():
            model_dir = str(ROOT / model_dir.removeprefix("/work/"))
        classifier_device = device_override or "cpu"
        extractor = ClassifierParamExtractor(model_dir, device=classifier_device)
        print(f"  Stage 2: E5 classifier ({model_dir})")
    elif stage2 == "bio_tagger":
        from src.pipeline.param_extractor_bio import BIOParamExtractor
        model_dir = params.get("stage2_model_dir", str(ROOT / "models" / "e5_bio_tagger"))
        if model_dir.startswith("/work/") and not Path(model_dir).exists():
            model_dir = str(ROOT / model_dir.removeprefix("/work/"))
        bio_device = device_override or "cpu"
        extractor = BIOParamExtractor(
            model_dir, schema_path=SCHEMA_PATH, device=bio_device
        )
        print(f"  Stage 2: BIO tagger ({model_dir})")
    else:
        from src.pipeline.param_extractor import LLMParamExtractor
        prompt_mode = params.get("stage2_prompt_mode", "extract")
        extractor = LLMParamExtractor(
            SCHEMA_PATH,
            ollama_base_url=params.get("stage2_ollama_url", "http://ollama:11434"),
            model=params.get("stage2_model", "llama3.1:8b"),
            prompt_mode=prompt_mode,
        )
        print(f"  Stage 2: LLM extractor ({params.get('stage2_model', 'llama3.1:8b')}, mode={prompt_mode})")

    # Stage 3: Catalog lookup
    catalog = CatalogLookup(SCHEMA_PATH, PARQUET_PATH)
    print("  Stage 3: catalog lookup ready")

    # Oracle mode: bypass Stage 1 with ground-truth parent_key
    oracle_parents = None
    if params.get("oracle"):
        text_field = meta.get("text_field", "text_norm")
        short_df = pd.read_parquet(
            SHORT_PARQUET_PATH, columns=[text_field, "parent_key"]
        )
        oracle_parents = dict(zip(short_df[text_field], short_df["parent_key"]))
        print(f"  Oracle mode: {len(oracle_parents)} query->parent mappings loaded")

    searcher = StructuredPipelineSearcher(
        e5_searcher=e5,
        param_extractor=extractor,
        catalog_lookup=catalog,
        item_to_parent=item_to_parent,
        schema=schema,
        oracle_parents=oracle_parents,
    )
    print(f"  Ready. {len(searcher.external_ids)} documents in index space.")
    return searcher


# ── Sanity test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Structured pipeline sanity test")
    parser.add_argument("--n-queries", type=int, default=50,
                        help="Number of queries to test (default: 50)")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Skip LLM variants (requires Ollama)")
    parser.add_argument("--base-url", default="http://localhost:11434",
                        help="Ollama base URL (default: http://localhost:11434)")
    parser.add_argument("--k", type=int, default=100,
                        help="Top-K results per query (default: 100)")
    parser.add_argument("--device", default=None,
                        help="Override E5 model device (e.g. 'cpu' for non-CUDA hosts)")
    args = parser.parse_args()

    # ── Sample queries ───────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"Structured Pipeline Sanity Test -- {args.n_queries} queries")
    print(f"{'='*70}\n")

    short_df = pd.read_parquet(SHORT_PARQUET_PATH)
    # Filter to concept groups (parent_key ending with $)
    concept_df = short_df[short_df["parent_key"].str.endswith("$")].copy()

    # Stratified sample: 2 per concept group, then trim to n_queries
    if args.n_queries < len(concept_df):
        per_group = max(1, args.n_queries // concept_df["parent_key"].nunique())
        parts = []
        for pk, grp in concept_df.groupby("parent_key"):
            parts.append(grp.sample(n=min(len(grp), per_group), random_state=42))
        sample_df = pd.concat(parts, ignore_index=True)
        if len(sample_df) > args.n_queries:
            sample_df = sample_df.head(args.n_queries)
        elif len(sample_df) < args.n_queries:
            # Fill remaining from unsampled rows
            used_idx = set(sample_df.index)
            remaining = concept_df[~concept_df.index.isin(used_idx)]
            extra = remaining.sample(
                n=min(len(remaining), args.n_queries - len(sample_df)),
                random_state=42,
            )
            sample_df = pd.concat([sample_df, extra], ignore_index=True)
    else:
        sample_df = concept_df.head(args.n_queries)

    print(f"Sampled {len(sample_df)} queries from {sample_df['parent_key'].nunique()} concept groups\n")

    # Use text_norm as query text (matches meta.json text_field)
    texts = sample_df["text_norm"].astype(str).tolist()
    gt_item_keys = sample_df["item_key"].astype(str).tolist()
    gt_parent_keys = sample_df["parent_key"].astype(str).tolist()

    # ── Define conditions ────────────────────────────────────────────────
    INDEX_ROOT = ROOT / "index"

    conditions = []
    # Rules variants (no Ollama needed)
    conditions.append(("structured_pipeline_rules", INDEX_ROOT / "structured_pipeline_rules"))
    conditions.append(("structured_pipeline_oracle_rules", INDEX_ROOT / "structured_pipeline_oracle_rules"))

    if not args.skip_llm:
        conditions.append(("structured_pipeline", INDEX_ROOT / "structured_pipeline"))
        conditions.append(("structured_pipeline_oracle", INDEX_ROOT / "structured_pipeline_oracle"))
        conditions.append(("structured_pipeline_classify", INDEX_ROOT / "structured_pipeline_classify"))
        conditions.append(("structured_pipeline_oracle_classify", INDEX_ROOT / "structured_pipeline_oracle_classify"))
        conditions.append(("structured_pipeline_twostep", INDEX_ROOT / "structured_pipeline_twostep"))
        conditions.append(("structured_pipeline_oracle_twostep", INDEX_ROOT / "structured_pipeline_oracle_twostep"))
        conditions.append(("structured_pipeline_paraaware", INDEX_ROOT / "structured_pipeline_paraaware"))
        conditions.append(("structured_pipeline_oracle_paraaware", INDEX_ROOT / "structured_pipeline_oracle_paraaware"))
        # Phi-4 14B variants (Sprint 10)
        conditions.append(("structured_pipeline_phi4_extract", INDEX_ROOT / "structured_pipeline_phi4_extract"))
        conditions.append(("structured_pipeline_oracle_phi4_extract", INDEX_ROOT / "structured_pipeline_oracle_phi4_extract"))
        conditions.append(("structured_pipeline_phi4_classify", INDEX_ROOT / "structured_pipeline_phi4_classify"))
        conditions.append(("structured_pipeline_oracle_phi4_classify", INDEX_ROOT / "structured_pipeline_oracle_phi4_classify"))
        # Phi-4 14B twostep + paraaware variants (Sprint 11)
        conditions.append(("structured_pipeline_phi4_twostep", INDEX_ROOT / "structured_pipeline_phi4_twostep"))
        conditions.append(("structured_pipeline_oracle_phi4_twostep", INDEX_ROOT / "structured_pipeline_oracle_phi4_twostep"))
        conditions.append(("structured_pipeline_phi4_paraaware", INDEX_ROOT / "structured_pipeline_phi4_paraaware"))
        conditions.append(("structured_pipeline_oracle_phi4_paraaware", INDEX_ROOT / "structured_pipeline_oracle_phi4_paraaware"))
        # Paraaware2 variants (Sprint 12)
        conditions.append(("structured_pipeline_paraaware2", INDEX_ROOT / "structured_pipeline_paraaware2"))
        conditions.append(("structured_pipeline_oracle_paraaware2", INDEX_ROOT / "structured_pipeline_oracle_paraaware2"))
        conditions.append(("structured_pipeline_phi4_paraaware2", INDEX_ROOT / "structured_pipeline_phi4_paraaware2"))
        conditions.append(("structured_pipeline_oracle_phi4_paraaware2", INDEX_ROOT / "structured_pipeline_oracle_phi4_paraaware2"))

    # ── Run conditions ───────────────────────────────────────────────────
    results = []

    for name, idx_dir in conditions:
        print(f"\n{'-'*60}")
        print(f"Condition: {name}")
        print(f"{'-'*60}")

        if not (idx_dir / "meta.json").exists():
            print(f"  SKIP -- index dir not found: {idx_dir}")
            continue

        # Patch LLM base URL if provided
        meta_path = idx_dir / "meta.json"
        with open(meta_path, encoding="utf-8") as f:
            meta_check = json.load(f)
        if meta_check.get("params", {}).get("stage2_method") == "llm":
            meta_check["params"]["stage2_ollama_url"] = args.base_url
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_check, f, indent=2, ensure_ascii=False)

        try:
            searcher = load(idx_dir, device_override=args.device)
        except Exception as e:
            print(f"  FAILED to load: {e}")
            continue

        t0 = time.time()
        top_idx, top_scores = searcher.search_batch(texts, k=args.k)
        elapsed = time.time() - t0

        # Verify output shape
        assert top_idx.shape == (len(texts), args.k), \
            f"Expected shape ({len(texts)}, {args.k}), got {top_idx.shape}"
        assert top_scores.shape == top_idx.shape
        assert top_idx.dtype == np.int64
        assert top_scores.dtype == np.float32

        # Compute accuracy
        ext_ids = np.asarray(searcher.external_ids, dtype=object)
        top_ext = ext_ids[top_idx[:, 0]]  # top-1 predicted item_key

        item_acc1 = np.mean([
            str(top_ext[i]) == gt_item_keys[i]
            for i in range(len(gt_item_keys))
        ])

        # Parent accuracy: derive parent from predicted top-1
        pred_parents = [
            searcher._item_to_parent.get(str(top_ext[i]), "")
            for i in range(len(gt_item_keys))
        ]
        parent_acc1 = np.mean([
            pred_parents[i] == gt_parent_keys[i]
            for i in range(len(gt_parent_keys))
        ])

        results.append({
            "method": name,
            "item_acc1": item_acc1,
            "parent_acc1": parent_acc1,
            "time": elapsed,
            "n_queries": len(texts),
        })

        print(f"\n  item Acc@1:   {item_acc1:.1%}")
        print(f"  parent Acc@1: {parent_acc1:.1%}")
        print(f"  time:         {elapsed:.1f}s ({elapsed/len(texts)*1000:.1f}ms/query)")

    # ── Summary table ────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"SUMMARY -- {args.n_queries} queries")
    print(f"{'='*70}")
    print(f"{'Method':<40} {'item_Acc@1':>10} {'parent_Acc@1':>12} {'time':>8}")
    print(f"{'-'*40} {'-'*10} {'-'*12} {'-'*8}")
    for r in results:
        print(f"{r['method']:<40} {r['item_acc1']:>9.1%} {r['parent_acc1']:>11.1%} {r['time']:>7.1f}s")
    print()
