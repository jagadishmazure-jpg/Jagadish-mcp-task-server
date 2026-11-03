# 05 — Built vs planned

| Area | Item | Status | Evidence |
|---|---|---|---|
| Data | SQLite table, CHECK constraints, 4 functions | Built, tested | `tests/test_database.py` (11 tests) |
| Server | 3 FastMCP tools, streamable HTTP | Built, tested | `tests/test_tools.py` (17), `tests/test_http.py` (5) |
| Least privilege | No edit/delete tool, smuggled-argument refusal | Built, tested | `tests/test_least_privilege.py` (3) |
| Injection | SQL, status, id, stored-text cases | Built, tested | `tests/test_prompt_injection.py` (9) |
| Agent | LangChain `create_agent`, adapters, `InMemorySaver`, offline fake model | Built, tested | `tests/test_agent_e2e.py` (6) |
| Auth | Optional bearer token, loopback default | Built, tested | `tests/test_http.py` |
| Clients | `client.py` | Built, run over real HTTP | `results/demo_output.txt` (measured) |
| IDE | VS Code `mcp.json`, Codex `config.toml.example` | Written, not run in CI | Needs an IDE session |
| Real model | `ChatOpenAI` path | Written, not run (no key by design) | — |
| CI | ruff, pytest with printed total, docs check, brand check, gitleaks, CodeQL | Built | `.github/workflows/` |
| Resources / prompts | `tasks://summary`, planning prompt | Planned | — |
| Auth | OAuth 2.1 / Entra ID with scopes | Planned | — |
| Ops | Audit log, rate limiting, human approval tool | Planned | — |
| Cloud | Container deployment | Planned only — nothing deployed, nothing billable | — |

Test total: <!-- tests:51 -->51 (measured, `scripts/count_tests.py`).
