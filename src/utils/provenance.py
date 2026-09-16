"""The four-part stamp every number carries, produced by the harness.

The branch's first operating rule: a number in a report or the manuscript carries
`{run_id, config SHA, code commit, query-set SHA-256}`, and a number without a stamp does
not exist. The rule exists because the previous review cycle found three distinct query
samples reported as one — which no amount of care in writing the report would have caught,
because the report was written from memory of what had run.

So the stamp is computed at run time, from the files actually read, and written into the
run. A report quotes it; it never assembles it.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

#: The four parts the operating rule names. `code_dirty` rides along because a commit id
#: from a modified tree names code that was never committed.
STAMP_FIELDS = ("run_id", "config_sha256", "code_commit", "query_set_sha256")

REPO = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    """Digest a file, streaming: the feature tables run to tens of megabytes."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"cannot stamp what is not a file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def provenance_stamp(
    *, run_id: str, config_path: Path, query_path: Path, repo: Path | str = REPO
) -> dict:
    """The stamp for one run. Raises rather than writing a null digest.

    A stamp with a null in it looks stamped and proves nothing, which is worse than no stamp
    at all — so a file that cannot be digested stops the run instead of being recorded as
    unknown.
    """
    repo = Path(repo)
    try:
        code_commit = _git(repo, "rev-parse", "HEAD")
        code_dirty = bool(_git(repo, "status", "--porcelain", "--", "src", "configs"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        # A container without git, or a checkout without history: say so, rather than
        # inventing a commit id that would be quoted later as if it were one.
        code_commit = "unavailable"
        code_dirty = True

    return {
        "run_id": run_id,
        "config_sha256": sha256_file(config_path),
        "code_commit": code_commit,
        "code_dirty": code_dirty,
        "query_set_sha256": sha256_file(query_path),
    }
