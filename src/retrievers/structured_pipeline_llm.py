# /src/retrievers/structured_pipeline_llm.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (stage2_method=llm) is in the index dir's meta.json (S9 work item 4).
from .structured_pipeline import load  # noqa: F401
