"""Multi-head E5 classifier for parameter extraction (Stage 2).

Replaces LLM-based extraction with a fine-tuned encoder + per-(group, axis)
classification heads. Each head outputs a distribution over the axis's value
set plus a null class (index 0).

Interface matches RuleBasedParamExtractor / LLMParamExtractor for drop-in use.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)

HEAD_SEP = "__"  # separator in ModuleDict keys: "OEB010$__TERRENO"


class MultiHeadClassifier(nn.Module):
    """E5 encoder + per-(concept_group, axis) classification heads."""

    def __init__(self, encoder_name: str, label_encoders: dict):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(encoder_name)
        self.hidden_size = self.encoder.config.hidden_size

        # Build one linear head per (parent_key, axis)
        self.heads = nn.ModuleDict()
        self.head_info = {}  # head_key -> (parent_key, axis_label, num_classes)
        for parent_key, axes in label_encoders.items():
            for axis_label, val_map in axes.items():
                head_key = f"{parent_key}{HEAD_SEP}{axis_label}"
                num_classes = len(val_map)
                self.heads[head_key] = nn.Linear(self.hidden_size, num_classes)
                self.head_info[head_key] = (parent_key, axis_label, num_classes)

        # Group heads by parent_key for fast lookup
        self._parent_heads = {}
        for head_key, (pk, axis, _) in self.head_info.items():
            self._parent_heads.setdefault(pk, []).append((head_key, axis))

    def forward(self, input_ids, attention_mask, head_keys: list[str]):
        """Run encoder and return logits for requested heads only.

        Returns: dict {head_key: logits tensor (batch, num_classes)}
        """
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls_emb = outputs.last_hidden_state[:, 0, :]  # [CLS] token

        result = {}
        for hk in head_keys:
            result[hk] = self.heads[hk](cls_emb)
        return result

    def get_head_keys_for_parent(self, parent_key: str) -> list[tuple[str, str]]:
        """Return [(head_key, axis_label), ...] for a concept group."""
        return self._parent_heads.get(parent_key, [])


class ClassifierParamExtractor:
    """Stage 2 extractor using the multi-head E5 classifier.

    Interface matches RuleBasedParamExtractor / LLMParamExtractor.
    """

    def __init__(
        self,
        model_dir: str | Path,
        device: str = "cpu",
        encoder_name: str = "intfloat/multilingual-e5-base",
    ):
        model_dir = Path(model_dir)
        repo_root = Path(__file__).resolve().parents[2]

        # Load label encoders
        config_path = model_dir / "config.json"
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        enc_path = config.get("label_encoders_path")
        if enc_path:
            enc_path = Path(enc_path)
            # Resolve Docker path (/work/...) to local if needed
            enc_str = str(enc_path).replace("\\", "/")
            if not enc_path.exists() and enc_str.startswith("/work/"):
                enc_path = repo_root / enc_str.removeprefix("/work/")
            with open(enc_path, encoding="utf-8") as f:
                self.label_encoders = json.load(f)
        else:
            with open(model_dir / "classifier_label_encoders.json", encoding="utf-8") as f:
                self.label_encoders = json.load(f)

        # Build inverse mapping: {parent_key: {axis: {index: value_or_None}}}
        self._inverse = {}
        for pk, axes in self.label_encoders.items():
            self._inverse[pk] = {}
            for axis, val_map in axes.items():
                inv = {idx: (val if val != "null" else None) for val, idx in val_map.items()}
                self._inverse[pk][axis] = inv

        # Load model
        self.device = torch.device(device)
        resolved_encoder = config.get("encoder_name", encoder_name)
        self.model = MultiHeadClassifier(resolved_encoder, self.label_encoders)

        ckpt_path = model_dir / "model.pt"
        if ckpt_path.exists():
            state = torch.load(ckpt_path, map_location=self.device, weights_only=True)
            # strict=False handles cross-version differences (e.g. position_ids)
            self.model.load_state_dict(state, strict=False)
            logger.info("Loaded checkpoint from %s", ckpt_path)

        self.model.to(self.device)
        self.model.eval()

        # Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(resolved_encoder)

    def extract(self, parent_key: str, query_text: str) -> dict:
        """Extract parameter values for a single query.

        Returns: {axis_label: value | None}
        """
        head_pairs = self.model.get_head_keys_for_parent(parent_key)
        if not head_pairs:
            return {}

        # Tokenize with E5 query prefix
        inputs = self.tokenizer(
            f"query: {query_text}",
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(self.device)

        head_keys = [hk for hk, _ in head_pairs]

        with torch.no_grad():
            logits_dict = self.model(inputs["input_ids"], inputs["attention_mask"], head_keys)

        result = {}
        for hk, axis in head_pairs:
            logits = logits_dict[hk]
            pred_idx = logits.argmax(dim=-1).item()
            result[axis] = self._inverse[parent_key][axis][pred_idx]
        return result

    def extract_batch(
        self, parent_keys: list[str], query_texts: list[str]
    ) -> list[dict]:
        """Extract parameters for a batch of queries.

        For simplicity, iterates over queries (each may have different active
        heads). Batching across queries with the same parent_key is a future
        optimization.
        """
        return [
            self.extract(pk, qt) for pk, qt in zip(parent_keys, query_texts)
        ]
