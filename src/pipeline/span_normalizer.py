"""Deterministic span → canonical-value normalizer for the BIO tagger pipeline.

Maps a raw surface span (the substring the BIO tagger emitted) to one of the
canonical values defined in OEB_concept_schema.json for the requested
(parent_key, axis_label). The normalizer never invents a value: if no
canonical value matches under any of the strategies below, it returns None.

Resolution order (first match wins):
  1. Exact case-insensitive match (whitespace collapsed).
  2. Surface-form override map for canonical values that have no literal
     surface form in long text (TIPO DE TERRENO=Normal -> "cualquier clase
     de terreno" / "cualquier tipo de terreno"). This is the inverse of
     data_prep_bio.SURFACE_OVERRIDES.
  3. Axis-specific rules:
     - BANDA DE MANTENIMIENTO: canonicalize operator/quote/spacing variants.
     - Numeric axes (Nº TUBOS, PROFUNDIDAD, DIÁMETRO, DIÁMETROS): strip
       trailing units (mm, m); compare numerically when both sides parse.
  4. Fuzzy match: normalized Levenshtein distance ≤ FUZZY_THRESHOLD (default
     0.15, per protocol §4.4).

The output is bounded by the schema — at most one of the ≤12 canonical values
per (parent_key, axis_label) can be returned. There is no LLM-style
hallucination risk by construction.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "data" / "processed" / "OEB_concept_schema.json"

FUZZY_THRESHOLD = 0.15

# Inverse of data_prep_bio.SURFACE_OVERRIDES. The override fires only when the
# canonical RHS is a valid value for the requested (parent_key, axis_label).
SURFACE_TO_CANONICAL: dict[tuple[str, str], str] = {
    ("TIPO DE TERRENO", "cualquier clase de terreno"): "Normal",
    ("TIPO DE TERRENO", "cualquier tipo de terreno"): "Normal",
}

NUMERIC_AXES = {"Nº TUBOS", "PROFUNDIDAD", "DIÁMETRO", "DIÁMETROS"}

# Tokens stripped from numeric-axis surface text before numeric comparison.
_NUMERIC_UNIT_RE = re.compile(r"\b(mm|cm|m|metros?|milimetros?)\b", re.IGNORECASE)


# ── helpers ─────────────────────────────────────────────────────────────────

def _collapse(text: str) -> str:
    """Lowercase, strip, collapse internal whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _normalize_banda(text: str) -> str:
    """Canonicalize a BANDA DE MANTENIMIENTO surface span.

    Handles operator spacing and stray quote chars so that all of these
    map to a single canonical form:
      i < 3 horas, i<3 horas, i< 3 horas, i  <  3   horas, i < "3" horas
    """
    s = text.lower().strip()
    # Strip stray quote characters around digits/operators
    s = s.replace('"', "").replace("'", "")
    # Normalize operator forms: <= and >= (with optional spaces) into a stable form
    s = re.sub(r"<\s*=", "<=", s)
    s = re.sub(r">\s*=", ">=", s)
    # Add a single space around <, <=, >, >= operators
    s = re.sub(r"\s*(<=|>=|<|>)\s*", r" \1 ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_numeric(text: str) -> str:
    """Strip units and surrounding whitespace; preserve digits/decimals/'."""
    s = text.lower().strip()
    s = _NUMERIC_UNIT_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _try_numeric_equal(a: str, b: str) -> bool:
    """True if both strings parse to the same number (after unit stripping)."""
    aa = _normalize_numeric(a).replace(",", ".")
    bb = _normalize_numeric(b).replace(",", ".")
    try:
        return float(aa) == float(bb)
    except ValueError:
        return False


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(
                min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb))
            )
        prev = curr
    return prev[-1]


def _normalized_lev(a: str, b: str) -> float:
    if not a and not b:
        return 0.0
    longest = max(len(a), len(b))
    return _levenshtein(a, b) / longest if longest else 0.0


# ── normalizer ──────────────────────────────────────────────────────────────

class SpanNormalizer:
    """Maps a BIO-extracted surface span to a canonical schema value."""

    def __init__(
        self,
        schema: dict | str | Path = SCHEMA_PATH,
        fuzzy_threshold: float = FUZZY_THRESHOLD,
    ):
        if isinstance(schema, (str, Path)):
            with open(schema, encoding="utf-8") as f:
                self.schema = json.load(f)
        else:
            self.schema = schema
        self.fuzzy_threshold = fuzzy_threshold

        # Pre-compute lookup tables: {(parent_key, axis): {lower_value: original_value}}
        self._lookup: dict[tuple[str, str], dict[str, str]] = {}
        # Pre-compute BANDA-normalized lookups for that axis
        self._banda_lookup: dict[tuple[str, str], dict[str, str]] = {}
        for pk, info in self.schema.items():
            for axis, values in info.get("axes", {}).items():
                key = (pk, axis)
                self._lookup[key] = {_collapse(v): v for v in values}
                if axis == "BANDA DE MANTENIMIENTO":
                    self._banda_lookup[key] = {
                        _normalize_banda(v): v for v in values
                    }

    # ── public API ──────────────────────────────────────────────────────────

    def normalize(
        self, axis_label: str, surface_text: str, parent_key: str
    ) -> str | None:
        """Map `surface_text` to a canonical value for (parent_key, axis_label).

        Returns the canonical value (original-case schema string) or None.
        """
        if not surface_text:
            return None

        key = (parent_key, axis_label)
        if key not in self._lookup:
            return None

        canonicals = self._lookup[key]
        surface = _collapse(surface_text)

        # 1. Exact match
        if surface in canonicals:
            return canonicals[surface]

        # 2. Surface override
        canon_target = SURFACE_TO_CANONICAL.get((axis_label, surface))
        if canon_target is not None:
            target_lower = canon_target.lower()
            if target_lower in canonicals:
                return canonicals[target_lower]

        # 3. Axis-specific rules
        if axis_label == "BANDA DE MANTENIMIENTO":
            normalized = _normalize_banda(surface_text)
            banda_lookup = self._banda_lookup.get(key, {})
            if normalized in banda_lookup:
                return banda_lookup[normalized]
            # Fallback: BANDA-normalize both sides and compare
            for lower, orig in canonicals.items():
                if _normalize_banda(orig) == normalized:
                    return orig

        if axis_label in NUMERIC_AXES:
            stripped = _normalize_numeric(surface_text)
            if stripped in canonicals:
                return canonicals[stripped]
            for lower, orig in canonicals.items():
                if _try_numeric_equal(surface_text, orig):
                    return orig

        # 4. Fuzzy match (normalized Levenshtein <= threshold)
        best_orig: str | None = None
        best_dist = self.fuzzy_threshold + 1.0
        for lower, orig in canonicals.items():
            dist = _normalized_lev(surface, lower)
            if dist < best_dist:
                best_dist = dist
                best_orig = orig
        if best_dist <= self.fuzzy_threshold:
            return best_orig

        return None

    # ── introspection ───────────────────────────────────────────────────────

    def canonical_values(self, parent_key: str, axis_label: str) -> list[str]:
        """Return the canonical values for a (parent_key, axis_label) pair, or []."""
        key = (parent_key, axis_label)
        return list(self._lookup.get(key, {}).values())
