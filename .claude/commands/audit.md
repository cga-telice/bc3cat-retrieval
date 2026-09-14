---
description: Audit a closed sprint with a fresh, adversarial reviewer
argument-hint: <sprint-id>
---

Audit sprint **$1**.

Launch the `sprint-auditor` subagent. Give it **only**: the paths to
`docs/synthetic-oe/sprints/SPRINT_$1_REPORT.md` and `SPRINT_$1_DESIGN.md` (with its freeze
SHA), and the `runs/` paths the report names.

Do not give it your summary of the work, your view of whether the numbers are right, or any
context from this session beyond those paths. Its entire value is that it has not seen them.
If you are in the session that produced this sprint, stop and run this command in a new one.

When it returns, save its verdict **verbatim** to
`docs/synthetic-oe/sprints/SPRINT_$1_AUDIT.md`. Do not edit, soften, or summarise it — a
findings list rewritten by the person it concerns is not a finding list.

Then: on `FAIL`, reopen the sprint. On `PASS WITH FINDINGS`, resolve each finding or record
in the report why it is accepted. On `PASS`, mark the sprint `done` in the registry and
update `STATE.md`.
