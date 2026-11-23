# ADR 0004 — Pin and allowlist every MCP server

**Status:** accepted

**Context.** An MCP host starts servers from configuration, usually by package name, and the process runs as the
user. An unpinned name tracks the registry. [modelcontextprotocol/servers v2.5.0](https://github.com/modelcontextprotocol/servers/releases/tag/v2.5.0)
fixed eight vulnerabilities in three reference servers, including config-driven command execution in
`mcp-server-git` (fixed at 2026.11.18) and a directory-listing gap in `@modelcontextprotocol/server-filesystem`
(fixed at 2.4.0).

**Decision.** The only approved server is the first-party task server at `http://127.0.0.1:8000/mcp`. Any other
server has to be added to `security/mcp-server-allowlist.json` at one exact version that meets the floors in that
file. CI rejects an unpinned spec, a server that is not on the list, and a pin below those floors.

**Consequences.** Adding a reference server is a reviewed change to the allowlist and the manifest together. The
check reads files only. It does not install or run the server. Detail: [`docs/07-mcp-supply-chain.md`](../07-mcp-supply-chain.md).
