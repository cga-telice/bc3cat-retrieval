"""Freeze a run's metrics as the golden fixture — S1 work item 3.

runs/ was destroyed on 2026-09-14, so the migration of S1 had no baseline to be checked
against (D-022). The OEB feature tables survived, so the baseline is manufactured instead of
conceded: the harness is run **before** any notebook is migrated, and its metrics are frozen
here. After the migration the same run must reproduce them exactly.

What is frozen is `metrics_dual.json` and a stamp. The run's own artefacts are not: they run
to hundreds of megabytes and `runs/` is git-ignored. The stamp is what makes the comparison
mean anything — the digests of every input, the config, the code commit and the execution
parameters, so a later re-run can be shown to be the same run and not merely a similar one.

    python src/utils/freeze_fixture.py \
        --run runs/bm25_unigram_params__k1-0.60__b-0.35 \
        --config configs/bm25_unigram_params__k1-0.60__b-0.35.yaml \
        --into tests/fixtures/oeb_bm25_pre_migration \
        --param RANDOM_SAMPLE=16590 --param K=100 --param SAVE=True
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
METRICS = "metrics_dual.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run directory holding metrics_dual.json")
    ap.add_argument("--config", required=True)
    ap.add_argument("--into", required=True, help="fixture directory to write")
    ap.add_argument(
        "--param",
        action="append",
        default=[],
        help="execution parameter as NAME=VALUE, repeatable",
    )
    args = ap.parse_args()

    run_dir = (REPO / args.run).resolve()
    config_path = (REPO / args.config).resolve()
    into = (REPO / args.into).resolve()

    metrics_path = run_dir / METRICS
    if not metrics_path.exists():
        raise SystemExit(f"no {METRICS} under {run_dir}")

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    collection = cfg["collection"]
    inputs = {}
    for key, template in (cfg.get("inputs") or {}).items():
        resolved = str(template).format(
            data_dir=(cfg.get("paths") or {}).get("data_dir", ""), collection=collection
        )
        on_disk = REPO / resolved.removeprefix("/work/")
        inputs[key] = {
            "path": resolved,
            "sha256": sha256(on_disk) if on_disk.exists() else None,
        }

    stamp = {
        "what": "OEB baseline captured before the S1 notebook migration (D-022)",
        "run_id": run_dir.name,
        "collection": collection,
        "queryset": "resumen",
        "config": {"path": args.config, "sha256": sha256(config_path)},
        "code_commit": git("rev-parse", "HEAD"),
        "code_dirty": bool(git("status", "--porcelain")),
        "inputs": inputs,
        "execution": dict(p.split("=", 1) for p in args.param),
        "metrics_sha256": sha256(metrics_path),
    }

    into.mkdir(parents=True, exist_ok=True)
    (into / METRICS).write_text(metrics_path.read_text(encoding="utf-8"), encoding="utf-8")
    (into / "STAMP.json").write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")

    print(f"frozen into {into.relative_to(REPO)}")
    print(json.dumps(stamp, indent=2))


if __name__ == "__main__":
    main()
