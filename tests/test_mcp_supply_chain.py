"""The supply-chain gate fails closed on unpinned or non-allowlisted MCP servers.

Fixtures are config and manifest text only. Nothing here installs a package or
starts a server.
"""

import json
from pathlib import Path

import pytest

from scripts.mcp_supply_chain_check import RELEASE_URL, check_root, main

ROOT = Path(__file__).resolve().parent.parent
FLOORS = {
    "mcp-server-git": "2026.11.18",
    "@modelcontextprotocol/server-filesystem": "2.4.0",
    "@modelcontextprotocol/server-everything": "2.3.1",
}


def _policy(servers: list[dict], floors: dict | None = None) -> str:
    body = {
        "schema": 1,
        "source": RELEASE_URL,
        "floors": FLOORS if floors is None else floors,
        "servers": servers,
    }
    return json.dumps(body, indent=2) + "\n"


def _write(
    root: Path, files: dict[str, str], servers: list[dict], floors: dict | None, allowlist: bool
) -> None:
    if allowlist:
        dest = root / "security" / "mcp-server-allowlist.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_policy(servers, floors))
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _git(version: str = "2026.11.18") -> dict:
    return {"id": "git", "transport": "stdio", "package": "mcp-server-git", "version": version}


def _filesystem(version: str = "2.4.0") -> dict:
    return {
        "id": "filesystem",
        "transport": "stdio",
        "package": "@modelcontextprotocol/server-filesystem",
        "version": version,
    }


def _everything(version: str = "2.3.1") -> dict:
    return {
        "id": "everything",
        "transport": "stdio",
        "package": "@modelcontextprotocol/server-everything",
        "version": version,
    }


def _http(url: str = "http://127.0.0.1:8000/mcp") -> dict:
    return {"id": "task-server", "transport": "http", "url": url}


