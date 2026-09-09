# /src/retrievers/structured_pipeline_phi4_twostep.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (model=phi4:latest, prompt_mode=twostep) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
