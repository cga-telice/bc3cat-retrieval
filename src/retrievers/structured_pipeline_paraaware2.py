# /src/retrievers/structured_pipeline_paraaware2.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (stage2_prompt_mode=paraaware2) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
