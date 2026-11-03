"""End-to-end demo over real streamable HTTP, saved to results/demo_output.txt.

Starts server.py on a free loopback port with a throwaway database, runs the
plain client, runs the offline agent, and times 50 list_tasks calls. All
numbers it prints are measured on the machine that runs it.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastmcp import Client  # noqa: E402

import client  # noqa: E402
import langchain_client as lc  # noqa: E402
from fake_model import FakeTaskModel  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def run(url: str) -> None:
    print("== plain FastMCP client ==")
    await client.demo(url)
    print("\n== LangChain agent (offline fake model) ==")
    async with Client(url) as c:
        agent = await lc.build_agent(c.session, model=FakeTaskModel())
        for text in [
            "add task MCP runbook",
            "mark MCP runbook as done",
            "change the description of MCP runbook to something else",
            "list tasks",
        ]:
            print(f"you> {text}\nagent> {await lc.ask(agent, text)}")
        samples = []
        for _ in range(50):
            t0 = time.perf_counter()
            await c.call_tool("list_tasks", {})
            samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    print("\n== latency, list_tasks over loopback HTTP (measured, n=50) ==")
    print(f"median {statistics.median(samples):.2f} ms, p95 {samples[int(0.95 * len(samples)) - 1]:.2f} ms")


def main() -> None:
    port = free_port()
    db = Path(tempfile.mkdtemp()) / "demo.db"
    env = {
        **os.environ,
        "MCP_PORT": str(port),
        "TASKS_DB_PATH": str(db),
        "FASTMCP_SHOW_SERVER_BANNER": "false",
    }
    env.pop("MCP_AUTH_TOKEN", None)
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", port), 0.2):
                break
            time.sleep(0.1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            asyncio.run(run(f"http://127.0.0.1:{port}/mcp"))
        text = buf.getvalue()
        print(text)
        (ROOT / "results").mkdir(exist_ok=True)
        (ROOT / "results" / "demo_output.txt").write_text(text)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    main()
