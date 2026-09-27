"""Corpus and query preparation — the functions that used to live inside `data.ipynb`.

They are moved here unchanged, so that they can be tested (they could not be, in a notebook
cell) and shared with the query-side code S1 adds. `tests/test_corpus_prep.py` pins them to
the output already recorded in `OEB_short_norm.parquet` and `OEB_long_norm.parquet`, row by
row, which is what makes "unchanged" a checked claim rather than an intention.

The one addition is `normalize_parameters_field` accepting BC3CAT-Syn's flat query shape
alongside the corpus's nested one — INTAKE §4 breakpoint 2. Everything else is verbatim.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict

import pandas as pd

# ---------------- Normalization & tokenization ----------------
WS_RE = re.compile(r"\s+", re.UNICODE)
THOUSANDS_DOT_RE = re.compile(r"(?<=\d)\.(?=\d{3}\b)")  # 1.234 -> 1234
DECIMAL_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")        # 1,60 -> 1.60
PERCENT_RE = re.compile(r"(?<=\d)%")                    # 95%  -> 95 %
WORD_TOKEN_RE_NO_NUM = re.compile(r"[a-záéíóúüñ]+", flags=re.UNICODE)
_WORD = re.compile(r"[a-záéíóúüñ0-9]+", re.UNICODE)

# Word tokens: Spanish letters & numeric forms, including 4x40
WORD_TOKEN_RE = re.compile(r"[a-záéíóúüñ]+|\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)?", flags=re.UNICODE)

NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)?")


def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    s = s.lower()
    s = THOUSANDS_DOT_RE.sub("", s)
    s = DECIMAL_COMMA_RE.sub(".", s)
    s = PERCENT_RE.sub(" %", s)
    s = WS_RE.sub(" ", s).strip()
    return s


def normalize_param_string(s: str) -> str:
    """Same normalization as text, then trim inner spaces."""
    return normalize_text(s)


def is_multiword_norm(s: str, min_tokens: int = 2) -> bool:
    """Count *word* tokens (letters only). 'Volumen escaso' -> 2 (True)."""
    return len(WORD_TOKEN_RE_NO_NUM.findall(s)) >= min_tokens


def snake_merge(s: str) -> str:
    """Turn normalized phrase into snake_case, keeping accents."""
    return "_".join(WORD_TOKEN_RE.findall(s))


def tokenize_words(s: str) -> list[str]:
    return WORD_TOKEN_RE.findall(s)


def make_text_char(text_norm: str, pad_char: str = " ") -> str:
    """The char-ngrams view: the normalized string with boundary padding."""
    if not isinstance(text_norm, str):
        text_norm = "" if text_norm is None else str(text_norm)
    return f"{pad_char}{text_norm}{pad_char}"


def extract_numbers(s: str) -> list[float]:
    nums = []
    for m in NUMBER_TOKEN_RE.findall(s):
        if "x" in m:
            for p in m.split("x"):
                try:
                    nums.append(float(p))
                except ValueError:
                    pass
        else:
            try:
                nums.append(float(m))
            except ValueError:
                pass
    return nums


# ---------------- Parameters ----------------

def is_flat_parameters(par: Any) -> bool:
    """True for BC3CAT-Syn's query shape: axis label -> a plain value (or null).

    The corpus nests each axis as {'label': ..., 'values': [...]}; a synthetic query flattens
    it to {'A': '3x1.5 cm', 'F': None}. Telling them apart by the type of the values is
    enough, and is checked rather than assumed: a dict with a 'values' list is nested.
    """
    if not isinstance(par, dict) or not par:
        return False
    return not any(isinstance(block, dict) and "values" in block for block in par.values())


def nest_flat_parameters(par: Dict[str, Any], axis_labels: Dict[str, str] | None = None) -> dict:
    """Lift a flat query `parameters` into the nested shape the corpus uses.

    `axis_labels` maps the axis key ('A') to the label the concept gives it, and comes from
    `OE_concept_schema.json`. Without it the axis key stands in for the label, which keeps
    the shape valid but makes the resulting param tokens incomparable with the corpus's —
    so callers that intend to match tokens must pass it.
    """
    axis_labels = axis_labels or {}
    nested: dict[str, dict] = {}
    for axis, value in par.items():
        if value is None:
            continue
        nested[axis] = {
            "label": axis_labels.get(axis, axis),
            "values": [{"label": axis, "value": str(value)}],
        }
    return nested


def axis_labels_from_corpus(records) -> Dict[str, Dict[str, str]]:
    """Map `parent_key -> {axis letter: axis label}`, read off the corpus itself.

    `OE_concept_schema.json` lists a concept's axes by label, without the letter the records
    key them on, so the letter-to-label correspondence exists only in the corpus — where both
    appear in the same block. Siblings share it, so the first leaf of each concept settles it.
    """
    if isinstance(records, pd.DataFrame):
        records = records.to_dict("records")

    labels: Dict[str, Dict[str, str]] = {}
    for record in records:
        parent = record.get("parent_key")
        if not parent or parent in labels:
            continue
        block_labels = {}
        for axis, block in (record.get("parameters") or {}).items():
            if isinstance(block, dict):
                block_labels[axis] = block.get("label", axis)
        if block_labels:
            labels[parent] = block_labels
    return labels


def normalize_parameters_field(par, axis_labels: Dict[str, str] | None = None):
    """
    Input: nested dict like:
      {'A': {'label': ' TERRENO ', 'values': [{'label': 'a','value': ' blando '}]}, ...}
    or BC3CAT-Syn's flat query dict:
      {'A': '3x1.5 cm', 'B': 'Diurno', 'F': None}

    Returns:
      parameters_norm:  same structure, but with 'label_norm' and 'value_norm' added
      param_values_multi_norm: flat list[str] of DISTINCT normalized multi-word values
    """
    if not isinstance(par, dict):
        return {}, []

    if is_flat_parameters(par):
        par = nest_flat_parameters(par, axis_labels)

    # An axis a concept does not use is present and null — 7,212 of the 70,242 OE corpus
    # records carry one, and the unmigrated code raised on every one of them. A null axis
    # contributes no label and no value, so it is dropped rather than defaulted: inventing an
    # empty value here would mint a `param_<label>_value` token that nothing else has.
    par_norm = copy.deepcopy({k: v for k, v in par.items() if isinstance(v, dict)})
    seen = set()
    multi = []

    for _, block in par_norm.items():
        # normalize block label
        raw_label = block.get("label", "")
        block["label_norm"] = normalize_param_string(raw_label)

        # normalize each value entry
        vals = block.get("values", [])
        for v in vals:
            raw_v = v.get("value", "")
            v["value_norm"] = normalize_param_string(raw_v)

            # collect multi-word normalized values (distinct)
            val_norm = v["value_norm"]
            if is_multiword_norm(val_norm):
                if val_norm not in seen:
                    seen.add(val_norm)
                    multi.append(val_norm)

    return par_norm, multi


def _slug_words(s: str) -> str:
    """Lowercase and keep only [a-záéíóúüñ0-9]+ chunks, joined by '_'."""
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    return "_".join(_WORD.findall(s.lower()))


def _canon_comparators(s: str) -> str:
    """Turn symbols into words so they survive word tokenization."""
    s = s.replace("≥", ">=").replace("≤", "<=")
    s = re.sub(r"\s*>=\s*", " ge ", s)
    s = re.sub(r"\s*<=\s*", " le ", s)
    s = re.sub(r"\s*>\s*", " gt ", s)
    s = re.sub(r"\s*<\s*", " lt ", s)
    return s


def build_param_tokens(parameters_norm: dict) -> list[str]:
    """For each block, mint 'param_<label_slug>_<value_slug>' from normalized labels/values."""
    out = []
    if not isinstance(parameters_norm, dict):
        return out
    for _, block in parameters_norm.items():
        lab_slug = _slug_words(block.get("label_norm", "")) or "label"
        for v in block.get("values", []):
            val_norm = _canon_comparators(v.get("value_norm", ""))
            val_slug = _slug_words(val_norm) or "value"
            out.append(f"param_{lab_slug}_{val_slug}")
    return out


def add_processed_columns(df: pd.DataFrame, raw_col: str) -> pd.DataFrame:
    df = df.copy()
    df["text_norm"] = df[raw_col].map(normalize_text)
    df["tokens_word"] = df["text_norm"].map(tokenize_words)
    df["text_word"] = df["tokens_word"].map(lambda toks: " ".join(toks))
    df["text_char"] = df["text_norm"].map(make_text_char)
    df["numbers"] = df["text_norm"].map(extract_numbers)

    out_par_norm = []
    out_param_values_multi = []
    for par in df["parameters"].tolist():
        par_norm, multi_norm = normalize_parameters_field(par)
        out_par_norm.append(par_norm)
        out_param_values_multi.append(multi_norm)

    df["parameters_norm"] = out_par_norm
    df["param_values_multi_norm"] = out_param_values_multi
    return df


def add_param_token_columns(df: pd.DataFrame) -> pd.DataFrame:
    """The two columns data.ipynb added outside add_processed_columns."""
    df = df.copy()
    df["param_tokens"] = df["parameters_norm"].map(build_param_tokens)
    df["text_word_params"] = df.apply(
        lambda r: (r["text_word"] + " " + " ".join(r["param_tokens"])).strip(), axis=1
    )
    return df


# ---------------- Loading ----------------

#: The projection data.ipynb applied to every record. Query sets carry more than this, and
#: what they carry beyond it is the gold and the slice metadata, so it must not be dropped
#: (INTAKE §4 breakpoint 3).
CORPUS_FIELDS = ("id", "item_key", "parent_key", "ud", "concept", "parameters", "text")
#: `texto_modification_*` arrived with the 2026-09-27 delivery and is the *visible* dose — the
#: modifications that actually reach the TEXTO. `modification_*` counts every applied record and
#: overstates the dose in the stacked set (D-025, and the D-004/D-025 note of 2026-09-17), so
#: every stratification by dose or by type reads the `texto_` field. Only the stacked set carries
#: it: SINGLE is exact by construction, so there the two would be equal and upstream emits one.
QUERY_FIELDS = (
    "gold_item_key",
    "modification_types",
    "modification_count",
    "texto_modification_types",
    "texto_modification_count",
)


def _as_record_from_obj(doc: Any, extra_fields: tuple[str, ...] = ()) -> Dict[str, Any]:
    """Flatten one record, preferring metadata over top-level keys, as data.ipynb did."""
    if isinstance(doc, dict):
        text = doc.get("text") or doc.get("content")
        md = (doc.get("metadata") or {}) if isinstance(doc.get("metadata"), dict) else {}
        root = doc
        doc_id = (
            root.get("id") or root.get("id_") or root.get("doc_id")
            or md.get("id") or md.get("id_") or md.get("doc_id")
        )
    else:
        text = getattr(doc, "text", None)
        md = getattr(doc, "metadata", None) or {}
        root = {}
        doc_id = getattr(doc, "id_", None) or getattr(doc, "doc_id", None) or md.get("id")

    def pick(key: str, default=None):
        return md.get(key, root.get(key, default))

    params = pick("parameters", {})
    if not isinstance(params, dict):
        params = {}

    record = {
        "id": doc_id,
        "item_key": pick("item_key"),
        "parent_key": pick("parent_key"),
        "ud": pick("ud"),
        "concept": pick("concept"),
        "parameters": params,
        "text": text if isinstance(text, str) else pick("text", ""),
    }
    # An extra field is carried only when the record actually has it. Adding an all-null column
    # to a query set the delivery never gave the field to would change that table's parquet
    # digest for no information — and those digests are what `runs/*/run_meta.json` stamps, so
    # the churn would invalidate runs that are still perfectly valid. Absence is then loud at
    # read time instead of silently stratifying on nulls.
    for field in extra_fields:
        if field in md or field in root:
            record[field] = pick(field)
    return record


def load_records(path: Path, extra_fields: tuple[str, ...] = ()) -> pd.DataFrame:
    """Load a list of documents (or {'documents': [...]}) into a DataFrame."""
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        container = obj
    elif isinstance(obj, dict):
        container = None
        for key in ("documents", "data", "items", "records"):
            if key in obj and isinstance(obj[key], list):
                container = obj[key]
                break
        if container is None:
            raise TypeError(
                f"Unsupported JSON shape in {path}. Expected a list or an object with a list "
                "under 'documents'/'data'."
            )
    else:
        raise TypeError(f"Unsupported JSON root type in {path}: {type(obj)}")

    return pd.DataFrame([_as_record_from_obj(d, extra_fields) for d in container]).reset_index(
        drop=True
    )


def assert_gold_present(queries: pd.DataFrame, corpus_keys) -> None:
    """Fail loud when a query's gold leaf is absent from the corpus (INTAKE §4 breakpoint 1).

    The old harness inferred the gold from the query's own key, so a synthetic query — whose
    key is `<leaf>_syn_<hash>` and is deliberately not in the corpus — would have scored
    against nothing and been dropped without a word. A dropped query is not a zero: it
    silently shrinks the denominator, and a whole condition can disappear that way.

    A query set with no `gold_item_key` column is one of the corpus's own renderings (`texto`,
    `resumen`), where the query key *is* the gold; those are checked against the corpus too.
    """
    column = "gold_item_key" if "gold_item_key" in queries.columns else "item_key"
    corpus_keys = set(corpus_keys)

    absent = queries[~queries[column].astype(str).isin(corpus_keys)]
    if len(absent):
        listed = ", ".join(absent["item_key"].astype(str).head(5))
        raise KeyError(
            f"{len(absent)} of {len(queries)} queries have a {column} absent from the corpus: "
            f"{listed}{' …' if len(absent) > 5 else ''}. A query whose gold is missing is never "
            "dropped silently."
        )


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop empty text and the template rows, whose keys end in '#' or '$'.

    This is where OEB's single `OEB#` row goes: the JSON holds 47,514 records and the
    parquets 47,513 (D-024). The OE corpus carries no such row.
    """
    df = df.dropna(subset=["text", "item_key"])
    df = df[df["text"].str.strip() != ""]
    df = df[~df["item_key"].astype(str).str.endswith(("#", "$"), na=False)]
    return df
