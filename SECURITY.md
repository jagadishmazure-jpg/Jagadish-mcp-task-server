# Security policy

This is a learning project and reference build. It is not deployed anywhere.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security tab → "Report a vulnerability").
Do not open a public issue for security problems.

## What is in scope

- `server.py` tool validation, auth and bind behaviour
- `database.py` query safety
- CI workflows

## Secrets

The repo contains no secrets and needs none to run. Optional values (`OPENAI_API_KEY`, `MCP_AUTH_TOKEN`) are read
from environment variables only. CI runs gitleaks across the full git history.
