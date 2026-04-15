# /src/retrievers/structured_pipeline_oracle.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (oracle=true) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
