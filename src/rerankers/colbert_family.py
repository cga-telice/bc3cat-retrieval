# /src/rerankers/colbert_family.py
"""Within-family ColBERT scores (S11 work item 1b).

Given a query and a concept, score **every** leaf of the concept with ColBERT MaxSim. The ColBERT arm only
scores the 256 documents its FAISS centroid search preselects, so a sibling outside that set has no score; the
two-stage arms need one for every sibling to order a family.

**Query encodings are taken in the reference run's own blocks.** The BGE-M3 server's ColBERT vectors depend on
which other texts share the request: the same query encoded alone and inside its run's block differed by up to
0.13 per component, and the resulting MaxSim by up to 0.31 (S11 work item 1b, measured on `stacked_texto`). So a
family score equals the ColBERT run's own score only if the query is encoded exactly as that run encoded it: the
run's full query list, in run order, in `search_batch`'s blocks (`DEFAULT_BATCH_SIZE`) and the remote client's
chunks. `build_colbert_family_cache.py` does that and nothing else.

**MaxSim is the searcher's arithmetic.** Per document block of `DOC_BLOCK`: the query and the block go to the GPU
in `DTYPE`, `einsum("qd,bld->bql")`, max over document tokens, sum over query tokens, then `float()`. Documents
are padded to `TD_CAP` by the searcher's `_stack_docs`. What changes is only that a family's blocks are built
once and kept on the GPU while all its queries are scored, instead of re-read from the memory map per query
(9.7 s per query on a 6,336-leaf family). **Every block is padded to `DOC_BLOCK` documents** with zero documents
(dropped from the result): the run scored full blocks (preselect 256 = two blocks of 128), and a partial block
takes a different fp16 kernel, which moved 8 of 43,446 compared `single_l2_texto` scores by one fp16 step
(0.125 at about 140). Padded, all 35,747 compared scores of that base matched; which documents share a full
block does not matter. `verify_against_run` holds every score to the run's.

Scores are stored per reference base (`FamilyScoreStore`, keyed by query text and concept). The two-stage arms read
them and **fail on a miss**: they never encode a query themselves, so they cannot score it under a different batch.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FamilyScoreStore:
    """Read-only view of the `.npz` files `build_colbert_family_cache` writes, one per reference base.

    Each file holds, per scored query: the SHA-256 of its text, its concept, and its family's scores in
    `doc_id` order (`offsets` delimit them). The family itself is not stored: it is the index's, and `require`
    checks the stored length against it."""

    def __init__(self, directory: Path, families: dict[str, np.ndarray]):
        self.dir = Path(directory)
        self._fam = families
        self._d: dict[tuple[str, str], np.ndarray] = {}
        self.files = sorted(self.dir.glob("*.npz"))
        for f in self.files:
            z = np.load(f, allow_pickle=False)
            for i, (h, c) in enumerate(zip(z["text_sha"], z["concept"])):
                sc = z["scores"][z["offsets"][i] : z["offsets"][i + 1]]
                key = (str(h), str(c))
                if key in self._d and not np.array_equal(self._d[key], sc):
                    raise ValueError(f"{f.name}: a different score for a query already stored (concept {c})")
                self._d[key] = sc

    def require(self, text: str, concept: str):
        sc = self._d.get((text_sha(text), concept))
        if sc is None:
            raise KeyError(f"no ColBERT family score for concept {concept} and this query; build the cache first")
        fam = self._fam[concept]
        if len(fam) != len(sc):
            raise ValueError(f"{concept}: stored scores do not match the index's family size")
        return fam, sc

    def __len__(self) -> int:
        return len(self._d)


def write_store(path: Path, texts: list[str], scored) -> int:
    """Write every (query, concept) score in `scored` (per query: None or {concept: (doc_ids, scores)})."""
    hs, cs, offs, parts = [], [], [0], []
    for t, got in zip(texts, scored):
        for c, (_, sc) in sorted((got or {}).items()):
            hs.append(text_sha(t)); cs.append(c); parts.append(np.asarray(sc, dtype=np.float32))
            offs.append(offs[-1] + len(sc))
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, text_sha=np.asarray(hs), concept=np.asarray(cs),
                        offsets=np.asarray(offs, dtype=np.int64),
                        scores=np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32))
    return len(hs)


def families_from_mapping(external_ids, item_to_parent: dict[str, str]) -> dict[str, np.ndarray]:
    """Concept → doc ids of its leaves in the index, ascending, from `external_ids` (row = doc_id)."""
    out: dict[str, list[int]] = {}
    for doc_id, key in enumerate(external_ids):
        p = item_to_parent.get(str(key))
        if p is not None:
            out.setdefault(p, []).append(doc_id)
    return {p: np.asarray(v, dtype=np.int64) for p, v in out.items()}


class _FamilyOnGPU:
    """A family's document blocks, built as `_maxsim_gpu_one` builds them, kept on the GPU."""

    def __init__(self, searcher, doc_ids: np.ndarray):
        from retrievers import bge_m3_colbert as cb
        self.doc_ids = doc_ids
        self.blocks = []
        self.sizes = []
        for s in range(0, len(doc_ids), cb.DOC_BLOCK):
            docs = [searcher._doc_tokens(int(i)) for i in doc_ids[s : s + cb.DOC_BLOCK]]
            Dnp, _ = cb._stack_docs(docs, cb.TD_CAP)
            if len(docs) < cb.DOC_BLOCK:
                Dnp = np.concatenate([Dnp, np.zeros((cb.DOC_BLOCK - len(docs),) + Dnp.shape[1:], dtype=Dnp.dtype)])
            self.sizes.append(len(docs))
            Dt = cb.torch.from_numpy(Dnp)
            Dt = Dt.to(device="cuda", dtype=cb.DTYPE) if cb.DTYPE is not None else Dt.to(device="cuda")
            if not searcher._already_norm:
                Dt = cb.F.normalize(Dt, p=2, dim=-1)
            self.blocks.append(Dt)

    def score(self, searcher, Q: np.ndarray) -> np.ndarray:
        """`_maxsim_gpu_one(Q, doc_ids)` over the kept blocks."""
        from retrievers import bge_m3_colbert as cb
        Qt = cb.torch.from_numpy(Q)
        Qt = Qt.to(device="cuda", dtype=cb.DTYPE) if cb.DTYPE is not None else Qt.to(device="cuda")
        if not searcher._already_norm:
            Qt = cb.F.normalize(Qt, p=2, dim=-1)
        out = []
        for Dt, n in zip(self.blocks, self.sizes):
            S = cb.torch.einsum("qd,bld->bql", Qt, Dt)
            out.append(S.amax(dim=2).sum(dim=1).float().detach().cpu().numpy()[:n])
            del S
        return np.concatenate(out, axis=0) if out else np.zeros((0,), dtype=np.float32)


