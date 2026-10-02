"""Why TF-IDF barely shows the rare-code pattern — S9 work item 3, D-041's open question. Descriptive.

S91 found that on coded `resumen`, `bm25_unigram`'s rank-1 document holds a rare code token the gold lacks
in most of its parent misses, and `tfidf_phrases_replace`'s almost never, with the same tokenizer. D-041
asked why before any guard is built. Both arms score a query as a sum over its terms of
(query weight × document weight), so the rank-1 score of a miss splits exactly into per-term
contributions. This module computes that split with each arm's own index and query encoder, and reports
the share carried by rare tokens, beside the IDF range each arm gives the query's tokens.

"Rare" is S91's rule, unchanged: a token in fewer than `RARE_MAX_DOCS` corpus documents, document
frequency read from the plain-word BM25 index (`text_word`, the S91 generator's tokenisation). Population:
dev coded `resumen` queries each arm misses at parent level, from the S91-era runs already on disk. No
run is made.
"""

from __future__ import annotations

import gzip
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from retrievers.bm25_unigram import BM25Searcher  # noqa: E402
from retrievers.tfidf_unigram import TfidfSearcher  # noqa: E402
from utils.splits import load_split  # noqa: E402

RARE_MAX_DOCS = 1_200
INDEX = REPO / "index" / "OE"
RUNS = REPO / "runs" / "OE"
SHORT_FEATS = REPO / "data" / "processed" / "OE_short_feats.parquet"
DF_SOURCE = "bm25_unigram__k1-0.60__b-0.35__OE"

ARMS = {
    "bm25_unigram": ("bm25_unigram__k1-0.60__b-0.35__OE", BM25Searcher),
    "tfidf_phrases_replace": ("tfidf_unigram_phrases_replace__OE", TfidfSearcher),
}


@dataclass
class ArmSplit:
    arm: str
    misses: int
    rare_share: np.ndarray          # per miss: share of the rank-1 score carried by rare query tokens
    rare_idf: float                 # median IDF of the rare tokens these queries carry
    other_idf: float                # median IDF of their other in-vocabulary tokens


def rare_tokens() -> set[str]:
    data = INDEX / DF_SOURCE / "data"
    vocab = json.loads((data / "vocab.json").read_text(encoding="utf-8"))
    df = np.load(data / "df.npy")
    return {t for t, j in vocab.items() if df[j] < RARE_MAX_DOCS}


def parent_misses(method: str, dev_keys: set[str], parent_of: dict[str, str]) -> dict[str, str]:
    """query key -> rank-1 document key, for dev queries whose rank-1 is in another concept."""
    out = {}
    with gzip.open(RUNS / "resumen" / method / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            key = str(rec["query_item_key"])
            if key not in dev_keys:
                continue
            top = str(rec["candidates"][0]["index_item_key"])
            if parent_of[top] != parent_of[key]:
                out[key] = top
    return out


def split_arm(arm: str, rare: set[str], feats: pd.DataFrame, parent_of: dict[str, str], dev_keys: set[str]) -> ArmSplit:
    method, cls = ARMS[arm]
    s = cls(INDEX / method)
    field = s.meta.get("text_field") or s.fields.get("text_field")
    vocab = s.vec_q.vocabulary
    inverse = {j: t for t, j in vocab.items()}
    row_of = {k: i for i, k in enumerate(s.external_ids)}
    misses = parent_misses(method, dev_keys, parent_of)
    keys = sorted(misses)
    texts = feats.set_index("item_key").loc[keys, field].fillna("").astype(str).tolist()
    Q = s._encode_queries_idf(texts) if isinstance(s, BM25Searcher) else s.encode(texts)
    Q = Q.tocsr()
    idf = s.idf if isinstance(s, BM25Searcher) else s.vec_q._tfidf.idf_
    shares, rare_idf, other_idf = [], [], []
    for i, k in enumerate(keys):
        row = Q.getrow(i)
        doc = s.X_docs.getrow(row_of[misses[k]])
        contrib = row.multiply(doc).tocsr()
        total = contrib.sum()
        terms = {inverse[j]: v for j, v in zip(contrib.indices, contrib.data)}
        shares.append(sum(v for t, v in terms.items() if t in rare) / total if total > 0 else 0.0)
        for j in row.indices:
            (rare_idf if inverse[j] in rare else other_idf).append(float(idf[j]))
    return ArmSplit(arm, len(keys), np.asarray(shares), float(np.median(rare_idf)) if rare_idf else float("nan"),
                    float(np.median(other_idf)))


def run() -> list[ArmSplit]:
    dev = load_split("dev")
    corpus = json.loads((REPO / "data" / "processed" / "OE_texto.json").read_text(encoding="utf-8"))
    parent_of = {str(r["item_key"]): r["parent_key"] for r in corpus}
    dev_keys = {k for k, p in parent_of.items() if p in dev}
    feats = pd.read_parquet(SHORT_FEATS)
    rare = rare_tokens()
    return [split_arm(arm, rare, feats, parent_of, dev_keys) for arm in ARMS]


if __name__ == "__main__":
    for a in run():
        q = np.percentile(a.rare_share, [25, 50, 75])
        print(f"{a.arm}: {a.misses:,} parent misses; rare share of rank-1 score quartiles "
              f"{q.round(3).tolist()}, > 0.5 in {np.mean(a.rare_share > 0.5):.1%}; "
              f"median IDF rare {a.rare_idf:.2f} vs other {a.other_idf:.2f}")
