# /src/retrievers/structured_pipeline_paraaware.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (stage2_prompt_mode=paraaware) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
