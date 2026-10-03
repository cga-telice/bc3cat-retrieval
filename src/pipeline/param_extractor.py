"""LLM-based parameter extractor (Stage 2) using Ollama.

Ported from `research/structured-retrieval@85c3359` for S9 work item 4 (D-026: file checkout, the
unmodified source is commit `1d27b40` on this branch). Changes against the source, and only these:

- **Every generation goes through S9's client** (`query_rewrite.llm`): the model is pinned by digest,
  the options are the design's (`temperature 0`, `seed`, `num_predict`, `num_ctx`; the source set
  temperature only), and each response is cached append-only, so a run reads back exactly what it
  generated. `ollama_base_url`, `model` and `temperature` are therefore the client's, not arguments.
- **Fail loud.** The source's `_call_ollama` returned `""` on a request error, which the parser then
  read as an unparseable answer and the extractor as "all axes null" — a server outage would have been
  scored as an extraction. It now raises.
- **The retry on a parse failure is kept**, and is a no-op by construction: the same prompt has the
  same cache key, so the retry returns the same response. Under the source's temperature 0 it would
  have returned the same response too, up to GPU non-determinism (S9 A1).
- **Schema.** No OEB default; the caller passes the collection's schema (OE, via the resolver).
- **Imports** are `pipeline.prompts`, this branch's package layout; `prompts.py` is unmodified.
- The `__main__` test harness, which read OEB parquets, is not ported.

The prompt mode S9 uses is `extract` (S9 design, work item 4).

**`key_match`** (S9 A7, post hoc). The source reads each axis with `parsed.get(axis_label)`, exactly, and
`phi4` often names an axis differently ("BANDA_DE_MANTENIMIENTO"), so the value is dropped. `"exact"`, the
default, is the source's behaviour and the registered arm's. `"tolerant"` matches a response key to a schema
axis after case-folding, stripping accents, turning `_` and `-` into spaces and collapsing whitespace; value
validation is unchanged. It applies to the `extract` / `classify` path, the one S9 runs.

Sends a structured Spanish prompt to Llama 3.1 8B via Ollama's REST API,
parses the JSON response into {axis_label: value | None}, which feeds
into Stage 3 (catalog lookup).

Usage::

    python -m src.pipeline.param_extractor
    python -m src.pipeline.param_extractor --base-url http://localhost:11434
    python -m src.pipeline.param_extractor --n-queries 50
"""

import json
import logging
import re
import time
import unicodedata
from pathlib import Path

from query_rewrite.llm import Cache, OllamaClient

from pipeline.prompts import (
    build_extraction_prompt,
    build_classification_prompt,
    build_twostep_extract_prompt,
    build_twostep_match_prompt,
    build_paraaware_extract_prompt,
    build_paraaware_match_prompt,
    build_paraaware2_step1_prompt,
    build_paraaware2_step2_prompt,
)

logger = logging.getLogger(__name__)



