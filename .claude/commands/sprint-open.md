---
description: Open a research sprint — verify preconditions, draft its design document, mark it active
argument-hint: <sprint-id>
---

Open sprint **$1** on `research/synthetic-oe`.

Do not start any experimental work in this command. Opening a sprint means agreeing on what
it will establish and how, and freezing that before results exist.

1. **Read** `docs/synthetic-oe/SPRINTS.md`, `STATE.md`, `DECISIONS.md`, and the sprint's
   entry in `RESEARCH_PLAN.md`. If $1 is not in the registry, it is an emergent sprint:
   assign the next free ID (backbone S14+, probe S91+), and ask which type it is before
   proceeding.
2. **Verify the entry state.** Every dependency sprint is `done`; every required artefact
   exists; every upstream delivery has landed and its digest is recorded. Check each one —
   do not take the registry's word for it. If something is missing, report it and stop.
3. **Draft the design document** at `docs/synthetic-oe/sprints/SPRINT_$1_DESIGN.md` from
   `_TEMPLATE_DESIGN.md`. Fill every section. For a probe, the stopping criterion is
   mandatory — a probe without one is not approved.
4. **Design constraints are written now, not later.** Which comparisons are paired, which
   population each effect is estimated on, what must not be compared with what, which
   caveats are carried in from the data. Writing them after results is how hypotheses drift.
5. **Present the design for approval.** Do not commit it unreviewed.
6. **On approval:** create `SPRINT_$1_AMENDMENTS.md` from `_TEMPLATE_AMENDMENTS.md` with its
   table empty, commit it with the design, record the commit SHA and date in both files,
   set the registry row to `active`, append the transition to the registry log, and update
   `STATE.md`.

From the freeze commit, the design is read-only. Changes go in `SPRINT_$1_AMENDMENTS.md`, dated
(D-045). The amendments file is a record: rows are appended, never edited.
