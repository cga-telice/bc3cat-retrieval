# /src/retrievers/structured_pipeline.py
"""
Three-stage structured retriever: dense retrieval → parameter extraction → catalog lookup.

Wires together:
  - Stage 1: DenseE5Searcher (item-level index) → parent_key
  - Stage 2: RuleBasedParamExtractor → {axis: value|None}
  - Stage 3: CatalogLookup → [item_key, ...]

Follows the standard Searcher contract (search, search_batch, external_ids)
so it integrates with retrieve.ipynb / eval.ipynb unchanged.

Pipeline config is read from meta.json in the pseudo-index directory.

Ported from `research/structured-retrieval@85c3359` (D-026). Changes against the source:

- **Paths.** The module-level `OEB_*` constants and `index/dense_e5` are gone. The collection
  comes from the index's `meta.json`; data paths from the resolver (`utils.run_context.
  data_paths`, D-022); the Stage-1 index is the sibling named by `params.stage1_index`, under
  the same `index/{collection}/`.
- **Fail loud.** `load` refuses a Stage-1 index whose document order differs from this
  index's `mapping.jsonl`: the ranking addresses documents by E5 row, and `retrieve.ipynb`
  reads ids from `external_ids`, so a silent disagreement would score the wrong leaves.
- **Scope.** Rules, and from S9 the LLM extractor (`stage2_method: llm`, `pipeline.param_extractor`,
  `phi4` in `extract` mode, generations cached; S9 work item 4). The oracle-parent mode is not ported
  (S5); asking for it raises instead of falling back.
- **Batching.** `search_batch` sends all queries through E5's `search_batch` (which blocks
  them itself, S2), then runs Stages 2–3 per query. The source looped over `search()`, which encodes one query at a time.
  Stages 1–3 and the three-tier ranking are otherwise unchanged; `search()` and
  `search_batch()` share `_rank_from_stage1`, and a test holds them equal.
- The `__main__` sanity test, which enumerated OEB variant directories, is not ported.
- **`stage3_value_match`** (S2 amendment 2026-09-17) is passed to `CatalogLookup`; absent means
  `"literal"`, the source's behaviour. See `pipeline.catalog_lookup`.
- **`stage2_method: oracle_params`** (S5 work item 1) — the oracle-extraction bound: Stage 2 is
  the query record's own `parameters_norm`, restricted to schema values
  (`pipeline.param_extractor_oracle`). It needs the record, which the text-only Searcher
  contract does not carry, so `retrieve.ipynb` calls `bind_queries(queries_df)` on any searcher
  that has it, and `search_batch` refuses texts that are not the bound ones, in order. `search()`
  is refused in this mode: a lone text has no record. Stage 1 and Stage 3 are the rules arm's.
"""

from __future__ import annotations
from pathlib import Path
import json
import logging

import numpy as np
import pandas as pd

from .dense_e5 import DenseE5Searcher
from pipeline.catalog_lookup import CatalogLookup
from pipeline.param_extractor_oracle import OracleParamsExtractor
from pipeline.param_extractor_rules import RuleBasedParamExtractor
from pipeline.param_extractor import LLMParamExtractor
from query_rewrite.llm import Cache, OllamaClient
from utils.run_context import data_paths

logger = logging.getLogger(__name__)


