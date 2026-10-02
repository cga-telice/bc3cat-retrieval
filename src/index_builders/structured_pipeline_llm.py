# /src/index_builders/structured_pipeline_llm.py
# Proxy module: the LLM-extraction arm (S9 work item 4) writes the same pseudo-index as the rules
# pipeline; only meta.json.params.stage2_method (and the llm_* params) differ.
from .structured_pipeline_rules import TEXT_FIELD, build, select_field  # noqa: F401
