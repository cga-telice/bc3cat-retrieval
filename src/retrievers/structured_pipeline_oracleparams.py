# /src/retrievers/structured_pipeline_oracleparams.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (stage2_method=oracle_params, the S5 oracle-extraction bound) is in the index
# dir's meta.json.
from .structured_pipeline import load  # noqa: F401
