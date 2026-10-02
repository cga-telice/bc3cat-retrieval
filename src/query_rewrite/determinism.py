"""The 100-query regeneration test — S9 work item 1 (c), exit criterion 2.

For each LLM transform: 100 dev queries, 20 from each base drawn with a fixed seed, generated twice
without the cache, in two separate passes over the sample. The design requires byte-identical responses;
if they are not, the rate is recorded as an amendment and the cached generation is the artefact. Every
response must also parse (`prompts.parse`).

No retrieval is run and nothing is scored. Output: `logs/S9/determinism_<transform>.json`, with the
model digest, ollama version, prompt SHA-256, the sample's keys and every mismatch.

    python src/query_rewrite/determinism.py hyde rewrite
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from query_rewrite.llm import OllamaClient  # noqa: E402
from query_rewrite.prompts import FORMAT_FOR, MODEL_FOR, PROMPT_SHA256, parse, render  # noqa: E402
from utils.run_context import S9_BASES  # noqa: E402
from utils.splits import load_split  # noqa: E402

SEED = 20261002
PER_BASE = 20


def sample() -> list[dict]:
    dev = load_split("dev")
    rng = random.Random(SEED)
    out = []
    for base in S9_BASES:
        records = json.loads((REPO / "data" / "processed" / f"OE_{base}.json").read_text(encoding="utf-8"))
        out += [{"base": base, "key": r["item_key"], "text": r["text"]}
                for r in rng.sample([r for r in records if r["parent_key"] in dev], PER_BASE)]
    return out


def run(transform: str, queries: list[dict]) -> dict:
    client = OllamaClient(MODEL_FOR[transform])
    passes = []
    for _ in range(2):
        passes.append([client.generate(render(transform, q["text"]), FORMAT_FOR[transform]) for q in queries])
    mismatches, unparsed = [], []
    for q, a, b in zip(queries, *passes):
        if a["response"] != b["response"]:
            mismatches.append({"key": q["key"], "base": q["base"], "first": a["response"], "second": b["response"]})
        try:
            parse(transform, a["response"])
        except (ValueError, KeyError) as err:
            unparsed.append({"key": q["key"], "error": repr(err), "response": a["response"]})
    return {
        "transform": transform,
        "model": client.model,
        "model_digest": client.digest,
        "ollama_version": client.version,
        "options": client.options,
        "prompt_sha256": PROMPT_SHA256[transform],
        "seed": SEED,
        "n": len(queries),
        "identical": len(queries) - len(mismatches),
        "unparsed": unparsed,
        "truncated": sum(1 for r in passes[0] if r["done_reason"] == "length"),
        "seconds_pass1": round(sum(r["seconds"] for r in passes[0]), 1),
        "keys": [q["key"] for q in queries],
        "mismatches": mismatches,
    }


def main(transforms: list[str]) -> None:
    queries = sample()
    out_dir = REPO / "logs" / "S9"
    out_dir.mkdir(parents=True, exist_ok=True)
    for transform in transforms:
        result = run(transform, queries)
        (out_dir / f"determinism_{transform}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{transform}: {result['identical']}/{result['n']} identical, {len(result['unparsed'])} unparsed, "
              f"{result['truncated']} truncated, {result['seconds_pass1']} s per pass")


if __name__ == "__main__":
    main(sys.argv[1:] or ["hyde", "rewrite"])
