# Agent guidance for zbs-researcher

Read `CLAUDE.md` and `.specify/memory/constitution.md` before non-trivial work.
For new features, use the repository-local Spec Kit workflow in
`.agents/skills/`; the active feature lives in `.specify/feature.json`.

Keep one unresolved product outcome active until it is implemented, explicitly
deferred, or blocked by a real owner decision. Do not start a second review,
history scan, or verification pass unless code changed, a check failed, or new
evidence identified a distinct risk. Existing Claude/Codex history is evidence,
not the current repository state; read the full archive only when the task asks
for history or a concrete gap cannot be resolved from live files.

Completion for a non-trivial change means: requested behavior, affected public
and operator documentation, focused tests, the full unittest suite, the
10-step self-test, and one final adversarial diff review. A green test candidate
is not a release. Merge, version bump, npm publication, marketplace update, and
real paid-provider calls remain separate outward actions requiring Nikita's
explicit approval.
