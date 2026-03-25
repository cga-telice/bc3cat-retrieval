"""Concept-level E5 index builder (Stage 1).

Standalone script that builds a concept-level dense index with one vector
per concept group (25 vectors) using the concept field text from the schema.

Usage::

    python -m src.index_builders.concept_dense_e5
    python -m src.index_builders.concept_dense_e5 --sanity-check-only
"""

import json
import time
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data" / "processed"
SCHEMA_PATH = DATA_DIR / "OEB_concept_schema.json"
INDEX_DIR = ROOT_DIR / "index" / "concept_dense_e5"

MODEL_NAME = "intfloat/multilingual-e5-base"
DOC_PREFIX = "passage: "


def build_index(schema_path=SCHEMA_PATH, index_dir=INDEX_DIR):
    """Build concept-level E5 index from schema JSON.

    Loads concept texts, encodes with E5, saves standard index artifacts.
    """
    from sentence_transformers import SentenceTransformer

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    # Sorted parent_keys for deterministic ordering
    parent_keys = sorted(schema.keys())
    concepts = [schema[pk]["concept"] for pk in parent_keys]

    # Prepend doc prefix (E5 convention: "passage: " for documents)
    texts = [f"{DOC_PREFIX}{c}" for c in concepts]

    print(f"[concept_dense_e5] Encoding {len(texts)} concepts with {MODEL_NAME}...")

    model = SentenceTransformer(MODEL_NAME)
    t0 = time.time()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,  # L2-normalize for cosine = dot product
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype(np.float32)
    elapsed = time.time() - t0

    print(f"[concept_dense_e5] Shape: {embeddings.shape} | Time: {elapsed:.2f}s")

    # --- Save artifacts ---
    data_dir = index_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # embeddings.npy -- (N_concepts, dim)
    np.save(data_dir / "embeddings.npy", embeddings)

    # mapping.jsonl -- doc_id -> parent_key
    with open(index_dir / "mapping.jsonl", "w", encoding="utf-8") as f:
        for i, pk in enumerate(parent_keys):
            line = json.dumps({"doc_id": i, "external_id": pk}, ensure_ascii=False)
            f.write(line + "\n")

    # meta.json
    meta = {
        "method": "concept_dense_e5",
        "model_name": MODEL_NAME,
        "dim": int(embeddings.shape[1]),
        "num_docs": int(embeddings.shape[0]),
        "normalize": True,
        "doc_prefix": DOC_PREFIX,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(index_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # fields.json
    with open(index_dir / "fields.json", "w", encoding="utf-8") as f:
        json.dump({"text_field": "concept"}, f, ensure_ascii=False, indent=2)

    print(f"[concept_dense_e5] Index saved to {index_dir}")
    return embeddings, parent_keys


def sanity_check(index_dir=INDEX_DIR, n_queries=50):
    """Test concept-level retrieval on a sample of queries.

    Loads the concept index via the existing DenseE5Searcher, encodes
    sample queries, and reports parent-level Acc@1.
    """
    import sys
    import pandas as pd

    sys.path.insert(0, str(ROOT_DIR))
    from src.retrievers.dense_e5 import load as load_searcher

    queries_path = DATA_DIR / "OEB_short_norm.parquet"
    df = pd.read_parquet(queries_path)

    # Keep only leaf queries (parent_key ending with $)
    df = df[df["parent_key"].str.endswith("$")]
    sample = df.sample(n=min(n_queries, len(df)), random_state=42)

    print(f"\n[concept_dense_e5] Sanity check: {len(sample)} queries...")
    searcher = load_searcher(index_dir)

    queries = sample["text"].tolist()
    gt_parents = sample["parent_key"].tolist()

    # Batch search for efficiency
    top_idx, top_sco = searcher.search_batch(queries, k=1)

    correct = 0
    for i in range(len(queries)):
        pred = searcher.external_ids[top_idx[i, 0]]
        if pred == gt_parents[i]:
            correct += 1

    acc = correct / len(queries)
    print(f"[concept_dense_e5] Result: {correct}/{len(queries)} = {acc:.1%} parent Acc@1")
    return acc


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Concept-level E5 index builder")
    parser.add_argument(
        "--sanity-check-only",
        action="store_true",
        help="Skip building, only run sanity check on existing index",
    )
    args = parser.parse_args()

    if not args.sanity_check_only:
        build_index()

    sanity_check()
