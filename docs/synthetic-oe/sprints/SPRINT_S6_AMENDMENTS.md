# Sprint S6 — amendments

Record, append-only (D-045). The amendments to [`SPRINT_S6_DESIGN.md`](SPRINT_S6_DESIGN.md), frozen at
`8abf24f` (2026-09-30). One row per change made after the freeze, dated, justified, and with its effect on claims.
Rows are never edited or deleted; a correction is a new row.

| Date | What changed | Why | Effect on claims |
|---|---|---|---|
| 2026-09-30 | **A1 — work item 2 as executed.** Nothing was *added* to the container: `bc3cat-s3` already holds `statsmodels` 0.14.1 and `matplotlib` 3.8.4 from its base image. They are pinned in code (`src/utils/analysis_stack.py`, with `patsy`, `scipy`, `numpy`, `pandas`), `require()` refuses any other versions and `stamp()` goes into every S6 table's sources block. The container has no `pytest` (the suite runs on the host, as in S3–S5), so the two container-only checks in `tests/test_analysis_stack.py` (pins match; the M0 shape fits with a nested variance component) were run by direct call in the container and passed. Full `pip freeze` of the container saved to `logs/S6/pip_freeze_bc3cat-s3_20260930.txt` (git-ignored; SHA-256 `42cdb9b1993c9c92`) | The design said "add"; the packages were already there, and installing pytest would add a package the design did not name | None. No package moved; the retrieval stack is D-034's (`transformers` 4.57.6, `sentence-transformers` 3.4.1) |
