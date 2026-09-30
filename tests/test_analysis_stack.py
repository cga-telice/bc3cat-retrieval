"""S6 work item 2: the analysis stack is pinned, checked and stamped.

The pin check runs only where the stack is present (the sprint container); on a host without
`statsmodels` it skips, which is the point of `require()` failing loud there instead.
"""

from __future__ import annotations

import importlib.util

import pytest

from utils import analysis_stack


def test_stamp_names_every_pin():
    line = analysis_stack.stamp()
    for name, ver in analysis_stack.PINNED.items():
        assert f"`{name}` {ver}" in line


def test_require_refuses_a_mismatch(monkeypatch):
    fake = dict(analysis_stack.PINNED, statsmodels="0.0.0")
    monkeypatch.setattr(analysis_stack, "installed", lambda: fake)
    with pytest.raises(SystemExit, match="statsmodels 0.0.0"):
        analysis_stack.require()


@pytest.mark.skipif(importlib.util.find_spec("statsmodels") is None, reason="analysis stack absent (host)")
def test_this_interpreter_matches_the_pins():
    analysis_stack.require()


@pytest.mark.skipif(importlib.util.find_spec("statsmodels") is None, reason="analysis stack absent (host)")
def test_mixedlm_with_a_nested_variance_component_fits():
    """The M0 shape of the design fits on this stack: concept groups, leaf as a variance component."""
    import numpy as np
    import pandas as pd
    import statsmodels.formula.api as smf

    rng = np.random.default_rng(20260930)
    rows = []
    for c in range(12):
        u = rng.normal(0, 0.1)
        for leaf in range(6):
            v = rng.normal(0, 0.05)
            for t in ("a", "b"):
                rows.append({"concept": f"c{c}", "leaf": f"c{c}l{leaf}", "type": t,
                             "delta": (-0.3 if t == "a" else -0.1) + u + v + rng.normal(0, 0.2)})
    frame = pd.DataFrame(rows)
    fit = smf.mixedlm("delta ~ 0 + C(type)", frame, groups="concept",
                      vc_formula={"leaf": "0 + C(leaf)"}).fit(reml=True)
    assert fit.converged
    assert fit.fe_params["C(type)[a]"] < fit.fe_params["C(type)[b]"]
