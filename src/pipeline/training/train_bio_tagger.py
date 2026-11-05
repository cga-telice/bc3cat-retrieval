"""Training script for the shared BIO tagger (Stage 2).

Loads bio_training_data.parquet + bio_label_inventory.json, fine-tunes
intfloat/multilingual-e5-base with a single shared Linear(768, 27) head over
BIO labels.

Training data is the long catalog text (text_norm). Evaluation queries (short
text) remain a fully held-out cross-distribution test, identical to the LW-06
methodology (protocol §1).

Per-epoch metrics on val:
  - token_acc  — per-token accuracy excluding special tokens (PAD, CLS, SEP)
  - span_f1    — macro span-level F1 across the 13 axes (best-checkpoint metric)
  - query_acc  — end-to-end: BIOTagger + SpanNormalizer vs canonical values

Usage::

    python -m src.pipeline.training.train_bio_tagger
    python -m src.pipeline.training.train_bio_tagger --epochs 5 --batch-size 16 --device cuda
    python -m src.pipeline.training.train_bio_tagger --sanity 100 --epochs 1 --device cpu
"""

import argparse
import json
import logging
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

from src.pipeline.param_extractor_bio import (
    BIOTagger,
    decode_bio_spans,
    merge_adjacent_same_axis,
)
from src.pipeline.span_normalizer import SpanNormalizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data" / "processed"
DEFAULT_OUTPUT_DIR = ROOT / "models" / "e5_bio_tagger"
DEFAULT_ENCODER = "intfloat/multilingual-e5-base"
MAX_LEN = 512
IGNORE_INDEX = -100  # CE default; applies to special tokens during loss/eval


# ── Dataset ─────────────────────────────────────────────────────────────────

