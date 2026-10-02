"""S9 work item 1 (c, d): the ollama client and the prompts, without a server.

The client must refuse a tag that resolves to other weights, put every option, the output format and the
full prompt into the cache key, and never call the server for a key it already holds. The prompts must
carry nothing from a leaf and parse to text deterministically.
"""

from __future__ import annotations

import json

import pytest

from query_rewrite import llm, prompts


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        pass


@pytest.fixture
def server(monkeypatch):
    calls = []
    digest = {"qwen2.5:14b": "7cdf5a0187d5" + "0" * 52}

    def get(url, timeout):
        if url.endswith("/api/version"):
            return FakeResponse({"version": "0.17.7"})
        return FakeResponse({"models": [{"name": k, "digest": v} for k, v in digest.items()]})

    def post(url, json, timeout):
        calls.append(json)
        return FakeResponse({"response": "out", "done_reason": "stop", "eval_count": 3, "prompt_eval_count": 7})

    monkeypatch.setattr(llm.requests, "get", get)
    monkeypatch.setattr(llm.requests, "post", post)
    return {"calls": calls, "digest": digest}


def test_options_are_the_designs():
    assert llm.OPTIONS == {"temperature": 0, "seed": 20260915, "num_predict": 256, "num_ctx": 4096}


def test_client_refuses_a_tag_with_other_weights(server):
    server["digest"]["qwen2.5:14b"] = "deadbeef" * 8
    with pytest.raises(RuntimeError, match="other weights"):
        llm.OllamaClient("qwen2.5:14b", url="http://x")


def test_client_refuses_a_model_the_design_does_not_fix(server):
    with pytest.raises(ValueError):
        llm.OllamaClient("llama3.1:8b", url="http://x")


def test_cache_key_moves_with_prompt_format_and_options(server):
    c = llm.OllamaClient("qwen2.5:14b", url="http://x")
    base = c.key("p")
    assert c.key("p") == base
    assert c.key("q") != base
    assert c.key("p", "json") != base
    c.options = {**c.options, "seed": 1}
    assert c.key("p") != base


def test_cache_serves_a_known_key_without_calling_the_server(server, tmp_path):
    c = llm.OllamaClient("qwen2.5:14b", url="http://x")
    cache = llm.Cache(tmp_path / "g.jsonl")
    first = cache.get_or_generate(c, "k1", "prompt", "json")
    assert server["calls"][-1]["format"] == "json" and server["calls"][-1]["options"] == llm.OPTIONS
    again = llm.Cache(tmp_path / "g.jsonl").get_or_generate(c, "k1", "prompt", "json")
    assert len(server["calls"]) == 1
    assert again == first and first["response"] == "out" and first["query_key"] == "k1"


def test_sidecar_records_the_provenance(server, tmp_path):
    c = llm.OllamaClient("qwen2.5:14b", url="http://x")
    recs = [{"seconds": 1.0, "done_reason": "stop", "eval_count": 3}, {"seconds": 3.0, "done_reason": "length", "eval_count": 5}]
    llm.write_sidecar(tmp_path / "s.json", c, "hyde", prompts.PROMPT_SHA256["hyde"], recs)
    s = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert s["model_digest"].startswith("7cdf5a0187d5") and s["ollama_version"] == "0.17.7"
    assert s["n"] == 2 and s["truncated"] == 1 and s["seconds_median"] == 2.0 and s["eval_tokens_total"] == 8


def test_prompts_carry_the_query_and_nothing_from_a_leaf():
    for transform, template in prompts.PROMPTS.items():
        assert template.count("{query}") == 1
        rendered = prompts.render(transform, "  canaleta de 30x15 mm  ")
        assert "canaleta de 30x15 mm" in rendered
        for leaf_field in ("item_key", "parent_key", "parameters", "gold", "OEB", "OEA"):
            assert leaf_field not in template
    assert set(prompts.MODEL_FOR.values()) <= set(llm.MODELS)


def test_parse_is_deterministic_and_strict():
    assert prompts.parse("hyde", "  Descripción: Canaleta PVC. ") == "Canaleta PVC."
    assert prompts.parse("rewrite", json.dumps({"consulta": "Consulta reescrita: Canaleta"})) == "Canaleta"
    with pytest.raises((ValueError, KeyError)):
        prompts.parse("rewrite", "not json")
    with pytest.raises(ValueError):
        prompts.parse("rewrite", json.dumps({"consulta": ["a"]}))
