"""Rule-based parameter extractor (Stage 2 baseline).

Pure string-matching baseline to quantify LLM value-add.
Matches LLMParamExtractor interface for side-by-side comparison.

Ported from `research/structured-retrieval@85c3359` (D-026). Changes against the source:
the default `OEB_concept_schema.json` path is gone — the schema path is required and comes
from the resolver (D-022); `normalize_text` is imported as `utils.text_processing`, the name
under which `src/` sits on `sys.path` here; and the module's test/comparison CLI (source
lines 258–841), which imports the LLM extractor and reads OEB parquets, is not ported — the
LLM variants belong to S5. Extraction logic is unchanged.
"""

import json
import logging
import re
import time
from pathlib import Path

from utils.text_processing import normalize_text

logger = logging.getLogger(__name__)


# Context regex patterns for Nº TUBOS matching (applied to raw query)
_TUBOS_PATTERNS = [
    re.compile(r"(\d+\s+o\s+\d+)\s+t(?:ubo|,)", re.IGNORECASE),  # "1 o 2 tubos"
    re.compile(r"(\d+)\s+t(?:ubo|,)", re.IGNORECASE),             # "3 T," or "3 tubos"
    re.compile(r"de\s+(\d+)\s+tubo", re.IGNORECASE),              # "de 2 tubos"
    re.compile(r"con\s+(\d+)\s+tubo", re.IGNORECASE),             # "con 1 tubos"
]


def _normalize_str(text: str) -> str:
    """Normalize text to a single lowercase, accent-stripped string."""
    return " ".join(normalize_text(text))