class BIOTaggerDataset(Dataset):
    """Re-tokenizes text_norm at training time (deterministic) and aligns the
    stored bio_labels to integer label ids. Special tokens get IGNORE_INDEX
    so they are excluded from CE loss and from token-level accuracy.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        label_inventory: dict[str, int],
        tokenizer,
        max_length: int = MAX_LEN,
    ):
        self.texts = df["text_norm"].tolist()
        self.bio_labels = df["bio_labels"].tolist()
        self.parent_keys = df["parent_key"].tolist()
        self.item_keys = df["item_key"].tolist()
        self.label_inventory = label_inventory
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        labels_str = list(self.bio_labels[idx])

        encoding = self.tokenizer(
            text,
            return_offsets_mapping=True,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            add_special_tokens=True,
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"].squeeze(0)
        attention_mask = encoding["attention_mask"].squeeze(0)
        offsets = encoding["offset_mapping"].squeeze(0).tolist()

        # Map stored BIO strings to ids; pad/truncate to match tokenization.
        # Special tokens (offset (0,0)) and pad positions get IGNORE_INDEX.
        label_ids = [IGNORE_INDEX] * len(input_ids)
        for i in range(len(input_ids)):
            if attention_mask[i].item() == 0:
                continue  # padding
            start, end = offsets[i]
            if start == 0 and end == 0:
                continue  # special token
            if i < len(labels_str):
                lbl = labels_str[i]
                label_ids[i] = self.label_inventory.get(lbl, IGNORE_INDEX)
        labels = torch.tensor(label_ids, dtype=torch.long)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
            "offsets": offsets,
            "text": text,
            "parent_key": self.parent_keys[idx],
            "item_key": self.item_keys[idx],
        }


def collate_fn(batch):
    return {
        "input_ids": torch.stack([b["input_ids"] for b in batch]),
        "attention_mask": torch.stack([b["attention_mask"] for b in batch]),
        "labels": torch.stack([b["labels"] for b in batch]),
        "offsets": [b["offsets"] for b in batch],
        "texts": [b["text"] for b in batch],
        "parent_keys": [b["parent_key"] for b in batch],
        "item_keys": [b["item_key"] for b in batch],
    }


# ── Span-F1 metric ──────────────────────────────────────────────────────────

def labels_to_axis_spans(label_seq: list[str]) -> set[tuple[str, int, int]]:
    """Convert a BIO label sequence to a set of (axis, start, end) tuples
    (token-index based; end is exclusive)."""
    spans: set[tuple[str, int, int]] = set()
    cur_axis: str | None = None
    cur_start: int | None = None
    for i, lab in enumerate(label_seq):
        if lab == "O":
            if cur_axis is not None:
                spans.add((cur_axis, cur_start, i))
                cur_axis, cur_start = None, None
            continue
        prefix, axis = lab[0], lab[2:]
        if prefix == "B":
            if cur_axis is not None:
                spans.add((cur_axis, cur_start, i))
            cur_axis, cur_start = axis, i
        elif prefix == "I":
            if cur_axis != axis:
                if cur_axis is not None:
                    spans.add((cur_axis, cur_start, i))
                cur_axis, cur_start = axis, i  # treat stray I as B
    if cur_axis is not None:
        spans.add((cur_axis, cur_start, len(label_seq)))
    return spans


def span_f1_per_axis(
    pred_seqs: list[list[str]], gold_seqs: list[list[str]], axis_set: list[str]
):
    """Compute precision/recall/F1 per axis and macro-F1.

    Returns (per_axis_dict, macro_f1) where per_axis_dict[axis] = (p, r, f1, tp, fp, fn).
    """
    tp = Counter(); fp = Counter(); fn = Counter()
    for pred, gold in zip(pred_seqs, gold_seqs):
        p_spans = labels_to_axis_spans(pred)
        g_spans = labels_to_axis_spans(gold)
        for axis, s, e in p_spans & g_spans:
            tp[axis] += 1
        for axis, s, e in p_spans - g_spans:
            fp[axis] += 1
        for axis, s, e in g_spans - p_spans:
            fn[axis] += 1

    per_axis: dict[str, tuple[float, float, float, int, int, int]] = {}
    f1s = []
    for axis in axis_set:
        t, fpx, fnx = tp[axis], fp[axis], fn[axis]
        prec = t / (t + fpx) if (t + fpx) > 0 else 0.0
        rec = t / (t + fnx) if (t + fnx) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        per_axis[axis] = (prec, rec, f1, t, fpx, fnx)
        # Only count axes that have at least one gold span in the eval set
        if (t + fnx) > 0:
            f1s.append(f1)
    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    return per_axis, macro_f1


# ── Evaluation ──────────────────────────────────────────────────────────────

def extract_canonical_labels(row) -> dict[str, str]:
    params = row["parameters_norm"]
    if not isinstance(params, dict):
        return {}
    out = {}
    for axis_info in params.values():
        if axis_info is None:
            continue
        label = axis_info["label"].strip()
        values = axis_info.get("values")
        if values is None or len(values) == 0:
            continue
        v_orig = (values[0].get("value") or "").strip()
        if v_orig:
            out[label] = v_orig
    return out


def evaluate(
    model: BIOTagger,
    dataloader: DataLoader,
    id_to_label: list[str],
    axis_set: list[str],
    normalizer: SpanNormalizer,
    long_idx: dict[str, dict],
    device: torch.device,
) -> dict:
    """Compute token_acc, macro span_f1, per-axis spans, and end-to-end query_acc."""
    model.eval()
    pred_label_seqs: list[list[str]] = []
    gold_label_seqs: list[list[str]] = []
    query_correct = 0
    query_total = 0
    token_correct = 0
    token_total = 0

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attn = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            logits = model(input_ids, attn)  # (B, T, num_labels)
            preds = logits.argmax(dim=-1)

            mask = labels != IGNORE_INDEX
            token_correct += int((preds[mask] == labels[mask]).sum().item())
            token_total += int(mask.sum().item())

            preds_cpu = preds.cpu().tolist()
            labels_cpu = labels.cpu().tolist()
            for i in range(len(preds_cpu)):
                pred_seq = []
                gold_seq = []
                for j, lid in enumerate(labels_cpu[i]):
                    if lid == IGNORE_INDEX:
                        pred_seq.append("O")
                        gold_seq.append("O")
                    else:
                        pred_seq.append(id_to_label[preds_cpu[i][j]])
                        gold_seq.append(id_to_label[lid])
                pred_label_seqs.append(pred_seq)
                gold_label_seqs.append(gold_seq)

                # End-to-end query accuracy via the normalizer
                text = batch["texts"][i]
                offsets = batch["offsets"][i]
                pk = batch["parent_keys"][i]
                ik = batch["item_keys"][i]

                spans = decode_bio_spans(pred_seq, offsets, text)
                spans = merge_adjacent_same_axis(spans, text)
                pred_dict: dict[str, str | None] = {}
                seen = set()
                for axis, surface, _cs, _ce in spans:
                    if axis in seen:
                        continue
                    canonical = normalizer.normalize(axis, surface, pk)
                    pred_dict[axis] = canonical
                    seen.add(axis)

                long_row = long_idx.get(ik)
                if long_row is None:
                    continue
                gold_dict = extract_canonical_labels(long_row)
                # Compare on the axes that the schema defines for this parent
                schema_axes = normalizer.canonical_values
                # build expected dict restricted to known axes
                schema_axis_keys = list(gold_dict.keys())
                ok = True
                for axis in schema_axis_keys:
                    if pred_dict.get(axis) != gold_dict[axis]:
                        ok = False
                        break
                query_total += 1
                if ok:
                    query_correct += 1

    per_axis, macro_f1 = span_f1_per_axis(pred_label_seqs, gold_label_seqs, axis_set)
    model.train()
    return {
        "token_acc": token_correct / token_total if token_total else 0.0,
        "span_f1": macro_f1,
        "per_axis_f1": {a: per_axis[a][2] for a in axis_set},
        "query_acc": query_correct / query_total if query_total else 0.0,
    }


# ── Train ───────────────────────────────────────────────────────────────────

def train(args):
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading data...")
    df = pd.read_parquet(data_dir / "bio_training_data.parquet")
    with open(data_dir / "bio_label_inventory.json", encoding="utf-8") as f:
        label_inventory: dict[str, int] = json.load(f)
    id_to_label = [None] * len(label_inventory)
    for label, idx in label_inventory.items():
        id_to_label[idx] = label
    axis_set = sorted({lbl[2:] for lbl in label_inventory if lbl != "O" and lbl.startswith("B-")})

    schema_path = data_dir / "OEB_concept_schema.json"
    long_df = pd.read_parquet(data_dir / "OEB_long_norm.parquet")
    long_idx = {r["item_key"]: r for _, r in long_df.iterrows()}
    normalizer = SpanNormalizer(schema_path)

    if args.sanity > 0:
        logger.info("SANITY MODE: using %d samples", args.sanity)
        df = df.head(args.sanity)

    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    if len(val_df) == 0:
        logger.info("Sanity mode: no rows in val split — using train as val for diagnostics")
        val_df = train_df.head(min(20, len(train_df)))
    logger.info("Train: %d, Val: %d", len(train_df), len(val_df))

    tokenizer = AutoTokenizer.from_pretrained(args.encoder)
    train_ds = BIOTaggerDataset(train_df, label_inventory, tokenizer)
    val_ds = BIOTaggerDataset(val_df, label_inventory, tokenizer)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)
    val_dl = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate_fn)

    device = torch.device(args.device)
    logger.info("Initializing model on %s...", device)
    model = BIOTagger(args.encoder, num_labels=len(label_inventory))
    model.to(device)
    num_params = sum(p.numel() for p in model.parameters())
    logger.info("Model: %d labels, %.1fM parameters", len(label_inventory), num_params / 1e6)

    if args.freeze_encoder:
        for param in model.encoder.parameters():
            param.requires_grad = False
        trainable = [p for p in model.parameters() if p.requires_grad]
        trainable_count = sum(p.numel() for p in trainable)
        logger.info("Encoder FROZEN. Trainable params: %.1fK (head only)", trainable_count / 1e3)
    else:
        trainable = model.parameters()

    optimizer = torch.optim.AdamW(trainable, lr=args.lr, weight_decay=0.01)
    total_steps = max(1, len(train_dl) * args.epochs)
    warmup_steps = max(1, int(0.1 * total_steps))
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    use_amp = args.device.startswith("cuda")
    if use_amp:
        try:
            scaler = torch.amp.GradScaler("cuda")
        except (TypeError, AttributeError):
            scaler = torch.cuda.amp.GradScaler()
    else:
        scaler = None

    # Class-weighted CE per protocol §4.6: "Use a weighted loss only if epoch 1
    # evaluation shows the model collapsing to all-O." The flag downweights the
    # majority O class; default 1.0 leaves CE unweighted.
    if args.class_weight_o != 1.0:
        weights = torch.ones(len(label_inventory), device=device)
        weights[label_inventory["O"]] = args.class_weight_o
        ce = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX, weight=weights)
        logger.info("Class-weighted CE: O weight = %.2f", args.class_weight_o)
    else:
        ce = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX)

    best_span_f1 = 0.0
    training_log = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        epoch_steps = 0
        t0 = time.time()

        for batch in train_dl:
            input_ids = batch["input_ids"].to(device)
            attn_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()

            if use_amp:
                with torch.cuda.amp.autocast():
                    logits = model(input_ids, attn_mask)
                    loss = ce(logits.view(-1, logits.size(-1)), labels.view(-1))
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                logits = model(input_ids, attn_mask)
                loss = ce(logits.view(-1, logits.size(-1)), labels.view(-1))
                loss.backward()
                optimizer.step()

            scheduler.step()
            epoch_loss += loss.item()
            epoch_steps += 1

        avg_loss = epoch_loss / max(epoch_steps, 1)
        elapsed = time.time() - t0

        metrics = evaluate(
            model, val_dl, id_to_label, axis_set, normalizer, long_idx, device
        )
        logger.info(
            "Epoch %d/%d — loss: %.4f, token_acc: %.1f%%, span_f1: %.1f%%, query_acc: %.1f%%, time: %.0fs",
            epoch, args.epochs, avg_loss,
            100 * metrics["token_acc"],
            100 * metrics["span_f1"],
            100 * metrics["query_acc"],
            elapsed,
        )

        training_log.append({
            "epoch": epoch,
            "loss": avg_loss,
            "token_acc": metrics["token_acc"],
            "span_f1": metrics["span_f1"],
            "query_acc": metrics["query_acc"],
            "per_axis_f1": metrics["per_axis_f1"],
            "time_s": elapsed,
        })

        # Always save the latest epoch so downstream code has *some* checkpoint
        # to load; track the best span_f1 separately.
        torch.save(model.state_dict(), output_dir / "model.pt")
        if metrics["span_f1"] > best_span_f1:
            best_span_f1 = metrics["span_f1"]
            torch.save(model.state_dict(), output_dir / "model_best.pt")
            logger.info("  New best checkpoint (span_f1=%.1f%%)", 100 * best_span_f1)

    config = {
        "encoder_name": args.encoder,
        "label_inventory_path": str(data_dir / "bio_label_inventory.json"),
        "num_labels": len(label_inventory),
        "best_val_span_f1": best_span_f1,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "freeze_encoder": args.freeze_encoder,
    }
    with open(output_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    with open(output_dir / "training_log.json", "w", encoding="utf-8") as f:
        json.dump(training_log, f, indent=2)

    logger.info("Training complete. Best val span_f1: %.1f%%", 100 * best_span_f1)
    logger.info("Outputs saved to %s", output_dir)


def main():
    parser = argparse.ArgumentParser(description="Train shared BIO tagger")
    parser.add_argument("--data-dir", type=str, default=str(DATA_DIR))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--encoder", type=str, default=DEFAULT_ENCODER)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--freeze-encoder", action="store_true")
    parser.add_argument("--sanity", type=int, default=0,
                        help="If > 0, use only this many rows for a CPU sanity check")
    parser.add_argument("--class-weight-o", type=float, default=1.0,
                        help="CE weight for the O class. Default 1.0 = unweighted. "
                             "Set <1 (e.g. 0.1) only if the model collapses to all-O "
                             "(protocol §4.6 fallback).")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
