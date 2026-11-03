"""Plain FastMCP client: no LLM, just direct tool calls.

uv run python server.py        # terminal 1
uv run python client.py        # terminal 2
"""

from __future__ import annotations

import asyncio
import os

from fastmcp import Client


async def demo(target) -> list[dict]:
    """Run the four steps against any target: a URL or an in-memory server."""
    async with Client(target, auth=os.environ.get("MCP_AUTH_TOKEN")) as client:
        tools = await client.list_tools()
        print("Tools:", ", ".join(t.name for t in tools))

        created = await client.call_tool(
            "create_task",
            {"title": "Write MCP notes", "description": "Summarise transports", "priority": "high"},
        )
        task = created.data
        print("Created:", task["title"], task["status"])

        updated = await client.call_tool(
            "update_task_status", {"task_id": task["task_id"], "status": "in_progress"}
        )
        print("Updated:", updated.data["title"], updated.data["status"])

        listed = await client.call_tool("list_tasks", {})
        for t in listed.data:
            print(f"- {t['title']} [{t['priority']}] {t['status']}")
        return listed.data


if __name__ == "__main__":
    asyncio.run(demo(os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")))
