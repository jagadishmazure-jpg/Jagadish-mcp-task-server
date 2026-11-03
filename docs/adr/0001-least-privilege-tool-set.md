# ADR 0001 — Publish three tools only

**Status:** accepted

**Context.** An agent can only misuse a capability it has been given. A generic `update_task(fields)` tool would be
shorter to write but would let the agent change anything.

**Decision.** Publish `create_task`, `list_tasks` and `update_task_status`. No edit-description, no delete.
`update_status` in the data layer only touches the `status` column.

**Consequences.** Users must edit descriptions another way. Adding a capability later is a deliberate, reviewed
change with its own denial tests.
