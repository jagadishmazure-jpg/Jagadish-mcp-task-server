# ADR 0003 — Deterministic fake model for tests and CI

**Status:** accepted

**Context.** Tests that call a hosted model need a key, cost money, and give different answers run to run.

**Decision.** `FakeTaskModel` turns fixed phrasings into tool calls. `pick_model()` uses it whenever
`OPENAI_API_KEY` is unset.

**Consequences.** The full agent → MCP → SQLite path is tested on every push for free. Real-model behaviour,
especially under prompt injection, is **not** measured by these tests and is stated as a limitation.
