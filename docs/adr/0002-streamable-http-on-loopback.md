# ADR 0002 — Streamable HTTP, bound to 127.0.0.1

**Status:** accepted

**Context.** Several clients (script, agent, two IDEs) must share one server and one database at the same time.
stdio gives each host its own child process.

**Decision.** Use streamable HTTP on port 8000, bound to loopback by default, with an optional bearer token.

**Consequences.** One server serves all clients. Exposing it beyond the machine needs an explicit `MCP_HOST`
change, which the docs tie to TLS and real auth.
