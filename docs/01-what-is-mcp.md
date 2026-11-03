# 01 — What is MCP? (cheat sheet)

**One line:** the Model Context Protocol is a standard way for an AI application to discover and call
capabilities that live somewhere else — your database, your file system, your ticketing system — without
writing a custom integration for every pairing of app and system.

## The three roles

```mermaid
flowchart LR
    H[Host<br/>the app the user sees<br/>e.g. Codex, VS Code, your agent] --> C1[MCP client<br/>one per server connection]
    C1 <-->|JSON-RPC 2.0| S1[MCP server<br/>this repo: task-server]
    S1 --> R[(Your system<br/>SQLite tasks)]
```

| Role | What it does | In this repo |
|---|---|---|
| **Host** | The application holding the model and the conversation | `langchain_client.py`, Codex, VS Code |
| **Client** | Keeps one connection to one server, speaks the protocol | `fastmcp.Client` |
| **Server** | Publishes capabilities and runs them | `server.py` |

## The three things a server can offer

| Primitive | Who decides to use it | Think of it as | Example |
|---|---|---|---|
| **Tools** | The **model** chooses to call them | Functions with side effects | `create_task`, `update_task_status` |
| **Resources** | The **application** chooses to load them | Read-only documents by URI | `tasks://summary` (planned) |
| **Prompts** | The **user** picks them | Reusable message templates | "Plan my week" (planned) |

This repo uses tools only, because the lesson is about controlling what an agent can *do*.

## The life of one tool call

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    C->>S: initialize (protocol version, capabilities)
    S-->>C: server info + capabilities
    C->>S: tools/list
    S-->>C: name, description, inputSchema for each tool
    C->>S: tools/call {name, arguments}
    S-->>C: content + structuredContent (or isError)
```

The model never sees your Python. It sees the **name, description and JSON Schema** of each tool. Good names
and descriptions are therefore part of the interface, not decoration.

## Transports

| Transport | How it travels | Use it when | Watch out for |
|---|---|---|---|
| **stdio** | Host starts the server as a child process; messages on stdin/stdout | Local, single-user tools | Never print to stdout from the server; it corrupts the stream |
| **Streamable HTTP** | One HTTP endpoint (`/mcp`); POST for requests, optional SSE stream for server messages | Shared or remote servers; this repo | Bind address, auth, origin checks |
| **SSE (legacy)** | Separate SSE endpoint plus POST endpoint | Only for older clients | Replaced by streamable HTTP in newer spec versions |

## MCP vs plain function calling

| | Function calling | MCP |
|---|---|---|
| Where tools are defined | Inside each app's code | In a separate server, once |
| Who can use them | That one app | Any MCP-capable host |
| Discovery | Hard-coded list | `tools/list` at run time |
| Process boundary | Same process | Separate process or machine |
| Relationship | MCP **uses** function calling underneath: the host still hands the model a tool list | |

## Least privilege, in one picture

```mermaid
flowchart TB
    Q["User: 'change the description of Cooking'"] --> M{Is there a tool<br/>that edits descriptions?}
    M -- no --> R[Agent says it can't]
    M -- yes --> W[Agent edits it]
    style W fill:#fde2e2
    style R fill:#e2f7e2
```

The safest permission is the one you never publish. This server publishes no edit or delete tool, and a test
checks that the agent's request leaves the database unchanged.

## Words to know

- **JSON-RPC 2.0** — the message format (`id`, `method`, `params`, `result` / `error`).
- **inputSchema** — the JSON Schema for a tool's arguments, generated here from Python type hints.
- **structuredContent** — machine-readable result next to the text result.
- **Session** — a client-server connection after `initialize`; streamable HTTP tracks it with a session header.

Next: [`../LEARNING_GUIDE.md`](../LEARNING_GUIDE.md).
