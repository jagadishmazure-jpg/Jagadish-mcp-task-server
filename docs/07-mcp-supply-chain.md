# 07 — MCP server supply chain

Reference: [modelcontextprotocol/servers v2.5.0](https://github.com/modelcontextprotocol/servers/releases/tag/v2.5.0)
(published 18 November 2026). That release fixes eight vulnerabilities in three reference servers.

## The risk class

An MCP host starts servers from a config file. The usual line is a package runner (`npx`, `uvx`, `pipx`) plus a
package name. The server process then has the same account as the person who launched the host. Two things follow.

- **An unpinned name is a moving dependency.** `uvx mcp-server-git` with no version installs whatever the registry
  serves that day. A later release, or a replaced release, arrives with no review in this repo.
- **The server is not the three task tools.** A vulnerable reference server can act outside the job it was given.
  For `mcp-server-git` the class is **config-driven command execution**: Git, which the server runs, can follow
  settings stored in the repository and start other programs, or return file contents from outside the checkout.
  For `@modelcontextprotocol/server-filesystem` the class is a check-then-use gap on directory listings. For
  `@modelcontextprotocol/server-everything` the class is a private-address check that treated a NAT64 address as
  public. A request could then be delivered to an internal host.

This page names those classes and the fixed versions. It does not describe how to build a repository that trips
them. Upstream limits that the release still leaves open: on Windows, a filesystem listing is not tied back to the
directory that passed the allow check, and after a git tool writes files the server does not run its repository
confinement check a second time.

## Fixed versions

| Package | Do not stay on | Floor |
|---|---|---|
| `mcp-server-git` | any calendar release on or before 11 November 2026 | `2026.11.18` |
| `@modelcontextprotocol/server-filesystem` | semver older than the floor, and every date-stamped npm release (the `2025.*` and `2026.*` lines) | `2.4.0` |
| `@modelcontextprotocol/server-everything` | `2.3.0` and older | `2.3.1` |

`mcp-server-git` is calendar-versioned, so the floor is a date. The npm servers switched from date stamps to
semantic versions. Resolvers sort `2.4.0` earlier than a `2026.*` stamp, so "newest" will not leave a date stamp.
Type the semantic version in the install spec.

```bash
uvx --from mcp-server-git==2026.11.18 mcp-server-git
npm install --save-exact @modelcontextprotocol/server-filesystem@2.4.0
npm install --save-exact @modelcontextprotocol/server-everything@2.3.1
```

Those commands are the upgrade for a project that already chose the package. `--save-exact` writes a pin with no
caret. This repository does not run them.

## What this repository uses

Searched manifests (`pyproject.toml`, `uv.lock`) and client configs (`mcp.json`, `.vscode/mcp.json`,
`codex/config.toml.example`). None of them depend on `mcp-server-git`, `@modelcontextprotocol/server-filesystem`,
or `@modelcontextprotocol/server-everything`. There was nothing to upgrade.

The only configured server is the first-party task server, HTTP on `http://127.0.0.1:8000/mcp`. Its code is this
repo. The Python packages `mcp` and `fastmcp` are the SDK and the framework, not those reference servers, and they
stay ranged in `pyproject.toml` with exact hashes in `uv.lock` (`uv sync --locked`).

## The gate

`security/mcp-server-allowlist.json` is the list of servers this repo is allowed to configure or depend on.
`scripts/mcp_supply_chain_check.py` reads that file and fails the process when any of these are true:

- An MCP client entry (`mcp.json`, `.mcp.json`, or a TOML file with `[mcp_servers`) is missing from the allowlist,
  points at a different URL, or launches a command that is not an exact package pin (or an argv copied exactly
  into the allowlist).
- A dependency named `mcp-server-*` or `@modelcontextprotocol/server-*` (or any package the allowlist names) is a
  range, a bare name, `@latest`, a caret, a date version of an npm server above, or below the floor.
- `uv.lock` or `package-lock.json` records one of those packages without the same exact direct pin.
- `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, or `Pipfile.lock` names one. Those files are not accepted as the
  pin.
- The allowlist floors differ from the versions in the table, or an allowlist entry itself is below the floor.

The floors live in the script as well as the JSON file. Editing only the JSON cannot approve `mcp-server-git`
`2026.11.11` or a filesystem date version.

CI job `mcp-supply-chain` in `.github/workflows/ci.yml` runs the script with the system Python. The script is
stdlib only: the job does not install packages and does not call a registry. `tests/test_mcp_supply_chain.py`
covers the same rules on temporary fixtures. The tests do not execute the commands they write down.

## Adding a server later

1. Pin an exact release at or above the floor. For the npm servers, do not use a `2025.*` or `2026.*` date version.
2. Add one allowlist object with the same id the config uses, the package name, and that version.
3. Keep the client args and the manifest on that same version. A range plus a lockfile is not enough.
4. Let CI fail if any of those drift.

Example shape, not enabled in this repo:

```json
{
  "id": "filesystem",
  "transport": "stdio",
  "package": "@modelcontextprotocol/server-filesystem",
  "version": "2.4.0"
}
```

```json
{
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem@2.4.0"]
    }
  }
}
```

## What the gate does not do

It does not install the package, talk to a registry, or watch the pin after it is committed. A pinned release can
still have its own bugs. It does not scan prose: a mention in this file is not a dependency. It does not replace
the least-privilege controls on the task server.