class RuleBasedParamExtractor:
    """Extract parameter values from queries using string matching.

    Two matching strategies:
    1. Text: normalized substring matching with longest-match-wins
    2. Numeric: context-keyword matching for axes with short digit values

    Interface matches LLMParamExtractor for drop-in replacement.
    """

    def __init__(self, schema_path: str | Path):
        with open(schema_path, encoding="utf-8") as f:
            self.schema = json.load(f)

        # Build match tables and classify axes
        # {pk: {axis: [(norm_value, original_value), ...]}} sorted longest-first
        self._match_table: dict[str, dict[str, list[tuple[str, str]]]] = {}
        # {pk: {axis: "text" | "numeric"}}
        self._axis_type: dict[str, dict[str, str]] = {}

        for pk, group in self.schema.items():
            self._match_table[pk] = {}
            self._axis_type[pk] = {}
            for axis_label, values in group["axes"].items():
                # Build normalized value table (sorted longest-first)
                entries = []
                for v in values:
                    norm_v = _normalize_str(v)
                    entries.append((norm_v, v))
                entries.sort(key=lambda x: len(x[0]), reverse=True)
                self._match_table[pk][axis_label] = entries

                # Classify axis: "numeric" if any value normalizes to <=2 chars
                has_short = any(len(nv) <= 2 for nv, _ in entries)
                self._axis_type[pk][axis_label] = (
                    "numeric" if has_short else "text"
                )

    def extract(self, parent_key: str, query: str) -> dict[str, str | None]:
        """Extract parameter values from a query using string matching.

        Args:
            parent_key: Concept group key (e.g., "OEA010$")
            query: The user query text

        Returns:
            {axis_label: extracted_value | None} for each axis in the schema.
        """
        if parent_key not in self.schema:
            logger.warning(f"Unknown parent_key: {parent_key}")
            return {}

        axes = self.schema[parent_key]["axes"]
        query_norm = _normalize_str(query)

        result = {}
        for axis_label in axes:
            atype = self._axis_type[parent_key][axis_label]
            if atype == "numeric":
                result[axis_label] = self._match_numeric(
                    query, query_norm, parent_key, axis_label
                )
            else:
                result[axis_label] = self._match_text(
                    query_norm, parent_key, axis_label
                )
        return result

    def extract_batch(
        self, items: list[tuple[str, str]]
    ) -> list[dict[str, str | None]]:
        """Batch extraction for multiple (parent_key, query) pairs.

        Args:
            items: List of (parent_key, query) tuples

        Returns:
            List of extraction results, one per input item
        """
        results = []
        t0 = time.time()
        for i, (parent_key, query) in enumerate(items):
            result = self.extract(parent_key, query)
            results.append(result)
            if (i + 1) % 10 == 0 or (i + 1) == len(items):
                elapsed = time.time() - t0
                avg_ms = (elapsed / (i + 1)) * 1000
                print(
                    f"  [{i + 1}/{len(items)}] "
                    f"{elapsed:.3f}s elapsed, {avg_ms:.3f}ms/query avg"
                )
        return results

    def _match_text(
        self, query_norm: str, parent_key: str, axis_label: str
    ) -> str | None:
        """Normalized substring matching with longest-match-wins.

        Finds all schema values whose normalized form is a substring of the
        normalized query. Applies subsumption filtering: if a shorter match
        is a substring of a longer match, discard the shorter one. Returns
        the value if exactly one match survives; None otherwise.
        """
        entries = self._match_table[parent_key][axis_label]
        matches = []
        for norm_val, orig_val in entries:
            if norm_val and norm_val in query_norm:
                matches.append((norm_val, orig_val))

        if not matches:
            return None

        # Subsumption: remove matches that are substrings of longer matches
        filtered = []
        for norm_a, orig_a in matches:
            subsumed = any(
                norm_a != norm_b and norm_a in norm_b
                for norm_b, _ in matches
            )
            if not subsumed:
                filtered.append((norm_a, orig_a))

        if len(filtered) == 1:
            return filtered[0][1]  # Return original-case value

        # Ambiguous or no unique match
        if len(filtered) > 1:
            logger.debug(
                f"Ambiguous match for axis '{axis_label}' in {parent_key}: "
                f"{[o for _, o in filtered]}"
            )
        return None

    def _match_numeric(
        self,
        query_raw: str,
        query_norm: str,
        parent_key: str,
        axis_label: str,
    ) -> str | None:
        """Context-aware numeric matching for axes with short digit values.

        Strategy:
        1. Try matching original values (with units) in raw query
        2. Try multi-word values via normalized substring
        3. Use context regex patterns for bare single/double-digit values
        """
        entries = self._match_table[parent_key][axis_label]
        query_lower = query_raw.lower()

        # Build set of allowed values for validation
        values_set = {orig for _, orig in entries}

        # --- Strategy 1: Match original values with units in raw query ---
        # Handles: 2", 3", 1'', 2'', 3 1/2'', 21mm, etc.
        raw_matches = []
        for _norm_val, orig_val in entries:
            if not orig_val.strip().isdigit():  # Has non-digit chars (units)
                if orig_val.lower() in query_lower:
                    raw_matches.append(orig_val)

        if len(raw_matches) == 1:
            return raw_matches[0]
        if len(raw_matches) > 1:
            # Multiple unit-values matched; pick longest
            raw_matches.sort(key=len, reverse=True)
            # Check subsumption
            filtered = [
                m for m in raw_matches
                if not any(
                    m.lower() != o.lower() and m.lower() in o.lower()
                    for o in raw_matches
                )
            ]
            if len(filtered) == 1:
                return filtered[0]
            return None  # Ambiguous

        # --- Strategy 2: Multi-word normalized values ---
        # Handles: "1 o 2" etc.
        multi_word_matches = []
        for norm_val, orig_val in entries:
            if " " in norm_val and norm_val in query_norm:
                multi_word_matches.append((norm_val, orig_val))
        if len(multi_word_matches) == 1:
            return multi_word_matches[0][1]

        # --- Strategy 3: Context regex for bare digit values ---
        # Detect axis type from label for context patterns
        label_upper = axis_label.strip().upper()
        is_tubos = "TUBO" in label_upper and "DIÁM" not in label_upper

        if is_tubos:
            for pattern in _TUBOS_PATTERNS:
                m = pattern.search(query_raw)
                if m:
                    captured = m.group(1).strip()
                    if captured in values_set:
                        return captured
                    # Try normalized comparison
                    cap_norm = _normalize_str(captured)
                    for nv, ov in entries:
                        if cap_norm == nv:
                            return ov

        return None
