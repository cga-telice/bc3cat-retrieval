"""`index_builders.bge_m3_colbert` after S2's streaming rewrite.

Two properties. The index lands where the resolver says it lives, next to the mapping and meta
the notebook writes — before S2 its two large files went to `index/{save_as}` instead. And the
streaming build writes exactly what the accumulate-then-write build wrote: same FP16 bytes,
offsets and FAISS centroids.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

faiss = pytest.importorskip("faiss")

from index_builders import bge_m3_colbert as colbert
from utils.run_context import load_run_context

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "bge_m3_colbert__OE.yaml"
D = 8


def _mats(texts):
    """Deterministic ragged token matrices, one per text, including an empty one."""
    out = []
    for t in texts:
        rng = np.random.default_rng(abs(hash(t)) % (2**32))
        n = 0 if t == "empty" else 1 + len(t) % 5
        out.append(rng.standard_normal((n, D)).astype(np.float32))
    return out


def _reference(texts):
    """The pre-S2 algorithm: accumulate every matrix, then write."""
    mats = _mats(texts)
    blob = b"".join(np.asarray(m, dtype=np.float16).tobytes(order="C") for m in mats)
    lengths = np.array([m.shape[0] for m in mats], dtype=np.int64)
    offsets = np.zeros(len(texts) + 1, dtype=np.int64)
    np.cumsum(lengths, out=offsets[1:])
    centroids = np.zeros((len(texts), D), dtype=np.float32)
    for i, L in enumerate(lengths):
        if L:
            centroids[i] = mats[i].mean(axis=0)
    faiss.normalize_L2(centroids)
    return blob, offsets, centroids


@pytest.fixture()
def built(tmp_path, monkeypatch):
    texts = [f"documento {i} " + "x" * (i % 7) for i in range(300)] + ["empty"]
    monkeypatch.setattr(
        colbert, "_encode_colbert_remote",
        lambda texts, **kw: _mats(texts),
    )
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    cfg["paths"]["index_root"] = str(tmp_path / "index")
    colbert.build(cfg, pd.DataFrame({"text_norm": texts}), "text_norm")
    return tmp_path, cfg, texts


def test_index_lands_in_the_resolver_directory(built, tmp_path):
    root, cfg, _ = built
    ctx = load_run_context(CONFIG, queryset=None, work_root=root, require_inputs=False)
    data = ctx.index_dir / cfg["io"]["data_dirname"]
    for name in ("token_mats.bin", "offsets.npy", "dim.json", "faiss.index"):
        assert (data / name).exists(), f"{name} not under {data}"
    assert not (root / "index" / cfg["method"]["save_as"]).exists()


def test_streaming_build_writes_what_the_accumulating_build_wrote(built):
    root, cfg, texts = built
    data = root / "index" / cfg["collection"] / cfg["method"]["save_as"] / "data"
    blob, offsets, centroids = _reference(texts)

    assert (data / "token_mats.bin").read_bytes() == blob
    np.testing.assert_array_equal(np.load(data / "offsets.npy"), offsets)
    index = faiss.read_index(str(data / "faiss.index"))
    np.testing.assert_array_equal(index.reconstruct_n(0, index.ntotal), centroids)
