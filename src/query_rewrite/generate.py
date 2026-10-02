"""Generate the LLM-transformed query sets — S9 work item 2 (transforms H and W).

For each transform and base: the base's **dev** records (test queries are never sent to a model), each
query rendered with the committed prompt, generated through the cache, parsed, and written as
`data/processed/OE_{base}__{transform}.json` — the base's dev records with only `text` changed — plus a
provenance sidecar `OE_{base}__{transform}.meta.json`.

- **hyde**: text = original query, a newline, the generated description (design, work item 2).
- **rewrite**: text = the generated rewrite.

The cache is `data/processed/llm_cache/OE_{base}__{transform}.jsonl`, append-only, so an interrupted run
resumes where it stopped. A response that does not parse leaves that query's text unchanged and is counted
in the sidecar as `fallback`; it is never repaired by hand. Any fallback is reported as an amendment.

    python src/query_rewrite/generate.py hyde rewrite
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from query_rewrite.llm import Cache, OllamaClient, write_sidecar  # noqa: E402
from query_rewrite.prompts import FORMAT_FOR, MODEL_FOR, PROMPT_SHA256, parse, render  # noqa: E402
from utils.run_context import S9_BASES  # noqa: E402
from utils.splits import load_split  # noqa: E402

DATA = REPO / "data" / "processed"
CACHE_DIR = DATA / "llm_cache"


def compose(transform: str, original: str, generated: str) -> str:
    if transform == "hyde":
        return original.rstrip() + "\n" + generated
    return generated


def generate_set(client: OllamaClient, transform: str, base: str, dev: frozenset[str]) -> None:
    name = f"OE_{base}__{transform}"
    out = DATA / f"{name}.json"
    records = [r for r in json.loads((DATA / f"OE_{base}.json").read_text(encoding="utf-8")) if r["parent_key"] in dev]
    cache = Cache(CACHE_DIR / f"{name}.jsonl")
    generated, accounting, fallback = [], [], []
    start = time.time()
    for i, r in enumerate(records, 1):
        rec = cache.get_or_generate(client, r["item_key"], render(transform, r["text"]), FORMAT_FOR[transform])
        accounting.append(rec)
        try:
            text = compose(transform, r["text"], parse(transform, rec["response"]))
        except (ValueError, KeyError):
            fallback.append(r["item_key"])
            text = r["text"]
        generated.append({**r, "text": text})
        if i % 250 == 0:
            print(f"  {name}: {i:,}/{len(records):,} ({time.time() - start:,.0f} s)", flush=True)
    payload = json.dumps(generated, ensure_ascii=False, indent=2)
    if out.exists() and out.read_text(encoding="utf-8") != payload:
        raise SystemExit(f"{out.name} exists with other content; refusing to overwrite a set runs may stamp")
    out.write_text(payload, encoding="utf-8")
    sidecar = DATA / f"{name}.meta.json"
    write_sidecar(sidecar, client, transform, PROMPT_SHA256[transform], accounting)
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    meta.update({"base": base, "fallback": len(fallback), "fallback_keys": fallback,
                 "cache": f"llm_cache/{name}.jsonl"})
    sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written: {out.name} ({len(generated):,} records, {len(fallback)} fallback, "
          f"{meta['truncated']} truncated)", flush=True)


def main(transforms: list[str]) -> None:
    dev = load_split("dev")
    for transform in transforms:
        client = OllamaClient(MODEL_FOR[transform])
        print(f"{transform}: {client.model} {client.digest[:12]}, ollama {client.version}, "
              f"prompt {PROMPT_SHA256[transform][:8]}", flush=True)
        for base in S9_BASES:
            generate_set(client, transform, base, dev)


if __name__ == "__main__":
    main(sys.argv[1:] or ["hyde", "rewrite"])
