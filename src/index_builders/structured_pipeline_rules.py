# /src/index_builders/structured_pipeline_rules.py
"""Pseudo-index for the structured pipeline: rules Stage 2 (D-026) or the oracle bound (S5).

The pipeline owns no matrix: Stage 1 reads an E5 index, Stages 2–3 read the concept schema and
the normalised corpus. What `index_builder.ipynb` writes here is only what `retrieve.ipynb`
requires of any index — `mapping.jsonl`, `fields.json`, `meta.json`, `data/` — with the
pipeline's configuration carried in `meta.json.params`.

Replaces `scripts/setup_structured_index.py` on `research/structured-retrieval@85c3359`,
which wrote the directories outside the config contract and copied `mapping.jsonl` from
`index/dense_e5`. Here the notebook writes the mapping from the corpus like any other index,
and `retrievers.structured_pipeline.load` refuses to run if it disagrees with Stage 1's.
"""
from typing import Any, Dict

import pandas as pd

# The query field Stage 1 and Stage 2 receive, as on the source branch.
TEXT_FIELD = "text_norm"


def select_field(feats_meta: Dict[str, Any]) -> str:
    return TEXT_FIELD


def build(cfg: Dict[str, Any], long_df: pd.DataFrame, text_field: str):
    p = cfg["method"].get("params") or {}
    if p.get("stage2_method") not in ("rules", "oracle_params"):
        raise ValueError(
            f"stage2_method={p.get('stage2_method')!r}: only 'rules' (D-026) and "
            "'oracle_params' (S5) exist here"
        )
    if p.get("oracle"):
        raise ValueError("oracle-parent mode is not ported (S5)")
    if p.get("stage3_value_match", "literal") not in ("literal", "normalized"):
        raise ValueError(f"stage3_value_match={p.get('stage3_value_match')!r}")
    if not p.get("stage1_index"):
        raise ValueError("method.params.stage1_index is required: the E5 index Stage 1 reads")

    n = len(long_df)
    print(
        f"[structured_pipeline_rules] pseudo-index | docs={n} | stage1={p['stage1_index']} "
        f"| stage3_value_match={p.get('stage3_value_match', 'literal')}"
    )
    artifacts = {"__num_docs__": int(n)}
    return artifacts, None, None
