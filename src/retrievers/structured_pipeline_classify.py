# /src/retrievers/structured_pipeline_classify.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (stage2_prompt_mode=classify) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
