# /src/retrievers/structured_pipeline_classifier.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (stage2_method=classifier) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
