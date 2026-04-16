#!/usr/bin/env python3
"""
Create pseudo-index directories for the structured pipeline variants.

Each directory contains:
  - meta.json   — pipeline config (stage2_method, oracle flag, etc.)
  - fields.json — text_field specification
  - mapping.jsonl — copied from the E5 index (same document space)
  - data/       — empty directory (required by retrieve.ipynb validation)

Usage:
    python scripts/setup_structured_index.py
"""

from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
INDEX_ROOT = ROOT / "index"
E5_MAPPING = INDEX_ROOT / "dense_e5" / "mapping.jsonl"

# Count docs from E5 mapping
NUM_DOCS = sum(1 for _ in open(E5_MAPPING, encoding="utf-8") if _.strip())

# ── Variant definitions ──────────────────────────────────────────────────────

VARIANTS = [
    {
        "name": "structured_pipeline",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
    },
    {
        "name": "structured_pipeline_rules",
        "stage2_method": "rules",
        "oracle": False,
    },
    {
        "name": "structured_pipeline_oracle",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
    },
    {
        "name": "structured_pipeline_oracle_rules",
        "stage2_method": "rules",
        "oracle": True,
    },
    {
        "name": "structured_pipeline_classify",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
        "stage2_prompt_mode": "classify",
    },
    {
        "name": "structured_pipeline_oracle_classify",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
        "stage2_prompt_mode": "classify",
    },
    {
        "name": "structured_pipeline_twostep",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
        "stage2_prompt_mode": "twostep",
    },
    {
        "name": "structured_pipeline_oracle_twostep",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
        "stage2_prompt_mode": "twostep",
    },
    {
        "name": "structured_pipeline_paraaware",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
        "stage2_prompt_mode": "paraaware",
    },
    {
        "name": "structured_pipeline_oracle_paraaware",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
        "stage2_prompt_mode": "paraaware",
    },
    # Phi-4 14B variants (Sprint 10)
    {
        "name": "structured_pipeline_phi4_extract",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
    },
    {
        "name": "structured_pipeline_oracle_phi4_extract",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
    },
    {
        "name": "structured_pipeline_phi4_classify",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
        "stage2_prompt_mode": "classify",
    },
    {
        "name": "structured_pipeline_oracle_phi4_classify",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
        "stage2_prompt_mode": "classify",
    },
    # Phi-4 14B twostep + paraaware variants (Sprint 11)
    {
        "name": "structured_pipeline_phi4_twostep",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
        "stage2_prompt_mode": "twostep",
    },
    {
        "name": "structured_pipeline_oracle_phi4_twostep",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
        "stage2_prompt_mode": "twostep",
    },
    {
        "name": "structured_pipeline_phi4_paraaware",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
        "stage2_prompt_mode": "paraaware",
    },
    {
        "name": "structured_pipeline_oracle_phi4_paraaware",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
        "stage2_prompt_mode": "paraaware",
    },
    # Paraaware2 variants (Sprint 12)
    {
        "name": "structured_pipeline_paraaware2",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
        "stage2_prompt_mode": "paraaware2",
    },
    {
        "name": "structured_pipeline_oracle_paraaware2",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "llama3.1:8b",
        "stage2_prompt_mode": "paraaware2",
    },
    {
        "name": "structured_pipeline_phi4_paraaware2",
        "stage2_method": "llm",
        "oracle": False,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
        "stage2_prompt_mode": "paraaware2",
    },
    {
        "name": "structured_pipeline_oracle_phi4_paraaware2",
        "stage2_method": "llm",
        "oracle": True,
        "stage2_ollama_url": "http://ollama:11434",
        "stage2_model": "phi4:latest",
        "stage2_prompt_mode": "paraaware2",
    },
    # ── Classifier variants (lightweight-extraction branch) ──
    {
        "name": "structured_pipeline_classifier",
        "stage2_method": "classifier",
        "oracle": False,
        "stage2_model_dir": "/work/models/e5_classifier",
    },
    {
        "name": "structured_pipeline_oracle_classifier",
        "stage2_method": "classifier",
        "oracle": True,
        "stage2_model_dir": "/work/models/e5_classifier",
    },
    # ── Frozen-encoder classifier variants (Sprint LW-07 baseline) ──
    {
        "name": "structured_pipeline_classifier_frozen",
        "stage2_method": "classifier",
        "oracle": False,
        "stage2_model_dir": "/work/models/e5_classifier_frozen",
    },
    {
        "name": "structured_pipeline_oracle_classifier_frozen",
        "stage2_method": "classifier",
        "oracle": True,
        "stage2_model_dir": "/work/models/e5_classifier_frozen",
    },
]