class LLMParamExtractor:
    """Extract parameter values from queries using an LLM via Ollama.

    Loads the concept schema, builds structured prompts, calls Ollama,
    and validates responses against allowed schema values.
    """

    def __init__(
        self,
        schema_path: str | Path,
        client: OllamaClient,
        cache: Cache,
        prompt_mode: str = "classify",
        key_match: str = "exact",
    ):
        with open(schema_path, encoding="utf-8") as f:
            self.schema = json.load(f)

        self._client = client
        self._cache = cache
        self.model = client.model
        self._prompt_mode = prompt_mode
        if key_match not in ("exact", "tolerant"):
            raise ValueError(f"key_match={key_match!r}: 'exact' (the source) or 'tolerant' (S9 A7)")
        self._key_match = key_match
        self._paraaware2_step2_fallbacks = 0

        # Pre-build lowercase lookup for value validation
        # {parent_key: {axis_label_lower: {value_lower: value_original}}}
        self._valid_values: dict[str, dict[str, dict[str, str]]] = {}
        for pk, group in self.schema.items():
            self._valid_values[pk] = {}
            for axis_label, values in group["axes"].items():
                self._valid_values[pk][axis_label.strip().lower()] = {
                    v.strip().lower(): v for v in values
                }

    def extract(self, parent_key: str, query: str) -> dict[str, str | None]:
        """Extract parameter values from a query for a given concept group.

        Args:
            parent_key: Concept group key (e.g., "OEB010$")
            query: The user query text

        Returns:
            {axis_label: extracted_value | None} for each axis in the schema.
            Values are returned as-is from the LLM if they match schema values
            (case-insensitive); otherwise set to None.
        """
        if parent_key not in self.schema:
            logger.warning(f"Unknown parent_key: {parent_key}")
            return {}

        group = self.schema[parent_key]
        concept = group["concept"]
        axes = group["axes"]

        if self._prompt_mode == "paraaware2":
            return self._extract_paraaware2(parent_key, concept, axes, query)

        if self._prompt_mode == "paraaware":
            return self._extract_paraaware(parent_key, concept, axes, query)

        if self._prompt_mode == "twostep":
            return self._extract_twostep(parent_key, concept, axes, query)

        if self._prompt_mode == "classify":
            prompt = build_classification_prompt(concept, axes, query)
        else:
            prompt = build_extraction_prompt(concept, axes, query)

        # Call Ollama with retry on parse failure
        raw_response = self._call_ollama(prompt)
        parsed = self._parse_json_response(raw_response)

        if parsed is None:
            # Retry once
            logger.warning(
                f"JSON parse failed for {parent_key}, retrying. "
                f"Raw response: {raw_response!r:.200}"
            )
            raw_response = self._call_ollama(prompt)
            parsed = self._parse_json_response(raw_response)

        if parsed is None:
            # Give up — return all None
            logger.error(
                f"JSON parse failed after retry for {parent_key}. "
                f"Query: {query!r:.100}. Raw: {raw_response!r:.200}"
            )
            return {label: None for label in axes}

        # Validate extracted values against schema
        result = {}
        for axis_label in axes:
            extracted = self._lookup(parsed, axis_label)
            if extracted is None:
                result[axis_label] = None
                continue

            # Case-insensitive validation
            extracted_lower = str(extracted).strip().lower()
            axis_lower = axis_label.strip().lower()
            valid_map = self._valid_values.get(parent_key, {}).get(axis_lower, {})

            if extracted_lower in valid_map:
                # Return the original-case value from schema
                result[axis_label] = valid_map[extracted_lower]
            else:
                logger.warning(
                    f"Unknown value '{extracted}' for axis '{axis_label}' "
                    f"in {parent_key}. Treating as null."
                )
                result[axis_label] = None

        return result

    def extract_batch(
        self, items: list[tuple[str, str]]
    ) -> list[dict[str, str | None]]:
        """Batch extraction for multiple (parent_key, query) pairs.

        Sequential calls to Ollama (no native batch API).
        Reports progress every 10 queries.

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
                    f"{elapsed:.1f}s elapsed, {avg_ms:.0f}ms/query avg"
                )
        return results

    def _extract_twostep(
        self, parent_key: str, concept: str, axes: dict[str, list[str]], query: str
    ) -> dict[str, str | None]:
        """Two-step extraction: free extract then match to schema.

        Step 1: LLM freely describes what each axis value is (no schema shown).
        Step 2: LLM matches Step 1's descriptions to exact schema values.

        Falls back gracefully:
        - Step 1 parse failure after retry -> all None
        - Step 2 parse failure after retry -> attempt direct validation of Step 1 values
        """
        # --- Step 1: Free extraction ---
        step1_prompt = build_twostep_extract_prompt(concept, axes, query)
        step1_raw = self._call_ollama(step1_prompt)
        step1_parsed = self._parse_json_response(step1_raw)

        if step1_parsed is None:
            logger.warning(
                f"Two-step Step 1 parse failed for {parent_key}, retrying. "
                f"Raw: {step1_raw!r:.200}"
            )
            step1_raw = self._call_ollama(step1_prompt)
            step1_parsed = self._parse_json_response(step1_raw)

        if step1_parsed is None:
            logger.error(
                f"Two-step Step 1 failed after retry for {parent_key}. "
                f"Query: {query!r:.100}"
            )
            return {label: None for label in axes}

        # Build extracted dict for Step 2 (use axis labels as keys)
        extracted = {}
        for label in axes:
            val = step1_parsed.get(label)
            if val is None or str(val).strip().lower() in (
                "no especificado", "null", "none", ""
            ):
                extracted[label] = None
            else:
                extracted[label] = str(val).strip()

        # --- Step 2: Match to schema ---
        step2_prompt = build_twostep_match_prompt(concept, axes, extracted)
        step2_raw = self._call_ollama(step2_prompt)
        step2_parsed = self._parse_json_response(step2_raw)

        if step2_parsed is None:
            logger.warning(
                f"Two-step Step 2 parse failed for {parent_key}, retrying. "
                f"Raw: {step2_raw!r:.200}"
            )
            step2_raw = self._call_ollama(step2_prompt)
            step2_parsed = self._parse_json_response(step2_raw)

        if step2_parsed is None:
            # Graceful degradation: try to validate Step 1 values directly
            logger.warning(
                f"Two-step Step 2 failed after retry for {parent_key}. "
                f"Falling back to Step 1 direct validation."
            )
            step2_parsed = extracted

        # --- Validate against schema ---
        result = {}
        for axis_label in axes:
            value = step2_parsed.get(axis_label)
            if value is None:
                result[axis_label] = None
                continue

            value_lower = str(value).strip().lower()
            axis_lower = axis_label.strip().lower()
            valid_map = self._valid_values.get(parent_key, {}).get(axis_lower, {})

            if value_lower in valid_map:
                result[axis_label] = valid_map[value_lower]
            else:
                logger.warning(
                    f"Two-step: unknown value '{value}' for axis '{axis_label}' "
                    f"in {parent_key}. Treating as null."
                )
                result[axis_label] = None

        return result

    def _extract_paraaware(
        self, parent_key: str, concept: str, axes: dict[str, list[str]], query: str
    ) -> dict[str, str | None]:
        """Parameter-aware two-step extraction.

        Step 1: LLM detects whether query contains info about each parameter.
        Step 2: LLM matches only non-null parameters to schema values.

        Key optimization vs twostep: Step 2 only processes axes where Step 1
        found relevant information. If all axes are null, Step 2 is skipped.

        Falls back gracefully:
        - Step 1 parse failure after retry -> all None
        - Step 2 parse failure after retry -> attempt direct validation of Step 1 values
        """
        # --- Step 1: Parameter-aware extraction ---
        step1_prompt = build_paraaware_extract_prompt(concept, axes, query)
        step1_raw = self._call_ollama(step1_prompt)
        step1_parsed = self._parse_json_response(step1_raw)

        if step1_parsed is None:
            logger.warning(
                f"Paraaware Step 1 parse failed for {parent_key}, retrying. "
                f"Raw: {step1_raw!r:.200}"
            )
            step1_raw = self._call_ollama(step1_prompt)
            step1_parsed = self._parse_json_response(step1_raw)

        if step1_parsed is None:
            logger.error(
                f"Paraaware Step 1 failed after retry for {parent_key}. "
                f"Query: {query!r:.100}"
            )
            return {label: None for label in axes}

        # Classify Step 1 results into non-null and null
        non_null_extracted = {}
        null_axes = set()
        for label in axes:
            val = step1_parsed.get(label)
            if val is None or str(val).strip().lower() in (
                "no especificado", "null", "none", ""
            ):
                null_axes.add(label)
            else:
                non_null_extracted[label] = str(val).strip()

        # Optimization: if ALL axes are null, skip Step 2 entirely
        if not non_null_extracted:
            logger.info(
                f"Paraaware: all axes null after Step 1 for {parent_key}, "
                f"skipping Step 2."
            )
            return {label: None for label in axes}

        # --- Step 2: Match only non-null axes to schema ---
        step2_prompt = build_paraaware_match_prompt(concept, axes, non_null_extracted)
        step2_raw = self._call_ollama(step2_prompt)
        step2_parsed = self._parse_json_response(step2_raw)

        if step2_parsed is None:
            logger.warning(
                f"Paraaware Step 2 parse failed for {parent_key}, retrying. "
                f"Raw: {step2_raw!r:.200}"
            )
            step2_raw = self._call_ollama(step2_prompt)
            step2_parsed = self._parse_json_response(step2_raw)

        if step2_parsed is None:
            # Graceful degradation: try to validate Step 1 values directly
            logger.warning(
                f"Paraaware Step 2 failed after retry for {parent_key}. "
                f"Falling back to Step 1 direct validation."
            )
            step2_parsed = non_null_extracted

        # --- Validate against schema (merge with null axes) ---
        result = {}
        for axis_label in axes:
            if axis_label in null_axes:
                result[axis_label] = None
                continue

            value = step2_parsed.get(axis_label)
            if value is None:
                result[axis_label] = None
                continue

            value_lower = str(value).strip().lower()
            axis_lower = axis_label.strip().lower()
            valid_map = self._valid_values.get(parent_key, {}).get(axis_lower, {})

            if value_lower in valid_map:
                result[axis_label] = valid_map[value_lower]
            else:
                logger.warning(
                    f"Paraaware: unknown value '{value}' for axis '{axis_label}' "
                    f"in {parent_key}. Treating as null."
                )
                result[axis_label] = None

        return result

    def _extract_paraaware2(
        self, parent_key: str, concept: str, axes: dict[str, list[str]], query: str
    ) -> dict[str, str | None]:
        """Per-axis detection+classification (paraaware2).

        Makes one LLM call per axis, each showing the full list of possible
        values. The LLM returns a bare value (not JSON), eliminating JSON
        parsing failures entirely.

        If the response is not an exact schema value and not null, a Step 2
        fallback call asks the LLM to match the unexpected text to a schema
        value.

        Args:
            parent_key: Concept group key (e.g., "OEB010$")
            concept: Human-readable concept name
            axes: {axis_label: [possible_values]} from the concept schema
            query: The user query text

        Returns:
            {axis_label: extracted_value | None} for each axis
        """
        result = {}
        for axis_label, values in axes.items():
            # --- Step 1: per-axis detection+classification ---
            prompt = build_paraaware2_step1_prompt(concept, axis_label, values, query)
            raw = self._call_ollama(prompt)
            cleaned = raw.strip().strip('`"\'').strip()

            # Check for null responses
            if cleaned.lower() in ("null", "none", "no especificado", ""):
                result[axis_label] = None
                continue

            # Case-insensitive match against schema values
            axis_lower = axis_label.strip().lower()
            valid_map = self._valid_values.get(parent_key, {}).get(axis_lower, {})
            cleaned_lower = cleaned.lower()

            if cleaned_lower in valid_map:
                result[axis_label] = valid_map[cleaned_lower]
                continue

            # --- Step 2 fallback: unexpected output ---
            self._paraaware2_step2_fallbacks += 1
            logger.info(
                f"Paraaware2 Step 2 fallback for axis '{axis_label}' in "
                f"{parent_key}: unexpected output {cleaned!r:.80}"
            )

            step2_prompt = build_paraaware2_step2_prompt(axis_label, values, cleaned)
            step2_raw = self._call_ollama(step2_prompt)
            step2_cleaned = step2_raw.strip().strip('`"\'').strip()

            if step2_cleaned.lower() in ("null", "none", "no especificado", ""):
                result[axis_label] = None
                continue

            step2_lower = step2_cleaned.lower()
            if step2_lower in valid_map:
                result[axis_label] = valid_map[step2_lower]
            else:
                logger.warning(
                    f"Paraaware2: Step 2 also failed for axis '{axis_label}' in "
                    f"{parent_key}. Step 1: {cleaned!r:.60}, Step 2: {step2_cleaned!r:.60}. "
                    f"Treating as null."
                )
                result[axis_label] = None

        return result

    def _call_ollama(self, prompt: str) -> str:
        """Send a prompt through the cached, pinned client and return the raw response text."""
        return self._cache.get_or_generate(self._client, "extract", prompt)["response"]

    @staticmethod
    def _key(label: str) -> str:
        """A7's tolerant form of an axis name."""
        s = "".join(c for c in unicodedata.normalize("NFD", str(label)) if unicodedata.category(c) != "Mn")
        return re.sub(r"\s+", " ", re.sub(r"[_-]", " ", s.casefold())).strip()

    def _lookup(self, parsed: dict, axis_label: str):
        """The response's value for an axis: exactly, as the source, or under A7's tolerant match."""
        if self._key_match == "exact" or axis_label in parsed:
            return parsed.get(axis_label)
        want = self._key(axis_label)
        hits = [v for k, v in parsed.items() if self._key(k) == want]
        return hits[0] if len(hits) == 1 else None

    @staticmethod
    def _parse_json_response(raw: str) -> dict | None:
        """Parse a JSON object from the LLM response text.

        Handles common LLM quirks:
        - Markdown code fences (```json ... ```)
        - Leading/trailing whitespace
        - Trailing commas (basic cleanup)
        """
        if not raw or not raw.strip():
            return None

        text = raw.strip()

        # Strip markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        text = text.strip()

        # Try parsing as-is
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        # Try removing trailing commas before } or ]
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        return None
