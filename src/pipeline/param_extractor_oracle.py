"""Oracle-extraction Stage 2: the query record's own parameters (S5, design work item 1).

Not a method. It is the bound on any Stage 2 that reads schema literals (D-010): it hands the
pipeline the values the query record declares, instead of reading them from the query text.
A synthetic query's record carries its **rendered** values — on L1 the rewritten one
(`0.03x0.015 m`, not `30x15 mm`) — so a value is kept only if it is one of the concept's schema
values under the comparison Stage 3 uses with `stage3_value_match: normalized`
(`utils.corpus_prep.normalize_param_string` on both sides). Anything else is an abstention on
that axis, exactly as the rules extractor abstains on a value it cannot find. On `texto` and on
L2/L3 the record carries the gold's own values, so every axis is recovered; on L1 the rewritten
axis abstains.

Same output contract as `RuleBasedParamExtractor.extract`: `{schema axis label: schema value or
None}` over every axis of `parent_key`, schema spelling kept verbatim (BC3 padding included).
The record is a row's `parameters_norm`, `{axis letter: None | {"label", "values": [{"value",
…}]}}`, identical in shape on the corpus and on the synthetic query tables.

If Stage 1 picked another concept, the record's labels are matched against *that* concept's
axes: a label it does not have contributes nothing, as a rules extractor reading the wrong
schema would find nothing. That keeps Stage 1 realistic, as the design requires.
"""

from __future__ import annotations

import json
from pathlib import Path

from utils.corpus_prep import normalize_param_string


class OracleParamsExtractor:
    """Stage 2 from the query record's declared parameters, restricted to schema values."""

    def __init__(self, schema_path: str | Path):
        with open(schema_path, encoding="utf-8") as f:
            self._schema = json.load(f)
        # parent → normalised label → (schema label, {normalised value → schema value})
        self._axes: dict[str, dict[str, tuple[str, dict[str, str]]]] = {}
        for pk, entry in self._schema.items():
            axes = {}
            for label, values in entry["axes"].items():
                table = {}
                for v in values:
                    nv = normalize_param_string(v)
                    if nv in table and table[nv] != v:
                        raise ValueError(
                            f"{pk}/{label!r}: schema values {table[nv]!r} and {v!r} normalise alike"
                        )
                    table[nv] = v
                axes[normalize_param_string(label)] = (label, table)
            self._axes[pk] = axes

    def extract(self, parent_key: str, record: dict | None) -> dict[str, str | None]:
        if parent_key not in self._axes:
            return {}
        axes = self._axes[parent_key]
        out: dict[str, str | None] = {label: None for label, _ in axes.values()}
        if record is None:
            raise ValueError("oracle extraction needs the query record's parameters_norm")
        for axis in record.values():
            if axis is None:
                continue
            values = list(axis["values"])
            if len(values) != 1:
                raise ValueError(f"axis {axis['label']!r} carries {len(values)} values; expected 1")
            hit = axes.get(normalize_param_string(axis["label"]))
            if hit is None:
                continue
            label, table = hit
            out[label] = table.get(normalize_param_string(values[0]["value"]))
        return out