CASES = [
    (
        "unpinned_uvx_git",
        {"mcp.json": json.dumps({"servers": {"git": {"command": "uvx", "args": ["mcp-server-git"]}}})},
        [],
        None,
        True,
        "without an exact version pin",
    ),
    (
        "unpinned_npx_filesystem",
        {
            "mcp.json": json.dumps(
                {
                    "servers": {
                        "filesystem": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                        }
                    }
                }
            )
        },
        [],
        None,
        True,
        "without an exact version pin",
    ),
    (
        "npx_latest",
        {
            "mcp.json": json.dumps(
                {
                    "servers": {
                        "filesystem": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-filesystem@latest"],
                        }
                    }
                }
            )
        },
        [],
        None,
        True,
        "without an exact version pin",
    ),
    (
        "npx_caret",
        {
            "mcp.json": json.dumps(
                {
                    "servers": {
                        "filesystem": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-filesystem@^2.4.0"],
                        }
                    }
                }
            )
        },
        [],
        None,
        True,
        "without an exact version pin",
    ),
    (
        "git_below_floor",
        {
            "mcp.json": json.dumps(
                {"servers": {"git": {"command": "uvx", "args": ["mcp-server-git==2026.11.11"]}}}
            )
        },
        [_git("2026.11.18")],
        None,
        True,
        "below the minimum safe version",
    ),
    (
        "filesystem_date_version",
        {
            "mcp.json": json.dumps(
                {
                    "servers": {
                        "filesystem": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-filesystem@2026.8.31"],
                        }
                    }
                }
            )
        },
        [_filesystem("2.4.0")],
        None,
        True,
        "date version",
    ),
    (
        "filesystem_not_allowlisted",
        {
            "mcp.json": json.dumps(
                {
                    "servers": {
                        "filesystem": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-filesystem@2.4.0"],
                        }
                    }
                }
            )
        },
        [],
        None,
        True,
        "not on the allowlist",
    ),
    (
        "filesystem_allowlisted",
        {
            "mcp.json": json.dumps(
                {
                    "servers": {
                        "filesystem": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-filesystem@2.4.0", "/tmp"],
                        }
                    }
                }
            )
        },
        [_filesystem()],
        None,
        True,
        None,
    ),
    (
        "git_allowlisted",
        {
            "mcp.json": json.dumps(
                {"servers": {"git": {"command": "uvx", "args": ["mcp-server-git==2026.11.18"]}}}
            )
        },
        [_git()],
        None,
        True,
        None,
    ),
    (
        "git_from_flag",
        {
            "mcp.json": json.dumps(
                {
                    "servers": {
                        "git": {
                            "command": "uvx",
                            "args": ["--from", "mcp-server-git==2026.11.18", "mcp-server-git"],
                        }
                    }
                }
            )
        },
        [_git()],
        None,
        True,
        None,
    ),
    (
        "everything_below_floor",
        {
            "mcp.json": json.dumps(
                {
                    "mcpServers": {
                        "everything": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-everything@2.3.0"],
                        }
                    }
                }
            )
        },
        [_everything("2.3.1")],
        None,
        True,
        "below the minimum safe version",
    ),
    (
        "everything_allowlisted",
        {
            "mcp.json": json.dumps(
                {
                    "mcpServers": {
                        "everything": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-everything@2.3.1"],
                        }
                    }
                }
            )
        },
        [_everything()],
        None,
        True,
        None,
    ),
    (
        "pyproject_range",
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.0.1"\n'
                'dependencies = ["mcp-server-git>=2026.11.18"]\n'
            )
        },
        [_git()],
        None,
        True,
        "not exact-pinned",
    ),
    (
        "pyproject_below_floor",
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.0.1"\n'
                'dependencies = ["mcp-server-git==2026.11.11"]\n'
            )
        },
        [_git()],
        None,
        True,
        "below the minimum safe version",
    ),
    (
        "pyproject_exact",
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.0.1"\n'
                'dependencies = ["mcp-server-git==2026.11.18"]\n'
            )
        },
        [_git()],
        None,
        True,
        None,
    ),
    (
        "pyproject_dev_group",
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.0.1"\ndependencies = []\n\n'
                "[dependency-groups]\ndev = ["
                '"mcp-server-git>=2026.11.18"]\n'
            )
        },
        [_git()],
        None,
        True,
        "not exact-pinned",
    ),
    (
        "lock_drift",
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.0.1"\n'
                'dependencies = ["mcp-server-git==2026.11.18"]\n'
            ),
            "uv.lock": '[[package]]\nname = "mcp-server-git"\nversion = "2026.12.1"\n',
        },
        [_git()],
        None,
        True,
        "but the direct pin is 2026.11.18",
    ),
    (
        "lock_without_direct_pin",
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.0.1"\ndependencies = []\n',
            "uv.lock": '[[package]]\nname = "mcp-server-git"\nversion = "2026.11.11"\n',
        },
        [],
        None,
        True,
        "without an exact direct pin",
    ),
    (
        "sdk_dependency_is_not_a_server",
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.0.1"\n'
                'dependencies = ["mcp>=1.24,<2", "fastmcp>=3.4,<4"]\n'
            ),
            "uv.lock": '[[package]]\nname = "mcp"\nversion = "1.30.0"\n',
        },
        [],
        None,
        True,
        None,
    ),
    (
        "unknown_http_server",
        {
            "mcp.json": json.dumps(
                {"servers": {"task-server": {"type": "http", "url": "http://127.0.0.1:8000/mcp"}}}
            )
        },
        [],
        None,
        True,
        "not on the allowlist",
    ),
    (
        "http_url_mismatch",
        {"mcp.json": json.dumps({"servers": {"task-server": {"url": "http://127.0.0.1:8000/mcp"}}})},
        [_http("http://127.0.0.1:9/mcp")],
        None,
        True,
        "does not match the allowlisted url",
    ),
    (
        "http_ok",
        {
            "mcp.json": json.dumps(
                {"servers": {"task-server": {"type": "http", "url": "http://127.0.0.1:8000/mcp"}}}
            )
        },
        [_http()],
        None,
        True,
        None,
    ),
    (
        "toml_http_ok",
        {"codex/config.toml": '[mcp_servers.task-server]\nurl = "http://127.0.0.1:8000/mcp"\n'},
        [_http()],
        None,
        True,
        None,
    ),
    (
        "package_json_caret",
        {"package.json": json.dumps({"dependencies": {"@modelcontextprotocol/server-filesystem": "^2.4.0"}})},
        [_filesystem()],
        None,
        True,
        "not exact-pinned",
    ),
    (
        "package_json_exact",
        {"package.json": json.dumps({"dependencies": {"@modelcontextprotocol/server-filesystem": "2.4.0"}})},
        [_filesystem()],
        None,
        True,
        None,
    ),
    (
        "package_lock_drift",
        {
            "package.json": json.dumps(
                {"dependencies": {"@modelcontextprotocol/server-filesystem": "2.4.0"}}
            ),
            "package-lock.json": json.dumps(
                {
                    "packages": {
                        "node_modules/@modelcontextprotocol/server-filesystem": {"version": "2.5.0"}
                    }
                }
            ),
        },
        [_filesystem()],
        None,
        True,
        "but the direct pin is 2.4.0",
    ),
    (
        "requirements_bare",
        {"requirements.txt": "mcp-server-git\n"},
        [_git()],
        None,
        True,
        "not exact-pinned",
    ),
    (
        "requirements_exact",
        {"requirements.txt": "# pinned on purpose\nmcp-server-git==2026.11.18\n"},
        [_git()],
        None,
        True,
        None,
    ),
    (
        "floors_drift",
        {},
        [],
        {"mcp-server-git": "2026.11.11"},
        True,
        "floors do not match",
    ),
    (
        "missing_allowlist",
        {},
        [],
        None,
        False,
        "allowlist is missing",
    ),
    (
        "opaque_shell",
        {"mcp.json": json.dumps({"servers": {"sh": {"command": "bash", "args": ["-c", "echo hi"]}}})},
        [],
        None,
        True,
        "without an exact package pin",
    ),
    (
        "exact_argv",
        {
            "mcp.json": json.dumps(
                {"servers": {"local": {"command": "uv", "args": ["run", "python", "server.py"]}}}
            )
        },
        [{"id": "local", "transport": "stdio", "command": "uv", "args": ["run", "python", "server.py"]}],
        None,
        True,
        None,
    ),
    (
        "allowlist_approves_old_git",
        {},
        [_git("2026.11.11")],
        None,
        True,
        "below the minimum safe version",
    ),
    (
        "yarn_lock_unsupported",
        {"yarn.lock": 'mcp-server-git@2026.11.18:\n  version "2026.11.18"\n'},
        [_git()],
        None,
        True,
        "unsupported lockfile",
    ),
    (
        "markdown_mention_ignored",
        {"README.md": "Do not run uvx mcp-server-git or npx @modelcontextprotocol/server-filesystem.\n"},
        [],
        None,
        True,
        None,
    ),
]


