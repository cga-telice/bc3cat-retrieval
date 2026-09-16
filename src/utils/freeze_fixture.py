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
    ap.add_argument(
        "--captured-at",
        help=(
            "the commit the run was produced at, when re-freezing an existing fixture. "
            "Without it the stamp would record today's HEAD as the capture commit, which "
            "for a fixture whose whole purpose is to predate the migration would be false."
        ),
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

    # Capture fields describe the run; frozen_at fields describe this invocation. They are
    # the same only the first time. On a re-freeze the capture fields are carried forward
    # from the previous stamp, and the stamp says they were carried rather than measured.
    previous = {}
    if (into / "STAMP.json").exists():
        previous = json.loads((into / "STAMP.json").read_text(encoding="utf-8"))

    captured_at = args.captured_at or previous.get("code_commit") or git("rev-parse", "HEAD")
    carried = bool(args.captured_at or previous.get("code_commit"))
    captured_dirty = previous.get("code_dirty", False) if carried else None
    stamp = {
        "what": "OEB baseline captured before the S1 notebook migration (D-022)",
        "run_id": run_dir.name,
        "collection": collection,
        "queryset": "resumen",
        "config": {"path": args.config, "sha256": sha256(config_path)},
        "code_commit": captured_at,
        "capture_fields": "carried forward from the previous stamp" if carried else "measured now",
        "frozen_at_commit": git("rev-parse", "HEAD"),
        # Only what can change the run counts: src/ and configs/. The fixture being written
        # is untracked at this moment and cannot count against itself, and an uncommitted
        # manuscript elsewhere in the tree says nothing about the number.
        "code_dirty": (
            captured_dirty
            if carried
            else bool(git("status", "--porcelain", "--", "src", "configs"))
        ),
        "inputs": inputs,
        "execution": dict(p.split("=", 1) for p in args.param),
        "metrics_sha256": sha256(metrics_path),
    }

    into.mkdir(parents=True, exist_ok=True)
    # newline="" so Windows does not translate LF to CRLF on the way out: a copy whose
    # bytes differ from the source digests to something the stamp does not name, which is
    # how the integrity chain gets a hole at both ends (audit F1).
    frozen = into / METRICS
    frozen.write_text(metrics_path.read_text(encoding="utf-8"), encoding="utf-8", newline="")

    # The frozen copy's own digest, not only the source's: without it nothing anchors the
    # file the tests actually read.
    stamp["frozen_metrics_sha256"] = sha256(frozen)
    (into / "STAMP.json").write_text(
        json.dumps(stamp, indent=2) + chr(10), encoding="utf-8", newline=""
    )

    print(f"frozen into {into.relative_to(REPO)}")
    print(json.dumps(stamp, indent=2))


if __name__ == "__main__":
    main()
