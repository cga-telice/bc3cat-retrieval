"""Rule-based parameter extractor (Stage 2 baseline).

Pure string-matching baseline to quantify LLM value-add.
Matches LLMParamExtractor interface for side-by-side comparison.

Usage::

    python -m src.pipeline.param_extractor_rules
    python -m src.pipeline.param_extractor_rules --n-queries 50
    python -m src.pipeline.param_extractor_rules --skip-llm
    python -m src.pipeline.param_extractor_rules --classify  # three-way comparison
    python -m src.pipeline.param_extractor_rules --classify --twostep --paraaware  # five-way
    python -m src.pipeline.param_extractor_rules --paraaware2  # paraaware2 comparison
    python -m src.pipeline.param_extractor_rules --classify --model phi4:latest  # Phi-4 comparison
"""

import json
import logging
import re
import time
from pathlib import Path

from src.utils.text_processing import normalize_text

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data" / "processed"
SCHEMA_PATH = DATA_DIR / "OEB_concept_schema.json"

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

    def __init__(self, schema_path: str | Path = SCHEMA_PATH):
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
            parent_key: Concept group key (e.g., "OEB010$")
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


# ---------------------------------------------------------------------------
# Tests (run with: python -m src.pipeline.param_extractor_rules)
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


def _get_sample(df, n_queries: int = 20):
    """Get the same sample of queries used in Sprint 04's T3 test.

    Uses identical sampling logic: stratified by parent_key with
    random_state=42, then fill to n_queries.
    """
    sample = df.groupby("parent_key", group_keys=False).apply(
        lambda x: x.sample(n=min(1, len(x)), random_state=42)
    )
    if len(sample) < n_queries:
        extra = df[~df.index.isin(sample.index)].sample(
            n=min(n_queries - len(sample), len(df) - len(sample)),
            random_state=42,
        )
        import pandas as pd
        sample = pd.concat([sample, extra])
    sample = sample.head(n_queries)
    return sample


