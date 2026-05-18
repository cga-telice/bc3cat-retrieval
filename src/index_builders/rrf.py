# /src/index_builders/rrf.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Tuple
import json, shutil, yaml

def _read_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(p: Path, obj: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def select_field(feats_meta: Dict[str, Any]) -> str:
    """
    For parity with other builders. Not actually used to build any matrix,
    but the index_build notebook may call this. We default to the unigram column.
    """
    tf = (feats_meta or {}).get("text_fields", {}) or {}
    return tf.get("word_unigram") or tf.get("char_ngram") or "text_word"

def build(cfg: Dict[str, Any], long_df=None, text_field: str|None=None) -> Tuple[Dict[str, Any], Any, Any]:
    """
    Build a *virtual* index for an RRF method so retrieve.ipynb can run unchanged.
    Returns (artifacts, transformer, X_docs) to respect the builder signature,
    but we write files directly because we need to copy mapping.jsonl.
    """
    # Resolve config
    method_name = cfg.get("method_name") or cfg.get("method", {}).get("name") or "rrf"
    paths = cfg.get("paths", {})
    index_root = Path(paths.get("index_root", "/work/index"))
    out_dir = index_root / method_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data").mkdir(exist_ok=True)

    rrf_cfg = cfg.get("rrf", {}) or {}
    comps = rrf_cfg.get("components", [])
    if not comps:
        raise ValueError("rrf.components is empty in YAML")

    # Use the first component as source of mapping + fields
    first_idx = Path(comps[0]["index_dir"])
    mapping_src = first_idx / "mapping.jsonl"
    fields_src  = first_idx / "fields.json"
    meta_src    = first_idx / "meta.json"
    if not mapping_src.exists():
        raise FileNotFoundError(f"Missing mapping.jsonl at {mapping_src}")
    if not fields_src.exists():
        raise FileNotFoundError(f"Missing fields.json at {fields_src}")
    if not meta_src.exists():
        raise FileNotFoundError(f"Missing meta.json at {meta_src}")

    # Copy mapping.jsonl verbatim — ensures 0..N-1 doc ids and shared external_ids
    _copy(mapping_src, out_dir / "mapping.jsonl")

    # Reuse the text field from the component so the notebook knows which column to read
    fields = _read_json(fields_src)
    text_field_final = fields.get("text_field", "text_word")
    _write_json(out_dir / "fields.json", {"text_field": text_field_final})

    # Minimal meta.json for RRF
    meta_base = _read_json(meta_src)
    meta = {
        "method": "rrf",
        "variant": method_name,
        "text_field": text_field_final,
        "num_docs": meta_base.get("num_docs"),
        "params": {
            "rrf_constant": int(rrf_cfg.get("rrf_constant", 60)),
            "k_each": int(rrf_cfg.get("k_each", 200)),
            "components": [{"name": c["name"], "weight": c.get("weight", 1.0), "k": c.get("k", None)} for c in comps],
        },
    }
    _write_json(out_dir / "meta.json", meta)

    # For parity with other builders, return a small artifacts dict (nothing to persist further)
    artifacts = {
        "__created__": True,
        "__index_dir__": str(out_dir),
        "fields.json": {"text_field": text_field_final},
        "meta.json": meta,
        "mapping.jsonl": str(out_dir / "mapping.jsonl"),
    }
    return artifacts, None, None

def build_from_yaml(yaml_path: str|Path) -> Tuple[Dict[str, Any], Any, Any]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return build(cfg)
