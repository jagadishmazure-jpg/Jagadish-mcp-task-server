"""The server has no tool that edits a description. These tests prove it."""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


async def test_no_edit_or_delete_tool_exists(mcp):
    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
    for forbidden in ("update_task_description", "edit_task", "delete_task", "update_task"):
        assert forbidden not in names


async def test_calling_missing_edit_tool_fails(mcp):
    async with Client(mcp) as c:
        with pytest.raises(ToolError):
            await c.call_tool("update_task_description", {"task_id": "x", "description": "y"})


async def test_update_status_rejects_smuggled_description(mcp):
    async with Client(mcp) as c:
        task = (await c.call_tool("create_task", {"title": "Cooking", "description": "buy chicken"})).data
        with pytest.raises(ToolError):
            await c.call_tool(
                "update_task_status",
                {"task_id": task["task_id"], "status": "done", "description": "changed"},
            )
        listed = (await c.call_tool("list_tasks", {})).data
    assert listed[0]["description"] == "buy chicken"
    assert listed[0]["status"] == "todo"