def setup_variant(variant: dict) -> None:
    """Create a pseudo-index directory for one pipeline variant."""
    name = variant["name"]
    idx_dir = INDEX_ROOT / name

    # Create directory structure
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / "data").mkdir(exist_ok=True)

    # meta.json — pipeline config
    params = {"stage2_method": variant["stage2_method"], "oracle": variant["oracle"]}
    if variant.get("stage2_ollama_url"):
        params["stage2_ollama_url"] = variant["stage2_ollama_url"]
    if variant.get("stage2_model"):
        params["stage2_model"] = variant["stage2_model"]
    if variant.get("stage2_prompt_mode"):
        params["stage2_prompt_mode"] = variant["stage2_prompt_mode"]
    if variant.get("stage2_model_dir"):
        params["stage2_model_dir"] = variant["stage2_model_dir"]

    meta = {
        "method": "structured_pipeline",
        "impl": "structured_pipeline",
        "variant": name,
        "text_field": "text_norm",
        "num_docs": NUM_DOCS,
        "params": params,
    }
    with open(idx_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # fields.json
    fields = {"text_field": "text_norm"}
    with open(idx_dir / "fields.json", "w", encoding="utf-8") as f:
        json.dump(fields, f, indent=2, ensure_ascii=False)

    # mapping.jsonl — copy from E5 index (not symlink, for Windows compat)
    dest_mapping = idx_dir / "mapping.jsonl"
    if not dest_mapping.exists() or dest_mapping.stat().st_size != E5_MAPPING.stat().st_size:
        shutil.copy2(E5_MAPPING, dest_mapping)
        print(f"  OK {name}: mapping.jsonl copied ({dest_mapping.stat().st_size:,} bytes)")
    else:
        print(f"  OK {name}: mapping.jsonl already up-to-date")


def main():
    print(f"Setting up structured pipeline index directories")
    print(f"  E5 mapping: {E5_MAPPING}")
    print(f"  Num docs:   {NUM_DOCS}")
    print(f"  Index root: {INDEX_ROOT}")
    print()

    if not E5_MAPPING.exists():
        raise FileNotFoundError(f"E5 mapping not found: {E5_MAPPING}")

    for variant in VARIANTS:
        setup_variant(variant)

    # Verify all directories
    print(f"\nVerification:")
    all_ok = True
    for variant in VARIANTS:
        name = variant["name"]
        idx_dir = INDEX_ROOT / name
        required = ["meta.json", "fields.json", "mapping.jsonl"]
        missing = [f for f in required if not (idx_dir / f).exists()]
        data_ok = (idx_dir / "data").is_dir()

        if missing or not data_ok:
            print(f"  FAIL {name}: missing {missing}, data/={'OK' if data_ok else 'MISSING'}")
            all_ok = False
        else:
            meta = json.load(open(idx_dir / "meta.json", encoding="utf-8"))
            s2 = meta["params"]["stage2_method"]
            oracle = meta["params"]["oracle"]
            pmode = meta["params"].get("stage2_prompt_mode", "")
            mode_str = f", prompt_mode={pmode}" if pmode else ""
            print(f"  OK {name}: stage2={s2}, oracle={oracle}{mode_str}")

    if all_ok:
        print(f"\nAll {len(VARIANTS)} index directories ready.")
    else:
        print(f"\nERROR: Some directories have issues.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
