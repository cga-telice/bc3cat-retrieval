"""Can every run in `runs/` still find the inputs it was stamped against? — S3 exit criterion 3.

A run's provenance is `{run_id, config SHA, code commit, query-set SHA-256}` and the branch's
first operating rule says a number without one does not exist. The unstated half of that rule is
that a stamp has to *resolve*: a digest naming a file no longer in the tree is not provenance,
it is a citation to a lost source.

This became concrete in S3 work item 1. The 2026-09-27 delivery replaces `OE_stacked_texto.json`,
and S2's three stacked runs are stamped against the *derived* table `7b0894e6…` rather than the
JSON — so keeping a copy of the JSON alone would have left them dangling. The superseded tables
are therefore kept under digest-stamped names, and this script is what demonstrates that the
keeping worked, rather than asserting it in prose.

    python src/utils/check_run_inputs.py            # all runs
    python src/utils/check_run_inputs.py --collection OE

Exit code 0 when every stamp resolves, 1 otherwise, so it can gate a sprint close.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "processed"
RUNS = REPO / "runs"
CONFIGS = REPO / "configs"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def data_digests() -> dict[str, list[str]]:
    """digest -> the files in data/processed carrying it (a digest can have several copies)."""
    out: dict[str, list[str]] = {}
    for path in sorted(DATA.iterdir()):
        if path.is_file():
            out.setdefault(sha256(path), []).append(path.name)
    return out


def commit_exists(commit: str) -> bool:
    try:
        subprocess.check_output(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{commit}^{{commit}}"],
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_run(meta_path: Path, digests: dict[str, list[str]]) -> list[str]:
    """Return a list of problems; empty means the run resolves."""
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    problems: list[str] = []

    for field in ("query_set_sha256", "corpus_sha256"):
        digest = meta.get(field)
        if not digest:
            problems.append(f"{field} absent from run_meta")
        elif digest not in digests:
            problems.append(f"{field} {digest[:16]}… not carried by any file in data/processed")

    # The config is resolved by name, then by digest: a renamed config that still hashes the
    # same is fine, an edited config with the recorded name is not.
    recorded = meta.get("config")
    config_sha = meta.get("config_sha256")
    if recorded and config_sha:
        candidate = CONFIGS / Path(recorded).name
        if not candidate.exists():
            problems.append(f"config {candidate.name} no longer in configs/")
        elif sha256(candidate) != config_sha:
            problems.append(
                f"config {candidate.name} has changed since the run "
                f"(stamped {config_sha[:16]}…, now {sha256(candidate)[:16]}…)"
            )

    commit = meta.get("code_commit")
    if not commit:
        problems.append("code_commit absent from run_meta")
    elif not commit_exists(commit):
        problems.append(f"code_commit {commit[:12]} not in this repository")

    if meta.get("code_dirty"):
        problems.append("run was made from a dirty tree (code_dirty: true)")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--collection", help="check only this collection, e.g. OE")
    args = ap.parse_args()

    root = RUNS / args.collection if args.collection else RUNS
    if not root.exists():
        print(f"nothing to check: {root} does not exist")
        return 0

    digests = data_digests()
    metas = sorted(root.rglob("run_meta.json"))
    failures: dict[str, list[str]] = {}

    for meta_path in metas:
        problems = check_run(meta_path, digests)
        run_id = str(meta_path.parent.relative_to(RUNS)).replace("\\", "/")
        status = "ok" if not problems else "FAIL"
        print(f"[{status:4s}] {run_id}")
        for problem in problems:
            print(f"         - {problem}")
        if problems:
            failures[run_id] = problems

    print()
    print(f"{len(metas) - len(failures)} of {len(metas)} runs resolve against the tree.")
    if failures:
        print(f"{len(failures)} do not; the stamps above name inputs that are gone or changed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
