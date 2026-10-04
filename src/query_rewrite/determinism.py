"""The 100-query regeneration test — S9 work item 1 (c), exit criterion 2.

For each LLM transform: 100 dev queries, 20 from each base drawn with a fixed seed, generated twice
without the cache, in two separate passes over the sample. The design requires byte-identical responses;
if they are not, the rate is recorded as an amendment and the cached generation is the artefact. Every
response must also parse (`prompts.parse`).

No retrieval is run and nothing is scored. Output: `logs/S9/determinism_<transform>.json`, with the
model digest, ollama version, prompt SHA-256, the sample's keys and every mismatch.

    python src/query_rewrite/determinism.py hyde rewrite
    python src/query_rewrite/determinism.py extract

`extract` (S9 work item 4, A1's pending rate) checks the LLM extractor the same way: `phi4`, the source's
`extract` prompt (`pipeline.prompts.build_extraction_prompt`) on the query's normalised text, as the
pipeline passes it. The prompt needs a concept; this test uses the query's gold concept, since it measures
only whether generation repeats, and no extraction is scored. A response "parses" if the source's own
parser returns an object.

`--s11` (S11 work item 2) runs the same `extract` check on the two E3 dev sets the S11 arms are the first LLM
to see, 50 queries from each with the same seed, and writes `logs/S11/determinism_extract.json`.

    python src/query_rewrite/determinism.py extract --s11
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from query_rewrite.llm import OllamaClient  # noqa: E402
from pipeline.param_extractor import LLMParamExtractor  # noqa: E402
from pipeline.prompts import build_extraction_prompt  # noqa: E402
from query_rewrite.prompts import FORMAT_FOR, MODEL_FOR, PROMPT_SHA256, parse, render  # noqa: E402
from retrievers.structured_pipeline import LLM_MODEL  # noqa: E402
from utils.corpus_prep import normalize_text  # noqa: E402
from utils.run_context import S9_BASES  # noqa: E402
from utils.splits import load_split  # noqa: E402

SEED = 20261002
PER_BASE = 20


#: S11 work item 2: the E3 dev sets and how many queries each contributes to the 100.
S11_BASES = ("dose_texto", "isolated_texto")
S11_PER_BASE = 50


def sample(bases=S9_BASES, per_base: int = PER_BASE) -> list[dict]:
    dev = load_split("dev")
    rng = random.Random(SEED)
    out = []
    for base in bases:
        records = json.loads((REPO / "data" / "processed" / f"OE_{base}.json").read_text(encoding="utf-8"))
        out += [{"base": base, "key": r["item_key"], "text": r["text"], "parent_key": r["parent_key"]}
                for r in rng.sample([r for r in records if r["parent_key"] in dev], per_base)]
    return out


SCHEMA = REPO / "data" / "processed" / "OE_concept_schema.json"


def _extract_prompt(q: dict, schema: dict) -> str:
    group = schema[q["parent_key"]]
    return build_extraction_prompt(group["concept"], group["axes"], normalize_text(q["text"]))


def run(transform: str, queries: list[dict]) -> dict:
    if transform == "extract":
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        client = OllamaClient(LLM_MODEL)
        prompt_of, fmt, prompt_sha = (lambda q: _extract_prompt(q, schema)), None, None
    else:
        client = OllamaClient(MODEL_FOR[transform])
        prompt_of, fmt, prompt_sha = (lambda q: render(transform, q["text"])), FORMAT_FOR[transform], PROMPT_SHA256[transform]
    passes = []
    for _ in range(2):
        passes.append([client.generate(prompt_of(q), fmt) for q in queries])
    mismatches, unparsed = [], []
    for q, a, b in zip(queries, *passes):
        if a["response"] != b["response"]:
            mismatches.append({"key": q["key"], "base": q["base"], "first": a["response"], "second": b["response"]})
        if transform == "extract":
            if LLMParamExtractor._parse_json_response(a["response"]) is None:
                unparsed.append({"key": q["key"], "error": "no JSON object", "response": a["response"]})
            continue
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
        "prompt_sha256": prompt_sha,
        "seed": SEED,
        "n": len(queries),
        "identical": len(queries) - len(mismatches),
        "unparsed": unparsed,
        "truncated": sum(1 for r in passes[0] if r["done_reason"] == "length"),
        "seconds_pass1": round(sum(r["seconds"] for r in passes[0]), 1),
        "keys": [q["key"] for q in queries],
        "mismatches": mismatches,
    }


def main(transforms: list[str], s11: bool = False) -> None:
    if s11 and transforms != ["extract"]:
        raise SystemExit("--s11 checks the extractor only")
    queries = sample(S11_BASES, S11_PER_BASE) if s11 else sample()
    out_dir = REPO / "logs" / ("S11" if s11 else "S9")
    out_dir.mkdir(parents=True, exist_ok=True)
    for transform in transforms:
        result = run(transform, queries)
        (out_dir / f"determinism_{transform}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{transform}: {result['identical']}/{result['n']} identical, {len(result['unparsed'])} unparsed, "
              f"{result['truncated']} truncated, {result['seconds_pass1']} s per pass")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--s11"]
    main(args or ["hyde", "rewrite"], s11="--s11" in sys.argv[1:])