def _run_tests(n_queries: int = 20, base_url: str = "http://localhost:11434",
               skip_llm: bool = False, classify: bool = False,
               twostep: bool = False, paraaware: bool = False,
               paraaware2: bool = False,
               model: str = "llama3.1:8b"):
    """Run rule-based extraction tests and optional LLM comparison."""
    import pandas as pd

    print("=" * 70)
    print("Rule-Based Parameter Extractor — Tests")
    print("=" * 70)

    # --- Load extractor and data ---
    extractor = RuleBasedParamExtractor()

    queries_path = DATA_DIR / "OEB_short_norm.parquet"
    df = pd.read_parquet(queries_path)
    df = df[df["parent_key"].str.endswith("$")]

    # --- T1: Single extraction ---
    print("\n[T1] Single extraction test...")
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
    print(f"  Time: {elapsed_ms:.3f}ms")

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
            print(
                f"  MISMATCH axis '{axis}': "
                f"expected '{gt_val}', got '{ext_val}'"
            )

    print(f"  Axes correct: {axes_correct}/{axes_total}")
    print(f"  {'PASS' if axes_correct == axes_total else 'PARTIAL'}")

    # --- T2: Batch of N queries ---
    print(f"\n[T2] Batch extraction test ({n_queries} queries)...")
    sample = _get_sample(df, n_queries)
    items = list(zip(sample["parent_key"], sample["text"]))

    t0 = time.time()
    rule_results = extractor.extract_batch(items)
    rule_elapsed = time.time() - t0

    # Evaluate rule-based
    total_axes = 0
    correct_axes = 0
    queries_all_correct = 0

    print(f"\n  {'#':>3}  {'parent':>8}  {'axes_ok':>7}  result")
    print(f"  {'---':>3}  {'--------':>8}  {'-------':>7}  ------")

    for i, (idx, row) in enumerate(sample.iterrows()):
        gt = _get_ground_truth(row)
        extracted = rule_results[i]
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
        print(
            f"  {i + 1:>3}  {row['parent_key']:>8}  {status:>7}  "
            f"{extracted}"
        )

    rule_avg_ms = (rule_elapsed / len(items)) * 1000

    print(f"\n  Rule-Based Summary:")
    print(
        f"    Per-axis accuracy:  {correct_axes}/{total_axes} "
        f"= {correct_axes / total_axes:.1%}"
    )
    print(
        f"    Per-query accuracy: {queries_all_correct}/{len(items)} "
        f"= {queries_all_correct / len(items):.1%}"
    )
    print(f"    Total time: {rule_elapsed:.3f}s")
    print(f"    Avg time/query: {rule_avg_ms:.3f}ms")

    # --- T3: Side-by-side comparison with LLM ---
    llm_extract_results = None
    llm_extract_elapsed = None
    llm_classify_results = None
    llm_classify_elapsed = None
    llm_twostep_results = None
    llm_twostep_elapsed = None
    llm_paraaware_results = None
    llm_paraaware_elapsed = None
    llm_paraaware2_results = None
    llm_paraaware2_elapsed = None
    llm_pa2_extractor = None  # keep reference for fallback counter

    if not skip_llm:
        print(f"\n[T3] Side-by-side comparison with LLM extractor...")
        import requests
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            model_base = model.split(":")[0]  # e.g., "llama3.1" or "phi4"
            if not any(model_base in m for m in models):
                print(f"  LLM comparison skipped: {model} not available.")
                skip_llm = True
            else:
                from src.pipeline.param_extractor import LLMParamExtractor

                # LLM-extract (original prompt)
                print(f"  Ollama reachable, running LLM extraction (mode=extract, model={model})...")
                llm_ext = LLMParamExtractor(
                    ollama_base_url=base_url, model=model,
                    prompt_mode="extract",
                )
                t0 = time.time()
                llm_extract_results = llm_ext.extract_batch(items)
                llm_extract_elapsed = time.time() - t0

                # LLM-classify -- only if --classify flag
                if classify:
                    print(f"  Running LLM extraction (mode=classify, model={model})...")
                    llm_cls = LLMParamExtractor(
                        ollama_base_url=base_url, model=model,
                        prompt_mode="classify",
                    )
                    t0 = time.time()
                    llm_classify_results = llm_cls.extract_batch(items)
                    llm_classify_elapsed = time.time() - t0

                # LLM-twostep -- only if --twostep flag
                if twostep:
                    print(f"  Running LLM extraction (mode=twostep, model={model})...")
                    llm_ts = LLMParamExtractor(
                        ollama_base_url=base_url, model=model,
                        prompt_mode="twostep",
                    )
                    t0 = time.time()
                    llm_twostep_results = llm_ts.extract_batch(items)
                    llm_twostep_elapsed = time.time() - t0

                # LLM-paraaware -- only if --paraaware flag
                if paraaware:
                    print(f"  Running LLM extraction (mode=paraaware, model={model})...")
                    llm_pa = LLMParamExtractor(
                        ollama_base_url=base_url, model=model,
                        prompt_mode="paraaware",
                    )
                    t0 = time.time()
                    llm_paraaware_results = llm_pa.extract_batch(items)
                    llm_paraaware_elapsed = time.time() - t0

                # LLM-paraaware2 -- only if --paraaware2 flag
                if paraaware2:
                    print(f"  Running LLM extraction (mode=paraaware2, model={model})...")
                    llm_pa2 = LLMParamExtractor(
                        ollama_base_url=base_url, model=model,
                        prompt_mode="paraaware2",
                    )
                    llm_pa2_extractor = llm_pa2
                    t0 = time.time()
                    llm_paraaware2_results = llm_pa2.extract_batch(items)
                    llm_paraaware2_elapsed = time.time() - t0
        except Exception as e:
            print(f"  LLM comparison skipped: {e}")
            skip_llm = True

    if not skip_llm and llm_extract_results is not None:
        has_classify = llm_classify_results is not None
        has_twostep = llm_twostep_results is not None
        has_paraaware = llm_paraaware_results is not None
        has_paraaware2 = llm_paraaware2_results is not None

        # Print side-by-side comparison header
        header = (f"  {'#':>3}  {'parent':>8}  {'axis':<30}  "
                  f"{'ground_truth':<20}  {'rule':<20}  {'llm-extract':<20}")
        sep = (f"  {'---':>3}  {'--------':>8}  {'-'*30}  "
               f"{'-'*20}  {'-'*20}  {'-'*20}")
        if has_classify:
            header += f"  {'llm-classify':<20}"
            sep += f"  {'-'*20}"
        if has_twostep:
            header += f"  {'llm-twostep':<20}"
            sep += f"  {'-'*20}"
        if has_paraaware:
            header += f"  {'llm-paraaware':<20}"
            sep += f"  {'-'*20}"
        if has_paraaware2:
            header += f"  {'llm-paraaware2':<20}"
            sep += f"  {'-'*20}"
        print(f"\n{header}")
        print(sep)

        # Counters
        llm_ext_total = 0
        llm_ext_correct = 0
        llm_ext_q_all_correct = 0
        llm_ext_norm_errors = 0

        llm_cls_total = 0
        llm_cls_correct = 0
        llm_cls_q_all_correct = 0
        llm_cls_norm_errors = 0

        llm_ts_total = 0
        llm_ts_correct = 0
        llm_ts_q_all_correct = 0
        llm_ts_norm_errors = 0

        llm_pa_total = 0
        llm_pa_correct = 0
        llm_pa_q_all_correct = 0
        llm_pa_norm_errors = 0

        llm_pa2_total = 0
        llm_pa2_correct = 0
        llm_pa2_q_all_correct = 0
        llm_pa2_norm_errors = 0

        # Build valid-values lookup for normalization error counting
        schema = extractor.schema
        valid_values_lower = {}  # {pk: {axis_lower: set(value_lower)}}
        for pk, group in schema.items():
            valid_values_lower[pk] = {}
            for axis_label, values in group["axes"].items():
                valid_values_lower[pk][axis_label.strip().lower()] = {
                    v.strip().lower() for v in values
                }

        for i, (idx, row) in enumerate(sample.iterrows()):
            gt = _get_ground_truth(row)
            rule_ext = rule_results[i]
            ext_result = llm_extract_results[i]
            cls_result = llm_classify_results[i] if has_classify else {}
            ts_result = llm_twostep_results[i] if has_twostep else {}
            pa_result = llm_paraaware_results[i] if has_paraaware else {}
            pa2_result = llm_paraaware2_results[i] if has_paraaware2 else {}
            pk = row["parent_key"]

            llm_ext_q_ok = 0
            llm_cls_q_ok = 0
            llm_ts_q_ok = 0
            llm_pa_q_ok = 0
            llm_pa2_q_ok = 0

            for axis, gt_val in gt.items():
                rule_val = rule_ext.get(axis)
                ext_val = ext_result.get(axis)
                cls_val = cls_result.get(axis) if has_classify else None
                ts_val = ts_result.get(axis) if has_twostep else None
                pa_val = pa_result.get(axis) if has_paraaware else None
                pa2_val = pa2_result.get(axis) if has_paraaware2 else None

                rule_ok = (
                    rule_val is not None
                    and rule_val.strip().lower() == gt_val.strip().lower()
                )
                ext_ok = (
                    ext_val is not None
                    and ext_val.strip().lower() == gt_val.strip().lower()
                )

                llm_ext_total += 1
                if ext_ok:
                    llm_ext_correct += 1
                    llm_ext_q_ok += 1

                # Count normalization errors for LLM-extract:
                # LLM returned None when GT has a value -> potential norm error
                if ext_val is None and gt_val is not None:
                    axis_lower = axis.strip().lower()
                    valid_set = valid_values_lower.get(pk, {}).get(axis_lower, set())
                    if valid_set:
                        llm_ext_norm_errors += 1

                # Markers
                rule_mark = "+" if rule_ok else "-"
                ext_mark = "+" if ext_ok else "-"
                r_display = f"{rule_mark} {rule_val}" if rule_val else "- None"
                e_display = f"{ext_mark} {ext_val}" if ext_val else "- None"

                line = (
                    f"  {i + 1:>3}  {row['parent_key']:>8}  "
                    f"{axis:<30}  {gt_val:<20}  {r_display:<20}  "
                    f"{e_display:<20}"
                )

                if has_classify:
                    cls_ok = (
                        cls_val is not None
                        and cls_val.strip().lower() == gt_val.strip().lower()
                    )
                    llm_cls_total += 1
                    if cls_ok:
                        llm_cls_correct += 1
                        llm_cls_q_ok += 1

                    if cls_val is None and gt_val is not None:
                        axis_lower = axis.strip().lower()
                        valid_set = valid_values_lower.get(pk, {}).get(axis_lower, set())
                        if valid_set:
                            llm_cls_norm_errors += 1

                    cls_mark = "+" if cls_ok else "-"
                    c_display = f"{cls_mark} {cls_val}" if cls_val else "- None"
                    line += f"  {c_display:<20}"

                if has_twostep:
                    ts_ok = (
                        ts_val is not None
                        and ts_val.strip().lower() == gt_val.strip().lower()
                    )
                    llm_ts_total += 1
                    if ts_ok:
                        llm_ts_correct += 1
                        llm_ts_q_ok += 1

                    if ts_val is None and gt_val is not None:
                        axis_lower = axis.strip().lower()
                        valid_set = valid_values_lower.get(pk, {}).get(axis_lower, set())
                        if valid_set:
                            llm_ts_norm_errors += 1

                    ts_mark = "+" if ts_ok else "-"
                    t_display = f"{ts_mark} {ts_val}" if ts_val else "- None"
                    line += f"  {t_display:<20}"

                if has_paraaware:
                    pa_ok = (
                        pa_val is not None
                        and pa_val.strip().lower() == gt_val.strip().lower()
                    )
                    llm_pa_total += 1
                    if pa_ok:
                        llm_pa_correct += 1
                        llm_pa_q_ok += 1

                    if pa_val is None and gt_val is not None:
                        axis_lower = axis.strip().lower()
                        valid_set = valid_values_lower.get(pk, {}).get(axis_lower, set())
                        if valid_set:
                            llm_pa_norm_errors += 1

                    pa_mark = "+" if pa_ok else "-"
                    p_display = f"{pa_mark} {pa_val}" if pa_val else "- None"
                    line += f"  {p_display:<20}"

                if has_paraaware2:
                    pa2_ok = (
                        pa2_val is not None
                        and pa2_val.strip().lower() == gt_val.strip().lower()
                    )
                    llm_pa2_total += 1
                    if pa2_ok:
                        llm_pa2_correct += 1
                        llm_pa2_q_ok += 1

                    if pa2_val is None and gt_val is not None:
                        axis_lower = axis.strip().lower()
                        valid_set = valid_values_lower.get(pk, {}).get(axis_lower, set())
                        if valid_set:
                            llm_pa2_norm_errors += 1

                    pa2_mark = "+" if pa2_ok else "-"
                    p2_display = f"{pa2_mark} {pa2_val}" if pa2_val else "- None"
                    line += f"  {p2_display:<20}"

                print(line)

            if llm_ext_q_ok == len(gt):
                llm_ext_q_all_correct += 1
            if has_classify and llm_cls_q_ok == len(gt):
                llm_cls_q_all_correct += 1
            if has_twostep and llm_ts_q_ok == len(gt):
                llm_ts_q_all_correct += 1
            if has_paraaware and llm_pa_q_ok == len(gt):
                llm_pa_q_all_correct += 1
            if has_paraaware2 and llm_pa2_q_ok == len(gt):
                llm_pa2_q_all_correct += 1

        ext_avg_ms = (llm_extract_elapsed / len(items)) * 1000

        print(f"\n  Comparison Summary:")
        print(
            f"    Rule-based:  per-axis {correct_axes}/{total_axes} "
            f"= {correct_axes / total_axes:.1%}, "
            f"per-query {queries_all_correct}/{len(items)} "
            f"= {queries_all_correct / len(items):.1%}, "
            f"avg {rule_avg_ms:.3f}ms/query"
        )
        print(
            f"    LLM-extract: per-axis {llm_ext_correct}/{llm_ext_total} "
            f"= {llm_ext_correct / llm_ext_total:.1%}, "
            f"per-query {llm_ext_q_all_correct}/{len(items)} "
            f"= {llm_ext_q_all_correct / len(items):.1%}, "
            f"avg {ext_avg_ms:.0f}ms/query"
        )
        if has_classify:
            cls_avg_ms = (llm_classify_elapsed / len(items)) * 1000
            print(
                f"    LLM-classify: per-axis {llm_cls_correct}/{llm_cls_total} "
                f"= {llm_cls_correct / llm_cls_total:.1%}, "
                f"per-query {llm_cls_q_all_correct}/{len(items)} "
                f"= {llm_cls_q_all_correct / len(items):.1%}, "
                f"avg {cls_avg_ms:.0f}ms/query"
            )
        if has_twostep:
            ts_avg_ms = (llm_twostep_elapsed / len(items)) * 1000
            print(
                f"    LLM-twostep: per-axis {llm_ts_correct}/{llm_ts_total} "
                f"= {llm_ts_correct / llm_ts_total:.1%}, "
                f"per-query {llm_ts_q_all_correct}/{len(items)} "
                f"= {llm_ts_q_all_correct / len(items):.1%}, "
                f"avg {ts_avg_ms:.0f}ms/query"
            )
        if has_paraaware:
            pa_avg_ms = (llm_paraaware_elapsed / len(items)) * 1000
            print(
                f"    LLM-paraaware: per-axis {llm_pa_correct}/{llm_pa_total} "
                f"= {llm_pa_correct / llm_pa_total:.1%}, "
                f"per-query {llm_pa_q_all_correct}/{len(items)} "
                f"= {llm_pa_q_all_correct / len(items):.1%}, "
                f"avg {pa_avg_ms:.0f}ms/query"
            )
        if has_paraaware2:
            pa2_avg_ms = (llm_paraaware2_elapsed / len(items)) * 1000
            print(
                f"    LLM-paraaware2: per-axis {llm_pa2_correct}/{llm_pa2_total} "
                f"= {llm_pa2_correct / llm_pa2_total:.1%}, "
                f"per-query {llm_pa2_q_all_correct}/{len(items)} "
                f"= {llm_pa2_q_all_correct / len(items):.1%}, "
                f"avg {pa2_avg_ms:.0f}ms/query"
            )

        # Error breakdown (always show when any LLM method ran)
        print(
            f"\n  Error breakdown (LLM returned None for axis with valid values):"
        )
        print(f"    LLM-extract:  {llm_ext_norm_errors}")
        if has_classify:
            print(f"    LLM-classify: {llm_cls_norm_errors}")
        if has_twostep:
            print(f"    LLM-twostep:  {llm_ts_norm_errors}")
        if has_paraaware:
            print(f"    LLM-paraaware: {llm_pa_norm_errors}")
        if has_paraaware2:
            print(f"    LLM-paraaware2: {llm_pa2_norm_errors}")
            if llm_pa2_extractor is not None:
                print(
                    f"\n  Step 2 fallback count (paraaware2): "
                    f"{llm_pa2_extractor._paraaware2_step2_fallbacks}"
                )
    else:
        print("\n  (LLM comparison skipped)")

    print("\n" + "=" * 70)
    print("Tests complete.")
    print("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Rule-Based Parameter Extractor (Stage 2 Baseline) — Tests"
    )
    parser.add_argument(
        "--n-queries",
        type=int,
        default=20,
        help="Number of queries for batch test (default: 20)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama base URL for LLM comparison (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM comparison",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Include LLM-classify in comparison",
    )
    parser.add_argument(
        "--twostep",
        action="store_true",
        help="Include LLM-twostep in comparison",
    )
    parser.add_argument(
        "--paraaware",
        action="store_true",
        help="Include LLM-paraaware in comparison",
    )
    parser.add_argument(
        "--paraaware2",
        action="store_true",
        help="Include LLM-paraaware2 in comparison",
    )
    parser.add_argument(
        "--model",
        default="llama3.1:8b",
        help="Ollama model to use for LLM extraction (default: llama3.1:8b)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    _run_tests(
        n_queries=args.n_queries,
        base_url=args.base_url,
        skip_llm=args.skip_llm,
        classify=args.classify,
        twostep=args.twostep,
        paraaware=args.paraaware,
        paraaware2=args.paraaware2,
        model=args.model,
    )
