"""Token-level BIO tagger for parameter extraction (Stage 2).

Replaces the multi-head CLS classifier with a shared BIO head that operates
on token-level evidence. The hypothesis (protocol §3.2): a tagger conditioned
on token representations should not exhibit the cross-distribution collapse
that defeated the CLS architecture, where the entire decision was conditioned
on a single 768-dim aggregation.

Architecture:
    Query text
      → E5 tokenizer (no "query:" prefix; matches LWN-01 training data)
      → E5 encoder (intfloat/multilingual-e5-base)
      → per-token hidden states (T × 768)
      → shared Linear(768, 27)
      → per-token BIO logits
      → greedy argmax + BIO post-processing → list of (axis, surface_text) spans
      → SpanNormalizer (deterministic, schema-bounded) → {axis: canonical_value | None}

The extractor exposes the same interface as RuleBasedParamExtractor /
ClassifierParamExtractor: `extract(parent_key, query) -> dict` and
`extract_batch`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

from src.pipeline.span_normalizer import SpanNormalizer

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "processed"
DEFAULT_SCHEMA_PATH = DATA_DIR / "OEB_concept_schema.json"
DEFAULT_INVENTORY_PATH = DATA_DIR / "bio_label_inventory.json"
DEFAULT_ENCODER = "intfloat/multilingual-e5-base"
DEFAULT_MAX_LEN = 512


# ── Model ───────────────────────────────────────────────────────────────────

class BIOTagger(nn.Module):
    """E5 encoder + single shared Linear head over BIO labels.

    The head is shared across all 25 concept groups; per-(group, axis) value
    constraints are applied downstream by SpanNormalizer. This consolidates
    training signal across groups for axes that recur (TRABAJO appears in 21
    of 25 groups), which is the central architectural commitment vs. the CLS
    classifier's 97 fragmented heads (protocol §4.2).
    """

    def __init__(self, encoder_name: str = DEFAULT_ENCODER, num_labels: int = 27):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(encoder_name)
        self.hidden_size = self.encoder.config.hidden_size
        self.num_labels = num_labels
        self.head = nn.Linear(self.hidden_size, num_labels)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Returns per-token logits of shape (B, T, num_labels)."""
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        return self.head(outputs.last_hidden_state)


# ── BIO post-processing ─────────────────────────────────────────────────────

def decode_bio_spans(
    bio_labels: list[str],
    offsets: list[tuple[int, int]],
    text: str,
) -> list[tuple[str, str, int, int]]:
    """Walk a BIO-tagged token sequence and emit span tuples.

    Returns a list of (axis_label, surface_text, char_start, char_end).

    Robustness rules (protocol §4.6):
      - A stray I-X without a preceding B-X is treated as B-X.
      - Adjacent same-axis B-X spans are merged into one (catches a model that
        re-labels the head of a continuing span).
      - O closes any open span.
      - Special tokens (offsets == (0,0)) are skipped — they neither open nor
        extend a span.
    """
    spans: list[tuple[str, str, int, int]] = []
    cur_axis: str | None = None
    cur_token_idxs: list[int] = []

    def _flush() -> None:
        nonlocal cur_axis, cur_token_idxs
        if cur_axis is not None and cur_token_idxs:
            starts = [offsets[i][0] for i in cur_token_idxs]
            ends = [offsets[i][1] for i in cur_token_idxs]
            char_start = min(starts)
            char_end = max(ends)
            surface = text[char_start:char_end]
            spans.append((cur_axis, surface, char_start, char_end))
        cur_axis, cur_token_idxs = None, []

    for i, lab in enumerate(bio_labels):
        if i >= len(offsets):
            break
        start, end = offsets[i]
        if start == 0 and end == 0:
            # Special token — skip without flushing the open span (subwords
            # never span [CLS]/[SEP], so flushing isn't needed)
            continue

        if lab == "O":
            _flush()
            continue

        prefix, axis = lab[0], lab[2:]
        if prefix == "B":
            _flush()
            cur_axis = axis
            cur_token_idxs = [i]
        elif prefix == "I":
            if cur_axis == axis:
                cur_token_idxs.append(i)
            else:
                # Stray I-X: treat as B-X (defensive per protocol §4.6)
                _flush()
                cur_axis = axis
                cur_token_idxs = [i]
        else:
            # Unknown prefix — treat as O
            _flush()

    _flush()
    return spans


def merge_adjacent_same_axis(
    spans: list[tuple[str, str, int, int]],
    text: str,
) -> list[tuple[str, str, int, int]]:
    """Merge spans of the same axis whose char ranges abut (or are separated
    only by whitespace). Defensive against B-X B-X B-X mislabeling."""
    if not spans:
        return spans
    merged = [spans[0]]
    for axis, surface, cs, ce in spans[1:]:
        prev_axis, prev_surface, prev_cs, prev_ce = merged[-1]
        gap = text[prev_ce:cs]
        if axis == prev_axis and gap.strip() == "":
            new_surface = text[prev_cs:ce]
            merged[-1] = (axis, new_surface, prev_cs, ce)
        else:
            merged.append((axis, surface, cs, ce))
    return merged


