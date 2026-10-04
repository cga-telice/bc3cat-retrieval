"""Stage decomposition of the S11 two-stage arms (design `931ee0c`, work item 5, T3), and K0's tie set.

For every query of a finished run, re-derive what each stage did from the run's own ranking and deterministic
code, as `structured_stages.py` does for S2 and S5:

- **Stage 1**: the parent of the run's rank-1 candidate (every arm ranks its Stage-1 family first).
- **Stage 2**: the arm's extractor on the query text the run used, for that parent. The LLM extractor reads
  only the generation cache (`OfflineClient`): a prompt absent from it raises, so nothing is ever generated here.
- **Stage 3**: the tiers the arm built: hard (matched leaves, then the rest of the family) or soft (leaves by
  number of agreeing usable axes, descending).

`consistent` holds the re-derivation to the run: the run's rank 1 is in the re-derived top tier. Every row also
gives what T3 prints (axes extracted, correct, misread; top-tier size; the gold's tier; the gold's rank within its
tier when it is in the run's top 100) and K0's **tie-free** hit: its top tier is ordered by catalogue position,
which is not a score, so the design scores the tier as one tie set, 1 / |tier| when the gold is in it.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd

from pipeline.catalog_lookup import CatalogLookup
from pipeline.param_extractor import LLMParamExtractor
from pipeline.param_extractor_rules import RuleBasedParamExtractor
from query_rewrite import llm as L

#: phi4:latest, the digest every S9 and S11 extraction was generated under (S9 design; `results/S9/cost.md`).
PHI4_DIGEST = "ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba"


class OfflineClient:
    """An `OllamaClient` stand-in that keys the cache exactly as the real one and never generates."""

    model = "phi4:latest"
    digest = PHI4_DIGEST
    version = "cache"

    def __init__(self):
        self.options = dict(L.OPTIONS)

    def key(self, prompt: str, fmt: str | None = None) -> str:
        return L.sha256_text(json.dumps([self.digest, self.options, fmt, prompt], ensure_ascii=False, sort_keys=True))

    def generate(self, prompt, fmt=None):
        raise KeyError("an extraction prompt is not in the cache; the re-derivation never generates")


def extractor_for(params: dict, schema_path: Path, cache_path: Path):
    """The Stage-2 callable an arm's `meta.json` params describe: (parent, text) -> {axis: value | None}."""
    stage2 = params["stage2_method"]
    if stage2 == "none":
        return lambda parent, text: {}
    if stage2 == "llm":
        ex = LLMParamExtractor(schema_path, OfflineClient(), L.Cache(cache_path), prompt_mode=params["llm_prompt_mode"],
                               key_match=params.get("llm_key_match", "exact"))
        return ex.extract
    if stage2 == "rules":
        ex = RuleBasedParamExtractor(schema_path)
        if params.get("stage2_canon"):
            from query_rewrite.canon import from_corpus
            canon = from_corpus()
            return lambda parent, text: ex.extract(parent, canon.apply(text)[0])
        return ex.extract
    raise ValueError(f"stage2_method={stage2!r} is not an S11 arm's")


def decompose(run_dir: Path, meta_params: dict, schema: dict, parents: dict[str, str], gold_axes: dict[str, dict],
              extract, catalog: CatalogLookup) -> pd.DataFrame:
    """One row per query of the run. `gold_axes[item]` is the leaf's {normalised axis: normalised value}."""
    soft = meta_params.get("stage3_match", "hard") == "soft"
    rows = []
    with gzip.open(run_dir / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            cands = [str(c["index_item_key"]) for c in r["candidates"]]
            s1 = parents[cands[0]]
            gold, gpar = str(r["gold_item_key"]), str(r["gold_parent_key"])
            got = extract(s1, r["query_text"])
            filters = catalog._filters(s1, got)
            family = list(schema[s1]["item_keys"])
            if soft:
                agree = catalog.agreement(s1, got)
                levels = sorted({agree[k] for k in family}, reverse=True)
                tier_of = {k: levels.index(agree[k]) for k in family}
            else:
                matched = set(catalog.lookup(s1, got))
                tier_of = {k: (0 if k in matched else 1) for k in family}
            top = min(tier_of.values())
            top_tier = [k for k in family if tier_of[k] == top]
            gold_tier = tier_of.get(gold)
            ga = gold_axes.get(gold, {}) if s1 == gpar else {}
            correct = sum(1 for a, v in filters.items() if ga.get(a) == v)
            in_tier = [k for k in cands if tier_of.get(k) == gold_tier] if gold_tier is not None else []
            rows.append({
                "key": str(r["query_item_key"]), "s1": s1, "s1_correct": s1 == gpar,
                "axes": len(schema[s1]["axes"]), "extracted": len(filters), "correct": correct,
                "misread": len(filters) - correct if s1 == gpar else len(filters),
                "top_tier_size": len(top_tier), "gold_tier": gold_tier, "gold_in_top": gold in top_tier,
                "gold_rank_in_tier": (in_tier.index(gold) + 1) if gold in in_tier else None,
                "consistent": cands[0] in top_tier,
                "item_tie_tier": (1.0 / len(top_tier)) if gold in top_tier else 0.0,
            })
    return pd.DataFrame(rows).set_index("key")


def gold_axes_from(long_norm: pd.DataFrame) -> dict[str, dict]:
    """{item_key: {label_norm: value_norm}}, as `CatalogLookup` indexes leaves."""
    out = {}
    for key, pn in zip(long_norm["item_key"], long_norm["parameters_norm"]):
        out[key] = {pn[a]["label_norm"]: pn[a]["values"][0]["value_norm"] for a in ("A", "B", "C", "D", "F")
                    if pn[a] is not None}
    return out