@pytest.mark.parametrize(
    ("name", "files", "servers", "floors", "allowlist", "expect"),
    CASES,
    ids=[case[0] for case in CASES],
)
def test_supply_chain_fixture(tmp_path, name, files, servers, floors, allowlist, expect):
    del name
    _write(tmp_path, files, servers, floors, allowlist)
    findings = check_root(tmp_path).findings
    if expect is None:
        assert findings == []
    else:
        assert findings, "expected the gate to fail"
        assert any(expect in finding.message for finding in findings)


def test_repository_servers_are_pinned_and_allowlisted(capsys):
    report = check_root(ROOT)
    assert report.findings == []
    assert report.servers == 3
    assert report.dependencies == 0
    assert main(["--root", str(ROOT)]) == 0
    assert "mcp supply-chain check passed: 3 server entries, 0 server dependencies" in capsys.readouterr().out


def test_cli_failure_exit_code(tmp_path):
    _write(
        tmp_path,
        {"mcp.json": json.dumps({"servers": {"git": {"command": "uvx", "args": ["mcp-server-git"]}}})},
        [],
        None,
        True,
    )
    assert main(["--root", str(tmp_path)]) == 1


def test_checker_does_not_execute_commands(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("supply-chain check must not execute a command")

    monkeypatch.setattr("os.system", boom)
    monkeypatch.setattr("subprocess.run", boom, raising=False)
    monkeypatch.setattr("subprocess.Popen", boom, raising=False)
    _write(
        tmp_path,
        {
            "mcp.json": json.dumps(
                {
                    "servers": {
                        "filesystem": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-filesystem@2.4.0"],
                        }
                    }
                }
            )
        },
        [_filesystem()],
        None,
        True,
    )
    assert check_root(tmp_path).findings == []


def test_readme_names_the_release_and_fixed_versions():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "07-mcp-supply-chain.md").read_text(encoding="utf-8")
    allowlist = (ROOT / "security" / "mcp-server-allowlist.json").read_text(encoding="utf-8")
    for text in (readme, guide, allowlist):
        assert RELEASE_URL in text
    for version in ("2026.11.18", "2.4.0", "2.3.1"):
        assert version in readme
        assert version in guide
    assert "config-driven command execution" in guide