# ── Extractor ───────────────────────────────────────────────────────────────

class BIOParamExtractor:
    """Stage 2 extractor: BIOTagger + SpanNormalizer.

    Same contract as RuleBasedParamExtractor / ClassifierParamExtractor:
        extract(parent_key, query) -> {axis_label: value | None, ...}
    The output dict has one entry per axis defined in
    schema[parent_key]["axes"]; missing or unmappable spans become None.
    """

    def __init__(
        self,
        model_dir: str | Path,
        schema_path: str | Path = DEFAULT_SCHEMA_PATH,
        inventory_path: str | Path = DEFAULT_INVENTORY_PATH,
        device: str = "cpu",
        encoder_name: str | None = None,
        max_length: int = DEFAULT_MAX_LEN,
    ):
        model_dir = Path(model_dir)
        repo_root = Path(__file__).resolve().parents[2]

        # Load config (mirrors ClassifierParamExtractor pattern)
        config_path = model_dir / "config.json"
        config = {}
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
        resolved_encoder = encoder_name or config.get("encoder_name") or DEFAULT_ENCODER

        # Resolve inventory path: prefer config-recorded path; fall back to default;
        # tolerate Docker /work/ paths on non-Docker hosts.
        inv_path = config.get("label_inventory_path") or str(inventory_path)
        inv_resolved = Path(inv_path)
        if not inv_resolved.exists():
            s = str(inv_resolved).replace("\\", "/")
            if s.startswith("/work/"):
                inv_resolved = repo_root / s.removeprefix("/work/")
        with open(inv_resolved, encoding="utf-8") as f:
            self.label_inventory: dict[str, int] = json.load(f)

        self.id_to_label = [None] * len(self.label_inventory)
        for label, idx in self.label_inventory.items():
            self.id_to_label[idx] = label

        # Load schema (used by extract() to know which axes to query)
        with open(schema_path, encoding="utf-8") as f:
            self.schema = json.load(f)
        self.normalizer = SpanNormalizer(self.schema)

        # Tokenizer + model
        self.device = torch.device(device)
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(resolved_encoder)
        self.model = BIOTagger(resolved_encoder, num_labels=len(self.label_inventory))

        ckpt_path = model_dir / "model.pt"
        if ckpt_path.exists():
            state = torch.load(ckpt_path, map_location=self.device, weights_only=True)
            self.model.load_state_dict(state, strict=False)
            logger.info("Loaded BIO checkpoint from %s", ckpt_path)
        else:
            logger.warning("No checkpoint at %s — model is randomly initialized", ckpt_path)

        self.model.to(self.device)
        self.model.eval()

    # ── public API ──────────────────────────────────────────────────────────

    def extract(self, parent_key: str, query_text: str) -> dict[str, str | None]:
        """Extract canonical parameter values for a single query.

        Returns a dict keyed by every axis in schema[parent_key]["axes"]
        (or empty if parent_key is unknown).
        """
        if parent_key not in self.schema:
            return {}
        axes = list(self.schema[parent_key]["axes"].keys())
        result: dict[str, str | None] = {a: None for a in axes}

        encoding = self.tokenizer(
            query_text,
            return_offsets_mapping=True,
            truncation=True,
            max_length=self.max_length,
            padding=False,
            add_special_tokens=True,
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(self.device)
        attn_mask = encoding["attention_mask"].to(self.device)
        offsets = encoding["offset_mapping"][0].tolist()

        with torch.no_grad():
            logits = self.model(input_ids, attn_mask)  # (1, T, 27)
        pred_ids = logits.argmax(dim=-1)[0].tolist()
        bio_labels = [self.id_to_label[i] for i in pred_ids]

        spans = decode_bio_spans(bio_labels, offsets, query_text)
        spans = merge_adjacent_same_axis(spans, query_text)

        # First span per axis wins (protocol §4.1: simple greedy decoding)
        seen: set[str] = set()
        for axis, surface, _cs, _ce in spans:
            if axis in seen or axis not in result:
                continue
            canonical = self.normalizer.normalize(axis, surface, parent_key)
            result[axis] = canonical
            seen.add(axis)
        return result

    def extract_batch(
        self, parent_keys: list[str], query_texts: list[str]
    ) -> list[dict[str, str | None]]:
        """Per-query batching is sufficient for the planned eval throughput.

        True batched encoding across queries with different parent_keys is a
        future optimization (each query has a different set of relevant axes,
        so the post-processing already differs row-by-row).
        """
        return [self.extract(pk, qt) for pk, qt in zip(parent_keys, query_texts)]