class StructuredPipelineSearcher:
    """Three-stage retriever: dense retrieval → parameter extraction → catalog lookup.

    Ranking tiers:
      - Tier 1: Matched items from Stage 3 (score ~1.0)
      - Tier 2: Remaining concept-group items (score ~0.5)
      - Tier 3: E5 fallback fill (score <0.5)
    """

    def __init__(
        self,
        e5_searcher,
        param_extractor,
        catalog_lookup: CatalogLookup,
        item_to_parent: dict[str, str],
        schema: dict,
    ):
        """
        Args:
            e5_searcher: Loaded DenseE5Searcher (item-level index).
            param_extractor: RuleBasedParamExtractor.
            catalog_lookup: CatalogLookup instance.
            item_to_parent: {item_key → parent_key} mapping.
            schema: Concept schema dict (from {collection}_concept_schema.json).
        """
        self._e5 = e5_searcher
        self._extractor = param_extractor
        self._catalog = catalog_lookup
        self._item_to_parent = item_to_parent
        self._schema = schema

        # Inherit external_ids from E5 (same document space)
        self.external_ids = self._e5.external_ids

        # Reverse mapping: item_key → doc_id (for Stage 3 → doc_id conversion)
        self._key_to_docid = {
            str(self.external_ids[i]): i
            for i in range(len(self.external_ids))
        }

        # Oracle extraction reads the query record, bound before the batch (S5).
        self._needs_record = isinstance(param_extractor, OracleParamsExtractor)
        self._bound_texts: list[str] | None = None
        self._bound_records: list[dict] | None = None

    # ── Query records (oracle extraction only) ───────────────────────────────

    #: The query field the pipeline reads; `index_builders.structured_pipeline_rules.TEXT_FIELD`.
    TEXT_FIELD = "text_norm"

    def bind_queries(self, queries_df: pd.DataFrame) -> None:
        """Receive the scored query rows, in scoring order. A no-op unless Stage 2 is oracle."""
        if not self._needs_record:
            return
        for col in (self.TEXT_FIELD, "parameters_norm"):
            if col not in queries_df.columns:
                raise KeyError(f"oracle extraction needs column {col!r} in the query table")
        self._bound_texts = queries_df[self.TEXT_FIELD].astype(str).tolist()
        self._bound_records = list(queries_df["parameters_norm"])

    # ── Search API ───────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 100):
        """Three-stage search.

        1. E5 retrieval → parent_key
        2. Parameter extraction for that concept group
        3. Catalog lookup for matching item(s)

        Returns:
            (top_indices, scores) — np arrays, shape (K,), matching Searcher contract.
        """
        if self._needs_record:
            raise RuntimeError("oracle extraction needs the query record: use bind_queries + search_batch")
        # Always do E5 search — needed for Stage 1 parent_key + Tier 3 fill
        e5_idx, e5_scores = self._e5.search(query, k=k)
        return self._rank_from_stage1(query, e5_idx, e5_scores, k)

    def search_batch(self, queries: list[str], k: int = 100, **e5_kwargs):
        """Batch search: E5 over all queries (blocked by E5's own `batch_size`), then Stages
        2–3 per query. Extra keyword arguments go to the Stage-1 searcher.

        Returns:
            (indices[B,K], scores[B,K]) — np arrays.
        """
        B = len(queries)
        all_idx = np.zeros((B, k), dtype=np.int64)
        all_scores = np.zeros((B, k), dtype=np.float32)
        if B == 0:
            return all_idx, all_scores

        records = [None] * B
        if self._needs_record:
            if self._bound_texts is None:
                raise RuntimeError("oracle extraction: bind_queries was not called before search_batch")
            if list(queries) != self._bound_texts:
                raise ValueError(
                    "oracle extraction: the texts searched are not the bound query rows, in order"
                )
            records = self._bound_records

        e5_idx, e5_scores = self._e5.search_batch(list(queries), k=k, **e5_kwargs)
        for i, q in enumerate(queries):
            idx, scores = self._rank_from_stage1(q, e5_idx[i], e5_scores[i], k, record=records[i])
            all_idx[i] = idx
            all_scores[i] = scores

        return all_idx, all_scores

    def _rank_from_stage1(self, query: str, e5_idx, e5_scores, k: int, record=None):
        # --- Stage 1: Derive parent_key ---
        top1_key = str(self._e5.external_ids[e5_idx[0]])
        parent_key = self._item_to_parent.get(top1_key)

        # Fallback: unknown parent → raw E5 ranking
        if parent_key is None or parent_key not in self._schema:
            return e5_idx[:k], e5_scores[:k]

        # --- Stage 2: Extract parameters (oracle: from the record, not the text) ---
        if self._needs_record:
            params = self._extractor.extract(parent_key, record)
        else:
            params = self._extractor.extract(parent_key, query)

        # --- Stage 3: Catalog lookup ---
        matched_keys = self._catalog.lookup(parent_key, params)

        # --- Build three-tier ranking ---
        return self._build_ranking(matched_keys, parent_key, e5_idx, e5_scores, k)

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

STAGE2_METHODS = ("rules", "oracle_params", "llm")

#: S9 work item 4: the LLM extractor's model and prompt mode are fixed by the design, and its
#: generations are cached here, append-only, shared by every run of the arm (`query_rewrite.llm`).
LLM_MODEL = "phi4:latest"
LLM_PROMPT_MODE = "extract"
LLM_CACHE = "llm_cache/structured_llm_extract.jsonl"

