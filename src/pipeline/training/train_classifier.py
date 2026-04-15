"""Training script for the multi-head E5 classifier (Stage 2).

Loads classifier_training_data.parquet + classifier_label_encoders.json,
fine-tunes intfloat/multilingual-e5-base with per-(group, axis) heads.

Usage::

    python -m src.pipeline.training.train_classifier
    python -m src.pipeline.training.train_classifier --epochs 5 --batch-size 32
    python -m src.pipeline.training.train_classifier --device cuda --lr 2e-5
    python -m src.pipeline.training.train_classifier --sanity 100
"""

import argparse
import json
import logging
import time
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

from src.pipeline.param_extractor_classifier import (
    MultiHeadClassifier,
    HEAD_SEP,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


class ClassifierDataset(Dataset):
    """Dataset yielding tokenized queries + target indices for active heads."""

    def __init__(self, df: pd.DataFrame, label_encoders: dict, tokenizer, max_length=512):
        self.queries = df["query_text"].tolist()
        self.parent_keys = df["parent_key"].tolist()
        self.labels_raw = [json.loads(x) for x in df["labels"].tolist()]
        self.label_encoders = label_encoders
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.queries)

    def __getitem__(self, idx):
        query = f"query: {self.queries[idx]}"
        parent_key = self.parent_keys[idx]
        labels_dict = self.labels_raw[idx]

        encoding = self.tokenizer(
            query,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )

        # Build target indices for each head of this parent_key
        targets = {}
        axes = self.label_encoders.get(parent_key, {})
        for axis_label, val_map in axes.items():
            head_key = f"{parent_key}{HEAD_SEP}{axis_label}"
            value = labels_dict.get(axis_label)
            if value is not None and value in val_map:
                targets[head_key] = val_map[value]
            else:
                targets[head_key] = 0  # null class

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "parent_key": parent_key,
            "targets": targets,
        }


def collate_fn(batch):
    """Custom collate: stack tensors, collect targets as list of dicts."""
    return {
        "input_ids": torch.stack([b["input_ids"] for b in batch]),
        "attention_mask": torch.stack([b["attention_mask"] for b in batch]),
        "parent_keys": [b["parent_key"] for b in batch],
        "targets": [b["targets"] for b in batch],
    }


def compute_loss(logits_dict, targets_list, device):
    """Sum of cross-entropy over all active heads across the batch."""
    ce = nn.CrossEntropyLoss()
    total_loss = torch.tensor(0.0, device=device)
    count = 0
    for i, targets in enumerate(targets_list):
        for head_key, target_idx in targets.items():
            if head_key in logits_dict:
                logit = logits_dict[head_key][i].unsqueeze(0)
                target = torch.tensor([target_idx], device=device)
                total_loss = total_loss + ce(logit, target)
                count += 1
    if count > 0:
        total_loss = total_loss / count
    return total_loss


def evaluate(model, dataloader, label_encoders, device):
    """Compute per-axis and per-query accuracy on a dataset."""
    model.eval()
    correct_axes = 0
    total_axes = 0
    correct_queries = 0
    total_queries = 0

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attn_mask = batch["attention_mask"].to(device)

            # Collect all needed head keys
            all_head_keys = set()
            for targets in batch["targets"]:
                all_head_keys.update(targets.keys())

            if not all_head_keys:
                continue

            logits_dict = model(input_ids, attn_mask, list(all_head_keys))

            for i, targets in enumerate(batch["targets"]):
                query_correct = True
                for head_key, target_idx in targets.items():
                    if head_key in logits_dict:
                        pred = logits_dict[head_key][i].argmax().item()
                        if pred == target_idx:
                            correct_axes += 1
                        else:
                            query_correct = False
                        total_axes += 1
                if not query_correct:
                    pass  # already set
                else:
                    correct_queries += 1
                total_queries += 1

    model.train()
    axis_acc = correct_axes / total_axes if total_axes > 0 else 0.0
    query_acc = correct_queries / total_queries if total_queries > 0 else 0.0
    return axis_acc, query_acc


