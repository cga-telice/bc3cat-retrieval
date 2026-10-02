"""Write the canonicalised query sets `OE_{base}__canon.json` — S9 work item 2 (transform C).

For each base: its dev records (test queries are never transformed), each `text` passed through the
canonicaliser built from `OE_texto.json`, nothing else changed. A sidecar `OE_{base}__canon.meta.json`
records the code commit, the corpus digest the canonicaliser was built from, and what C did: queries
touched, number words, unit spellings, conversions made and declined. T4 reads it.

    python src/query_rewrite/apply_canon.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from query_rewrite.canon import CORPUS, from_corpus  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402
from utils.run_context import S9_BASES  # noqa: E402
from utils.splits import load_split  # noqa: E402

DATA = REPO / "data" / "processed"


def main() -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "src"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit(f"src/ has uncommitted changes; commit the canonicaliser first:\n{dirty}")
    dev = load_split("dev")
    canon = from_corpus()
    for base in S9_BASES:
        records = [r for r in json.loads((DATA / f"OE_{base}.json").read_text(encoding="utf-8")) if r["parent_key"] in dev]
        totals: Counter = Counter()
        out_records = []
        for r in records:
            text, rep = canon.apply(r["text"])
            totals["touched"] += rep.touched()
            totals["changed"] += text != r["text"]
            for k in ("numbers", "units", "converted", "declined"):
                totals[k] += getattr(rep, k)
            out_records.append({**r, "text": text})
        out = DATA / f"OE_{base}__canon.json"
        payload = json.dumps(out_records, ensure_ascii=False, indent=2)
        if out.exists() and out.read_text(encoding="utf-8") != payload:
            raise SystemExit(f"{out.name} exists with other content; refusing to overwrite a set runs may stamp")
        out.write_text(payload, encoding="utf-8")
        meta = {"base": base, "transform": "canon", "code_commit": commit,
                "corpus": CORPUS.name, "corpus_sha256": sha256_file(CORPUS), "n": len(records), **totals}
        (DATA / f"OE_{base}__canon.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"written: {out.name} ({len(records):,} records; {totals['changed']:,} changed, "
              f"{totals['converted']} converted, {totals['declined']} declined)")


if __name__ == "__main__":
    main()