def _read_mapping_ids(path: Path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [str(json.loads(ln)["external_id"]) for ln in f if ln.strip()]


def load(index_dir: str | Path, device_override: str | None = None) -> StructuredPipelineSearcher:
    """Factory following the retriever contract. Reads pipeline config from meta.json.

    meta.json must carry `collection` and, under `params`:
      - stage2_method: "rules", or "oracle_params" (the S5 oracle-extraction bound)
      - stage1_index:  the E5 index's directory name under index/{collection}/
      - oracle:        false, or absent
      - stage3_value_match: "literal" (default, as the source) or "normalized"

    Args:
        device_override: If set, overrides the E5 searcher's device (e.g. "cpu").
    """
    index_dir = Path(index_dir)

    with open(index_dir / "meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    params = meta.get("params", {})
    variant = meta.get("variant", "structured_pipeline")

    stage2 = params.get("stage2_method")
    if stage2 not in STAGE2_METHODS:
        raise NotImplementedError(
            f"{variant}: stage2_method={stage2!r}. Only {STAGE2_METHODS} exist on this branch "
            "(D-026, S5, S9)."
        )
    if params.get("oracle"):
        raise NotImplementedError(f"{variant}: oracle-parent mode is not ported (S5).")
    stage1 = params.get("stage1_index")
    if not stage1:
        raise KeyError(f"{variant}: meta.json params declare no stage1_index")

    collection = meta.get("collection")
    if not collection:
        raise KeyError(f"{variant}: meta.json declares no collection")
    # index/{collection}/{method} is the resolver's layout (D-008); anything else means this
    # directory was not written by it, and the work root below would be a guess.
    if index_dir.parent.name != collection:
        raise ValueError(
            f"{index_dir} is not under index/{collection}/ — not a resolver-built index"
        )
    work_root = index_dir.parents[2]
    paths = data_paths(collection, work_root=work_root)

    print(f"Loading structured pipeline: {variant}")

    # Stage 1: E5 searcher (always loaded -- needed for search + fill)
    e5_dir = index_dir.parent / stage1
    print(f"  Loading E5 index from {e5_dir}")
    e5 = DenseE5Searcher(e5_dir)
    if device_override:
        e5.device = device_override

    own_ids = _read_mapping_ids(index_dir / "mapping.jsonl")
    e5_ids = [str(x) for x in e5.external_ids]
    if own_ids != e5_ids:
        raise ValueError(
            f"{variant}: mapping.jsonl ({len(own_ids)} docs) and the Stage-1 index "
            f"{stage1} ({len(e5_ids)} docs) do not list the same documents in the same order"
        )

    # Schema
    with open(paths.concept_schema, encoding="utf-8") as f:
        schema = json.load(f)

    # Item-to-parent mapping from parquet
    long_df = pd.read_parquet(paths.long_norm, columns=["item_key", "parent_key"])
    item_to_parent = dict(zip(long_df["item_key"], long_df["parent_key"]))
    print(f"  item_to_parent: {len(item_to_parent)} entries")

    # Stage 2: rule-based extractor, or the oracle bound
    if stage2 == "rules":
        extractor = RuleBasedParamExtractor(paths.concept_schema)
    elif stage2 == "llm":
        model, mode = params.get("llm_model"), params.get("llm_prompt_mode")
        if (model, mode) != (LLM_MODEL, LLM_PROMPT_MODE):
            raise ValueError(f"{variant}: llm_model / llm_prompt_mode are ({model!r}, {mode!r}); "
                             f"the S9 design fixes ({LLM_MODEL!r}, {LLM_PROMPT_MODE!r})")
        key_match = params.get("llm_key_match", "exact")
        extractor = LLMParamExtractor(paths.concept_schema, OllamaClient(model),
                                      Cache(paths.data_dir / LLM_CACHE), prompt_mode=mode, key_match=key_match)
    else:
        extractor = OracleParamsExtractor(paths.concept_schema)
    print(f"  Stage 2: {stage2}")

    # Stage 3: Catalog lookup
    value_match = params.get("stage3_value_match", "literal")
    catalog = CatalogLookup(paths.concept_schema, paths.long_norm, value_match=value_match)
    print(f"  Stage 3: catalog lookup ready (value_match={value_match})")

    searcher = StructuredPipelineSearcher(
        e5_searcher=e5,
        param_extractor=extractor,
        catalog_lookup=catalog,
        item_to_parent=item_to_parent,
        schema=schema,
    )
    print(f"  Ready. {len(searcher.external_ids)} documents in index space.")
    return searcher
