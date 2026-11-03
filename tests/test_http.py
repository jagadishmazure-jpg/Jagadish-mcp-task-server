"""Real streamable-HTTP run: server in a subprocess, bearer token on and off."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

import server

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def http_server(tmp_path):
    port = _free_port()
    env = {
        **os.environ,
        "MCP_PORT": str(port),
        "TASKS_DB_PATH": str(tmp_path / "h.db"),
        "MCP_AUTH_TOKEN": "test-only-token",
        "FASTMCP_SHOW_SERVER_BANNER": "false",
    }
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/mcp"
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


async def test_http_with_token_works(http_server):
    async with Client(http_server, auth="test-only-token") as c:
        task = (await c.call_tool("create_task", {"title": "over http"})).data
        rows = (await c.call_tool("list_tasks", {})).data
    assert rows[0]["task_id"] == task["task_id"]


async def test_http_without_token_is_401(http_server):
    async with httpx.AsyncClient() as h:
        r = await h.post(
            http_server,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert r.status_code == 401


async def test_http_wrong_token_is_401(http_server):
    async with httpx.AsyncClient() as h:
        r = await h.post(
            http_server,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": "Bearer wrong", "Accept": "application/json, text/event-stream"},
        )
    assert r.status_code == 401


def test_default_bind_is_loopback(monkeypatch):
    captured = {}
    monkeypatch.delenv("MCP_HOST", raising=False)
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kw: captured.update(kw))
    monkeypatch.setenv("TASKS_DB_PATH", ":memory:")
    server.main()
    assert captured["host"] == "127.0.0.1" and captured["port"] == 8000
    assert captured["transport"] == "streamable-http"


def test_no_token_env_means_no_auth(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    assert server.bearer_auth_from_env() is None
