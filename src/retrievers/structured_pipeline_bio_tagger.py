# /src/retrievers/structured_pipeline_bio_tagger.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (stage2_method=bio_tagger) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