def score_in_run_blocks(searcher, families: dict[str, np.ndarray], texts: list[str], concepts: list,
                        block: int | None = None, use_gpu: bool | None = None, log=None):
    """Per query, None or {concept: (doc_ids, scores)}, for the concepts listed in `concepts[i]` (empty: skip).

    `texts` must be the reference run's full query list in run order: it is encoded in `search_batch`'s blocks.
    Encoding comes first, block by block, keeping the scored queries' matrices; then each family is put on the GPU
    once and scored against every query that lists it (a family per block cost about 7 minutes a block on `texto_u`).
    Neither changes a score: encoding blocks are the run's, and a family's padded blocks are the same whoever asks."""
    from retrievers import bge_m3_colbert as cb
    if len(texts) != len(concepts):
        raise ValueError("texts and concepts differ in length")
    block = block or cb.DEFAULT_BATCH_SIZE
    if use_gpu is None:
        use_gpu = cb._HAS_TORCH and cb.torch.cuda.is_available()
    want_c = [tuple(sorted(set(c or ()))) for c in concepts]
    # Pass 1: encode in the run's blocks, keeping only the matrices of queries that are scored.
    mats: dict[int, np.ndarray] = {}
    for s in range(0, len(texts), block):
        want = [i for i in range(s, min(s + block, len(texts))) if want_c[i]]
        if not want:
            continue
        enc = searcher._encode_queries(texts[s : s + block])
        if len(enc) != min(block, len(texts) - s):
            raise ValueError("the encoder dropped texts (empty queries?); block alignment is lost")
        for i in want:
            mats[i] = enc[i - s]
        if log:
            log(f"encoded queries {s}..{min(s + block, len(texts)) - 1}")
    # Pass 2: one family at a time, put on the GPU once and scored against every query that needs it.
    out: list = [None] * len(texts)
    for c in sorted({c for cs in want_c for c in cs}):
        if c not in families:
            raise KeyError(f"{c}: no leaves of this concept in the ColBERT index")
        fam = families[c]
        onfam = [i for i in mats if c in want_c[i]]
        if use_gpu:
            g = _FamilyOnGPU(searcher, fam)
            for i in onfam:
                out[i] = out[i] or {}
                out[i][c] = (fam, g.score(searcher, mats[i]))
            del g
            cb.torch.cuda.empty_cache()
        else:
            for i in onfam:
                out[i] = out[i] or {}
                out[i][c] = (fam, np.asarray(searcher._maxsim_cpu_one(mats[i], fam), dtype=np.float32))
        if log:
            log(f"scored concept {c}: {len(onfam)} queries, {len(fam)} leaves")
    return out


def verify_against_run(scored, run_rows, atol: float = 0.0) -> dict:
    """Compare family scores with a ColBERT run's stored top-100 scores, query by query.

    `scored` (as `score_in_run_blocks` returns it) and `run_rows` are aligned; None entries are skipped. Every leaf
    of every scored family that is in the run's top 100 is compared. `atol` is 0: the design asks for the run's
    scores, not near them."""
    n_q = n_cmp = n_bad = 0
    worst = 0.0
    for got, row in zip(scored, run_rows):
        if not got:
            continue
        n_q += 1
        for doc_ids, scores in got.values():
            pos = {int(d): j for j, d in enumerate(doc_ids)}
            for c in row["candidates"]:
                j = pos.get(int(c["doc_id"]))
                if j is None:
                    continue
                n_cmp += 1
                diff = abs(float(scores[j]) - float(c["score"]))
                worst = max(worst, diff)
                if diff > atol:
                    n_bad += 1
    return {"queries": n_q, "compared": n_cmp, "mismatched": n_bad, "max_abs_diff": worst}
