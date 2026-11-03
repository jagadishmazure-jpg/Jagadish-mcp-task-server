# 03 — Interview points (MCP)

Short answers first, then the detail. Repo proof is named so you can open it live.

## 30-second pitch

"I built an MCP server for a task list and used it from three different clients — a plain script, a
LangChain agent and IDE agents. The design choice I care about is least privilege: the server publishes three
tools only, so the agent physically cannot edit or delete data. Each rule has a test — <!-- tests:51 -->51 in
total, including prompt-injection cases and an HTTP run with token auth — and CI runs them with no API key."

## MCP vs function calling

| Question | Answer |
|---|---|
| Are they competitors? | No. Function calling is how a model asks for a tool. MCP is how tools are **packaged, discovered and served** so any host can use them. |
| What does MCP add? | A process boundary, run-time discovery (`tools/list`), a standard wire format (JSON-RPC 2.0), and reuse across hosts. |
| When is plain function calling enough? | One app, a few in-process functions, no reuse. |
| Cost of MCP? | Another process to run and secure, a network hop (measured here: median 4.30 ms per `list_tasks` over loopback, n=50, one run). |

## Transports

| | stdio | Streamable HTTP | SSE (legacy) |
|---|---|---|---|
| Process model | Host spawns server | Server runs on its own | Server runs on its own |
| Users | One | Many | Many |
| Auth | OS process boundary | HTTP auth (bearer / OAuth) | HTTP auth |
| Gotcha | Printing to stdout breaks the protocol | Bind address, origin checks | Two endpoints; superseded |
| This repo | — | Yes, `127.0.0.1:8000/mcp` | — |

## Tools, resources, prompts

- **Tools** — model-controlled actions. Here: `create_task`, `list_tasks`, `update_task_status`.
- **Resources** — app-controlled, read-only context by URI. Planned: `tasks://summary`.
- **Prompts** — user-chosen templates. Planned: a weekly planning prompt.
- Rule of thumb: if it changes state, it is a tool; if it is context to read, it is a resource.

## Security questions you will get

| Question | Answer with proof |
|---|---|
| How do you stop an agent doing too much? | Do not publish the capability. No edit/delete tool; `test_no_edit_or_delete_tool_exists`. |
| Prompt injection through stored data? | Task text is data; system prompt says so; the server enforces limits regardless. `test_injected_title_is_stored_verbatim_not_executed`. Honest limit: the offline model is rule-based, so this proves the server side, not real-model behaviour. |
| SQL injection? | Placeholders only plus `CHECK` constraints. `test_sql_injection_text_is_stored_as_plain_data`. |
| Argument smuggling? | Schemas have `additionalProperties: false`. `test_update_status_rejects_smuggled_description`. |
| Network exposure? | Loopback by default; bearer token optional; constant-time compare. `test_http_without_token_is_401`. |
| Secrets? | None in repo; env vars only; gitleaks over full history in CI. |
| What would you add for production? | OAuth 2.1 with scopes, audit log, rate limits, human approval for destructive tools, TLS. |

## Design trade-offs to mention

- **Factory `build_server(db_path)`** → every test gets an isolated server and database.
- **Validation twice** (schema + DB) → a bug in one layer does not become bad data.
- **Deterministic fake model** → CI without keys; the trade-off is that it does not test real-model judgment.
- **Pinned `mcp<2`** → the LangChain adapter still needs the 1.x SDK; pinning avoids a broken import.

## Likely follow-ups

1. *How does the model know what a tool does?* — Name, description and JSON Schema from `tools/list`.
2. *What happens on an invalid status?* — FastMCP rejects it against the enum before the function runs; the client gets `isError: true`.
3. *How would you add delete safely?* — A separate `request_task_deletion` tool that records intent, plus a human approval step that performs it.
4. *Stateful sessions over HTTP?* — Streamable HTTP keeps a session id header; the LangChain side keeps chat memory in the checkpointer by `thread_id`.
