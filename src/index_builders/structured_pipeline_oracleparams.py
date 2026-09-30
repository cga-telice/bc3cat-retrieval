# /src/index_builders/structured_pipeline_oracleparams.py
# Proxy module: the oracle-extraction bound (S5) writes the same pseudo-index as the rules
# pipeline; only meta.json.params.stage2_method differs.
from .structured_pipeline_rules import TEXT_FIELD, build, select_field  # noqa: F401