def train(args):
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    logger.info("Loading data...")
    df = pd.read_parquet(data_dir / "classifier_training_data.parquet")
    with open(data_dir / "classifier_label_encoders.json", encoding="utf-8") as f:
        label_encoders = json.load(f)

    # Sanity mode: subsample
    if args.sanity > 0:
        logger.info("SANITY MODE: using %d samples", args.sanity)
        df = df.head(args.sanity)

    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    logger.info("Train: %d, Val: %d", len(train_df), len(val_df))

    # Tokenizer & datasets
    tokenizer = AutoTokenizer.from_pretrained(args.encoder)
    train_ds = ClassifierDataset(train_df, label_encoders, tokenizer)
    val_ds = ClassifierDataset(val_df, label_encoders, tokenizer)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)
    val_dl = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate_fn)

    # Model
    device = torch.device(args.device)
    logger.info("Initializing model on %s...", device)
    model = MultiHeadClassifier(args.encoder, label_encoders)
    model.to(device)
    num_heads = len(model.heads)
    num_params = sum(p.numel() for p in model.parameters())
    logger.info("Model: %d heads, %.1fM parameters", num_heads, num_params / 1e6)

    # Optimizer & scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_dl) * args.epochs
    warmup_steps = int(0.1 * total_steps)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    # Mixed precision
    use_amp = args.device.startswith("cuda")
    scaler = torch.amp.GradScaler("cuda") if use_amp else None

    # Training loop
    best_query_acc = 0.0
    training_log = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        epoch_steps = 0
        t0 = time.time()

        for batch in train_dl:
            input_ids = batch["input_ids"].to(device)
            attn_mask = batch["attention_mask"].to(device)

            # Collect all head keys needed for this batch
            all_head_keys = set()
            for targets in batch["targets"]:
                all_head_keys.update(targets.keys())

            if not all_head_keys:
                continue

            optimizer.zero_grad()

            if use_amp:
                with torch.amp.autocast("cuda"):
                    logits_dict = model(input_ids, attn_mask, list(all_head_keys))
                    loss = compute_loss(logits_dict, batch["targets"], device)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                logits_dict = model(input_ids, attn_mask, list(all_head_keys))
                loss = compute_loss(logits_dict, batch["targets"], device)
                loss.backward()
                optimizer.step()

            scheduler.step()
            epoch_loss += loss.item()
            epoch_steps += 1

        avg_loss = epoch_loss / max(epoch_steps, 1)
        elapsed = time.time() - t0

        # Validation
        if len(val_df) > 0:
            val_axis_acc, val_query_acc = evaluate(model, val_dl, label_encoders, device)
        else:
            val_axis_acc, val_query_acc = 0.0, 0.0

        logger.info(
            "Epoch %d/%d — loss: %.4f, val_axis_acc: %.1f%%, val_query_acc: %.1f%%, time: %.0fs",
            epoch, args.epochs, avg_loss,
            100 * val_axis_acc, 100 * val_query_acc, elapsed
        )

        training_log.append({
            "epoch": epoch,
            "loss": avg_loss,
            "val_axis_acc": val_axis_acc,
            "val_query_acc": val_query_acc,
            "time_s": elapsed,
        })

        # Save best checkpoint
        if val_query_acc > best_query_acc:
            best_query_acc = val_query_acc
            torch.save(model.state_dict(), output_dir / "model.pt")
            logger.info("  Saved best checkpoint (val_query_acc=%.1f%%)", 100 * val_query_acc)

    # Save config and log
    config = {
        "encoder_name": args.encoder,
        "label_encoders_path": str(data_dir / "classifier_label_encoders.json"),
        "num_heads": num_heads,
        "best_val_query_acc": best_query_acc,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
    }
    with open(output_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    with open(output_dir / "training_log.json", "w", encoding="utf-8") as f:
        json.dump(training_log, f, indent=2)

    logger.info("Training complete. Best val_query_acc: %.1f%%", 100 * best_query_acc)
    logger.info("Outputs saved to %s", output_dir)


def main():
    parser = argparse.ArgumentParser(description="Train multi-head E5 classifier")
    parser.add_argument("--data-dir", type=str, default="data/processed")
    parser.add_argument("--output-dir", type=str, default="models/e5_classifier")
    parser.add_argument("--encoder", type=str, default="intfloat/multilingual-e5-base")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--sanity", type=int, default=0,
                        help="If > 0, use only this many samples for a quick sanity check")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
