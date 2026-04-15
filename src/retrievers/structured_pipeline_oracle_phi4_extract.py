# /src/retrievers/structured_pipeline_oracle_phi4_extract.py
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (oracle + model=phi4:latest, prompt_mode=extract) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
