# Security policy

This is a learning project and reference build. It is not deployed anywhere.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security tab → "Report a vulnerability").
Do not open a public issue for security problems.

## What is in scope

- `server.py` tool validation, auth and bind behaviour
- `database.py` query safety
- CI workflows
- MCP server pins and `security/mcp-server-allowlist.json`

## MCP server supply chain

This repo does not depend on the reference servers fixed in
[modelcontextprotocol/servers v2.5.0](https://github.com/modelcontextprotocol/servers/releases/tag/v2.5.0).
CI rejects an MCP server that is not exact-pinned and listed in the allowlist. Floors, if those packages are
added later: `mcp-server-git` 2026.11.18, `@modelcontextprotocol/server-filesystem` 2.4.0,
`@modelcontextprotocol/server-everything` 2.3.1. See [`docs/07-mcp-supply-chain.md`](docs/07-mcp-supply-chain.md).

## Secrets

The repo contains no secrets and needs none to run. Optional values (`OPENAI_API_KEY`, `MCP_AUTH_TOKEN`) are read
from environment variables only. CI runs gitleaks across the full git history.
