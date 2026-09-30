"""The D-004 pantry artefacts, flagged two ways: from the text, and from upstream's sidecar.

S3 flagged them from the text alone (`build_overlap.has_doubled_token`, `has_topo_drift`), because
the modifications sidecar had not been taken in. S6 work item 1 takes it in, and the design keeps the
text detector primary with the sidecar as its cross-check. This module is that cross-check, written
so it does not look at the detector's answer:

- **doubling, from the sidecar**: the rewrite's `new` value is located in the query's tokens, and the
  query is flagged when the token just before the span repeats the span's first token, the token just
  after repeats its last, or `new` itself holds an immediate repeat. That is the only way a rewrite
  can produce "tubos tubos" in a template that never says it (corpus rate 0 %, S3).
- **drift, from the sidecar**: a rewrite whose `new` says *topograf-* and whose `original` does not.

A query whose `new` cannot be located in its own tokens is returned as `None`: unknown, not clean.
So is any rewrite whose `new` is a template (it holds `$` / `%` placeholders, as every L3 rewrite
does): its literal tokens meet the placeholder values only at render time, so the sidecar alone
cannot say whether they collide, and placeholder names ("$L(b,%C). $L(c,%C)") tokenise into repeats
that are not in any query. The sidecar therefore cross-checks L1 and L2 rewrites; L3's doubling rests
on the text detector alone, and S6's T5 says so.
"""

from __future__ import annotations

import json
from pathlib import Path

from utils.build_overlap import has_doubled_token, has_topo_drift
from utils.corpus_prep import normalize_text, tokenize_words


def load_sidecar(path: Path) -> dict[str, list[dict]]:
    """`item_key` → its list of modification records."""
    with open(path, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    out = {r["item_key"]: r["modifications"] for r in rows}
    if len(out) != len(rows):
        raise ValueError(f"{path.name}: duplicate item_key")
    return out


def _tokens(text: str) -> list[str]:
    return tokenize_words(normalize_text(text))


def _find(needle: list[str], hay: list[str]) -> list[int]:
    n = len(needle)
    return [i for i in range(len(hay) - n + 1) if hay[i:i + n] == needle] if n else []


def sidecar_doubling(query_text: str, modifications: list[dict]) -> bool | None:
    """Did an applied rewrite put a token next to its own copy? `None` if no span could be located."""
    q = _tokens(query_text)
    located = False
    for mod in modifications:
        if mod.get("status") != "applied":
            continue
        raw = str(mod.get("new") or "")
        if "$" in raw or "%" in raw:
            return None
        new = _tokens(raw)
        if not new:
            continue
        if any(new[i] == new[i + 1] for i in range(len(new) - 1)):
            return True
        for i in _find(new, q):
            located = True
            j = i + len(new)
            if (i > 0 and q[i - 1] == new[0]) or (j < len(q) and q[j] == new[-1]):
                return True
    return False if located else None


def sidecar_topo(modifications: list[dict]) -> bool:
    return any(
        m.get("status") == "applied"
        and "topograf" in str(m.get("new") or "").lower()
        and "topograf" not in str(m.get("original") or "").lower()
        for m in modifications
    )


def text_flags(query_text: str, gold_text: str) -> dict[str, bool]:
    """S3's detector, unchanged: the primary flag (S6 design)."""
    return {"doubled": has_doubled_token(query_text), "topo": has_topo_drift(query_text, gold_text)}
