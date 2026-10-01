# Sprint S8 — amendments

Record, append-only (D-045). The amendments to [`SPRINT_S8_DESIGN.md`](SPRINT_S8_DESIGN.md), frozen at
`4f62d5a` (2026-10-01). One row per change made after the freeze, dated, justified, and with its effect on claims.
Rows are never edited or deleted; a correction is a new row.

| Date | What changed | Why | Effect on claims |
|---|---|---|---|
| 2026-10-01 | **A1. The container maps `host.docker.internal` to the bridge gateway for work item 2.** Before any run, from `bc3cat-s3`: `host.docker.internal` resolves to `fdc4:f303:9324::254` (IPv6) and `192.168.65.254` (IPv4), and neither reaches the BGE-M3 server (curl `000`, IPv4 forced included; Python `Errno 101 Network is unreachable`). `http://172.17.0.1:8800/health` answers `{"ok":true,…,"model":"BAAI/bge-m3"}`. For the duration of `logs/S8/run_s8.sh` the container's `/etc/hosts` maps `host.docker.internal` to `172.17.0.1`, as S7's second pass did (S7 A3); the script adds the line, checks health through the configured URL before any run, and removes the line on exit. | The design's risk row fixes that a reuse of S7's mapping is recorded here. Docker Desktop's host alias is still broken (STATE, 2026-10-01). | None. The mapping is environment, not code or config: the configs' `api_base` is unchanged and is the URL the runs use; no config SHA moves. |
