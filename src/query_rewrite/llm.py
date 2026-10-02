"""The ollama client every S9 LLM arm goes through — S9 work item 1 (c).

Generation is outside the harness's own determinism, so the design puts it inside the provenance chain
instead: every generation is cached on disk, and the generated query file a run reads is what the run
stamps. This module makes that chain checkable:

- **The model is named by digest.** At start the client asks the server for its models and refuses to run
  unless the tag resolves to the expected digest prefix. A tag can be re-pulled to other weights; a digest
  cannot.
- **Options are fixed** (design, work item 1 (c)): `temperature 0`, `seed 20260915`, `num_predict 256`,
  `num_ctx 4096`. They are part of every cache key, so a changed option never reads a stale answer.
- **The cache** is one JSONL per generated set. A line holds the cache key, the query key, the response,
  the server's token counts, `done_reason` and wall-clock seconds. Lines are only appended; a resumed run
  skips keys already present.
- **The sidecar** (`write_sidecar`) records model, digest, ollama version, prompt SHA-256, options, n and
  timing, beside the generated query file.

The server is reached at `$OLLAMA_URL`, default `http://host.docker.internal:11434`, which answers from
`bc3cat-s3` (checked 2026-10-02).
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

DEFAULT_URL = "http://host.docker.internal:11434"

#: The design's options (S9 work item 1 (c)). Changing one is an amendment.
OPTIONS = {"temperature": 0, "seed": 20260915, "num_predict": 256, "num_ctx": 4096}

#: The models the design fixes, by tag and digest prefix (S9 design, Depends on).
MODELS = {
    "qwen2.5:14b": "7cdf5a0187d5",
    "phi4:latest": "ac896e5b8b34",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class OllamaClient:
    model: str
    url: str = field(default_factory=lambda: os.environ.get("OLLAMA_URL", DEFAULT_URL))
    options: dict = field(default_factory=lambda: dict(OPTIONS))
    timeout: float = 600.0
    digest: str = field(init=False, default="")
    version: str = field(init=False, default="")

    def __post_init__(self) -> None:
        if self.model not in MODELS:
            raise ValueError(f"{self.model!r} is not a model the S9 design fixes: {sorted(MODELS)}")
        self.version = requests.get(f"{self.url}/api/version", timeout=30).json()["version"]
        tags = requests.get(f"{self.url}/api/tags", timeout=30).json()["models"]
        found = {m["name"]: m["digest"] for m in tags}
        if self.model not in found:
            raise RuntimeError(f"{self.model} is not on the server at {self.url}; it has {sorted(found)}")
        if not found[self.model].startswith(MODELS[self.model]):
            raise RuntimeError(
                f"{self.model} resolves to {found[self.model][:12]}, not the design's {MODELS[self.model]}: "
                "the tag now names other weights"
            )
        self.digest = found[self.model]

    def key(self, prompt: str, fmt: str | None = None) -> str:
        """Cache key: model digest, options, output format and the full prompt."""
        payload = json.dumps([self.digest, self.options, fmt, prompt], ensure_ascii=False, sort_keys=True)
        return sha256_text(payload)

    def generate(self, prompt: str, fmt: str | None = None) -> dict:
        """One uncached generation. `fmt="json"` asks the server for a JSON object. Returns the response
        and the server's accounting."""
        body = {"model": self.model, "prompt": prompt, "stream": False, "options": self.options}
        if fmt:
            body["format"] = fmt
        start = time.perf_counter()
        r = requests.post(f"{self.url}/api/generate", json=body, timeout=self.timeout)
        r.raise_for_status()
        body = r.json()
        return {
            "response": body["response"],
            "done_reason": body.get("done_reason"),
            "prompt_eval_count": body.get("prompt_eval_count"),
            "eval_count": body.get("eval_count"),
            "seconds": round(time.perf_counter() - start, 3),
        }


class Cache:
    """Append-only JSONL cache of generations for one generated set."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lines: dict[str, dict] = {}
        if self.path.exists():
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        rec = json.loads(line)
                        self.lines[rec["cache_key"]] = rec

    def get_or_generate(self, client: OllamaClient, query_key: str, prompt: str, fmt: str | None = None) -> dict:
        key = client.key(prompt, fmt)
        if key in self.lines:
            return self.lines[key]
        rec = {"cache_key": key, "query_key": query_key, **client.generate(prompt, fmt)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.lines[key] = rec
        return rec


def write_sidecar(path: Path, client: OllamaClient, prompt_name: str, prompt_sha: str, records: list[dict]) -> None:
    """Provenance of one generated set, beside its query file."""
    seconds = [r["seconds"] for r in records]
    sidecar = {
        "model": client.model,
        "model_digest": client.digest,
        "ollama_version": client.version,
        "options": client.options,
        "prompt": prompt_name,
        "prompt_sha256": prompt_sha,
        "n": len(records),
        "truncated": sum(1 for r in records if r.get("done_reason") == "length"),
        "seconds_total": round(sum(seconds), 1),
        "seconds_median": round(statistics.median(seconds), 3) if seconds else None,
        "eval_tokens_total": sum(r.get("eval_count") or 0 for r in records),
    }
    Path(path).write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
