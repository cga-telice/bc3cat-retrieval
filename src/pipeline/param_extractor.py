"""LLM-based parameter extractor (Stage 2) using Ollama.

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
from pathlib import Path

import requests

from src.pipeline.prompts import (
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

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data" / "processed"
SCHEMA_PATH = DATA_DIR / "OEB_concept_schema.json"


class LLMParamExtractor:
    """Extract parameter values from queries using an LLM via Ollama.

    Loads the concept schema, builds structured prompts, calls Ollama,
    and validates responses against allowed schema values.
    """

    def __init__(
        self,
        schema_path: str | Path = SCHEMA_PATH,
        ollama_base_url: str = "http://ollama:11434",
        model: str = "llama3.1:8b",
        temperature: float = 0.0,
        prompt_mode: str = "classify",
    ):
        with open(schema_path, encoding="utf-8") as f:
            self.schema = json.load(f)

        self.base_url = ollama_base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self._prompt_mode = prompt_mode
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
            extracted = parsed.get(axis_label)
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
        """Send a prompt to Ollama and return the raw response text."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except requests.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            return ""

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


# ---------------------------------------------------------------------------
# Tests (run with: python -m src.pipeline.param_extractor)
# ---------------------------------------------------------------------------

def _get_ground_truth(row) -> dict[str, str]:
    """Extract ground-truth axis values from a parquet row's parameters."""
    params = row["parameters"]
    gt = {}
    for axis_key, axis_data in params.items():
        if axis_data is None:
            continue
        label = axis_data["label"].strip()
        value = axis_data["values"][0]["value"].strip()
        gt[label] = value
    return gt


def _run_tests(base_url: str, n_queries: int = 20):
    """Run connectivity, single extraction, and batch tests."""
    import pandas as pd

    print("=" * 60)
    print("LLM Parameter Extractor — Tests")
    print("=" * 60)

    # --- T1: Connectivity ---
    print("\n[T1] Connectivity check...")
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=10)
        resp.raise_for_status()
        tags = resp.json()
        models = [m["name"] for m in tags.get("models", [])]
        print(f"  Ollama reachable at {base_url}")
        print(f"  Models available: {models}")
        if not any("llama3.1" in m for m in models):
            print("  WARNING: llama3.1:8b not found! Pull it first.")
            return
        print("  PASS")
    except requests.RequestException as e:
        print(f"  FAIL: Cannot reach Ollama at {base_url}: {e}")
        print("  Make sure Ollama is running and the model is pulled.")
        return

    # --- Load extractor and data ---
    extractor = LLMParamExtractor(
        ollama_base_url=base_url, model="llama3.1:8b"
    )
    print(f"  Prompt mode: {extractor._prompt_mode}")

    queries_path = DATA_DIR / "OEB_short_norm.parquet"
    df = pd.read_parquet(queries_path)
    df = df[df["parent_key"].str.endswith("$")]

    # --- T2: Single extraction ---
    print("\n[T2] Single extraction test...")
    # Pick a query from a small group for quick testing
    row = df[df["parent_key"] == "OEB010$"].iloc[0]
    query_text = row["text"]
    parent_key = row["parent_key"]
    gt = _get_ground_truth(row)

    print(f"  Query: {query_text!r:.120}")
    print(f"  Concept group: {parent_key}")
    print(f"  Ground truth: {gt}")

    t0 = time.time()
    extracted = extractor.extract(parent_key, query_text)
    elapsed_ms = (time.time() - t0) * 1000

    print(f"  Extracted:     {extracted}")
    print(f"  Time: {elapsed_ms:.0f}ms")

    # Compare
    axes_correct = 0
    axes_total = len(gt)
    for axis, gt_val in gt.items():
        ext_val = extracted.get(axis)
        match = (
            ext_val is not None
            and ext_val.strip().lower() == gt_val.strip().lower()
        )
        if match:
            axes_correct += 1
        else:
            print(f"  MISMATCH axis '{axis}': expected '{gt_val}', got '{ext_val}'")

    print(f"  Axes correct: {axes_correct}/{axes_total}")
    print(f"  {'PASS' if axes_correct == axes_total else 'PARTIAL'}")

    # --- T3: Batch of N queries ---
    print(f"\n[T3] Batch extraction test ({n_queries} queries)...")

    # Sample from different concept groups
    sample = df.groupby("parent_key", group_keys=False).apply(
        lambda x: x.sample(n=min(1, len(x)), random_state=42)
    )
    if len(sample) < n_queries:
        extra = df[~df.index.isin(sample.index)].sample(
            n=min(n_queries - len(sample), len(df) - len(sample)),
            random_state=42,
        )
        sample = pd.concat([sample, extra])
    sample = sample.head(n_queries)

    items = list(zip(sample["parent_key"], sample["text"]))

    t0 = time.time()
    results = extractor.extract_batch(items)
    total_elapsed = time.time() - t0

    # Evaluate
    total_axes = 0
    correct_axes = 0
    queries_all_correct = 0

    print(f"\n  {'#':>3}  {'parent':>8}  {'axes_ok':>7}  result")
    print(f"  {'---':>3}  {'--------':>8}  {'-------':>7}  ------")

    for i, (idx, row) in enumerate(sample.iterrows()):
        gt = _get_ground_truth(row)
        extracted = results[i]
        q_correct = 0
        q_total = len(gt)

        for axis, gt_val in gt.items():
            total_axes += 1
            ext_val = extracted.get(axis)
            if (
                ext_val is not None
                and ext_val.strip().lower() == gt_val.strip().lower()
            ):
                correct_axes += 1
                q_correct += 1

        all_ok = q_correct == q_total
        if all_ok:
            queries_all_correct += 1

        status = "OK" if all_ok else f"{q_correct}/{q_total}"
        print(f"  {i + 1:>3}  {row['parent_key']:>8}  {status:>7}  {extracted}")

    avg_ms = (total_elapsed / len(items)) * 1000

    print(f"\n  Summary:")
    print(f"    Per-axis accuracy:  {correct_axes}/{total_axes} = {correct_axes / total_axes:.1%}")
    print(f"    Per-query accuracy: {queries_all_correct}/{len(items)} = {queries_all_correct / len(items):.1%}")
    print(f"    Total time: {total_elapsed:.1f}s")
    print(f"    Avg time/query: {avg_ms:.0f}ms")

    # --- T4: Edge case — malformed response ---
    print("\n[T4] Edge case: JSON parsing robustness...")
    test_cases = [
        ('```json\n{"A": "x"}\n```', {"A": "x"}),
        ('{"A": "x",}', {"A": "x"}),
        ("  {  } ", {}),
        ("not json at all", None),
        ("", None),
    ]
    for raw, expected in test_cases:
        result = LLMParamExtractor._parse_json_response(raw)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status}: parse({raw!r:.40}) -> {result}")

    print("\n" + "=" * 60)
    print("Tests complete.")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="LLM Parameter Extractor (Stage 2) — Tests"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama base URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--n-queries",
        type=int,
        default=20,
        help="Number of queries for batch test (default: 20)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    _run_tests(base_url=args.base_url, n_queries=args.n_queries)
