"""S9 work item 4: the LLM extractor ported from `research/structured-retrieval@85c3359`, without a server.

The port may change only what its docstring lists. Pinned here: the prompt is the source's own
(`prompts.py` unmodified), every call goes through the cached client, a request error raises instead of
being read as "all axes null", the retry is served from the cache, and an answer outside the schema is
null as in the source. The arm's config differs from `rules_valuenorm`'s only in Stage 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests
import yaml

from pipeline import param_extractor as pe
from pipeline import prompts
from query_rewrite import llm

REPO = Path(__file__).resolve().parents[1]
SCHEMA = {"OEA010$": {"concept": "CANALETA PVC", "axes": {"DIMENSIONES": ["30x15 mm", "40x25 mm"],
                                                           "TRABAJO": ["Diurno", "Nocturno"]},
                      "item_keys": [], "num_items": 0}}


class FakeClient:
    model = "phi4:latest"
    digest = "ac896e5b8b34" + "0" * 52
    options = dict(llm.OPTIONS)

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def key(self, prompt, fmt=None):
        return llm.sha256_text(json.dumps([self.digest, self.options, fmt, prompt]))

    def generate(self, prompt, fmt=None):
        self.prompts.append(prompt)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return {"response": r, "done_reason": "stop", "eval_count": 1, "prompt_eval_count": 1, "seconds": 0.0}


@pytest.fixture
def schema_path(tmp_path):
    p = tmp_path / "schema.json"
    p.write_text(json.dumps(SCHEMA, ensure_ascii=False), encoding="utf-8")
    return p


def make(schema_path, tmp_path, responses):
    client = FakeClient(responses)
    return pe.LLMParamExtractor(schema_path, client, llm.Cache(tmp_path / "c.jsonl"), prompt_mode="extract"), client


def test_extract_uses_the_source_prompt_and_validates_against_the_schema(schema_path, tmp_path):
    ex, client = make(schema_path, tmp_path, ['{"DIMENSIONES": "30X15 MM", "TRABAJO": "Vespertino"}'])
    got = ex.extract("OEA010$", "canaleta de 30x15 mm")
    assert got == {"DIMENSIONES": "30x15 mm", "TRABAJO": None}
    assert client.prompts == [prompts.build_extraction_prompt("CANALETA PVC", SCHEMA["OEA010$"]["axes"],
                                                              "canaleta de 30x15 mm")]


def test_retry_on_a_parse_failure_is_served_by_the_cache(schema_path, tmp_path):
    ex, client = make(schema_path, tmp_path, ["no json here"])
    assert ex.extract("OEA010$", "q") == {"DIMENSIONES": None, "TRABAJO": None}
    assert len(client.prompts) == 1


def test_a_request_error_raises_instead_of_reading_as_null(schema_path, tmp_path):
    ex, _ = make(schema_path, tmp_path, [requests.ConnectionError("down")])
    with pytest.raises(requests.ConnectionError):
        ex.extract("OEA010$", "q")


def test_the_port_keeps_the_source_prompts_unmodified():
    import subprocess
    source = subprocess.run(["git", "show", "85c3359:src/pipeline/prompts.py"], cwd=REPO,
                            capture_output=True, text=True, encoding="utf-8")
    if source.returncode != 0:
        pytest.skip("research/structured-retrieval@85c3359 not in this clone")
    here = (REPO / "src" / "pipeline" / "prompts.py").read_text(encoding="utf-8")
    assert here.replace("\r\n", "\n") == source.stdout.replace("\r\n", "\n")


def test_llm_arm_differs_from_rules_only_in_stage2():
    rules = yaml.safe_load((REPO / "configs" / "structured_pipeline_rules_valuenorm__OE.yaml").read_text(encoding="utf-8"))
    arm = yaml.safe_load((REPO / "configs" / "structured_pipeline_llm_valuenorm__OE.yaml").read_text(encoding="utf-8"))
    p = arm["method"]["params"]
    assert (p.pop("stage2_method"), p.pop("llm_model"), p.pop("llm_prompt_mode")) == ("llm", "phi4:latest", "extract")
    assert rules["method"]["params"].pop("stage2_method") == "rules"
    assert p == rules["method"]["params"]
    assert arm["retriever"]["module"] == "src.retrievers.structured_pipeline_llm"
    for key in ("collection", "paths", "inputs", "io"):
        assert arm[key] == rules[key]


def test_pipeline_fixes_model_and_mode():
    from retrievers import structured_pipeline as sp
    assert "llm" in sp.STAGE2_METHODS
    assert (sp.LLM_MODEL, sp.LLM_PROMPT_MODE) == ("phi4:latest", "extract")
    assert sp.LLM_MODEL in llm.MODELS
