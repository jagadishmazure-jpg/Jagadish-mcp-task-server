import uuid

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import database as db


async def test_exactly_three_tools_exposed(mcp):
    async with Client(mcp) as c:
        names = sorted(t.name for t in await c.list_tools())
    assert names == ["create_task", "list_tasks", "update_task_status"]


async def test_every_tool_has_a_description(mcp):
    async with Client(mcp) as c:
        for tool in await c.list_tools():
            assert tool.description and len(tool.description) > 20


async def test_create_task_uses_uuid4_and_todo(mcp):
    async with Client(mcp) as c:
        task = (await c.call_tool("create_task", {"title": "Cooking"})).data
    assert uuid.UUID(task["task_id"]).version == 4
    assert task["status"] == "todo"
    assert task["priority"] == "medium"


async def test_create_task_cannot_set_status(mcp):
    async with Client(mcp) as c:
        with pytest.raises(ToolError):
            await c.call_tool("create_task", {"title": "x", "status": "done"})


async def test_title_whitespace_trimmed(mcp):
    async with Client(mcp) as c:
        task = (await c.call_tool("create_task", {"title": "  Read RFC  "})).data
    assert task["title"] == "Read RFC"


@pytest.mark.parametrize("title", ["", "   ", "x" * (db.TITLE_MAX + 1)])
async def test_bad_titles_rejected(mcp, title):
    async with Client(mcp) as c:
        with pytest.raises(ToolError, match="title"):
            await c.call_tool("create_task", {"title": title})


async def test_title_at_limit_accepted(mcp):
    async with Client(mcp) as c:
        task = (await c.call_tool("create_task", {"title": "x" * db.TITLE_MAX})).data
    assert len(task["title"]) == db.TITLE_MAX


async def test_description_limit(mcp):
    async with Client(mcp) as c:
        with pytest.raises(ToolError, match="description"):
            await c.call_tool("create_task", {"title": "x", "description": "d" * (db.DESCRIPTION_MAX + 1)})


async def test_priority_enum_enforced(mcp):
    async with Client(mcp) as c:
        with pytest.raises(ToolError):
            await c.call_tool("create_task", {"title": "x", "priority": "urgent"})


async def test_validation_error_does_not_echo_input(mcp):
    secret_like = "y" * (db.TITLE_MAX + 5)
    async with Client(mcp) as c:
        result = await c.call_tool("create_task", {"title": secret_like}, raise_on_error=False)
    assert result.is_error
    assert secret_like not in result.content[0].text


async def test_update_and_list_round_trip(mcp):
    async with Client(mcp) as c:
        task = (await c.call_tool("create_task", {"title": "Cooking"})).data
        await c.call_tool("update_task_status", {"task_id": task["task_id"], "status": "in_progress"})
        listed = (await c.call_tool("list_tasks", {})).data
    assert listed[0]["status"] == "in_progress"


async def test_update_status_rejects_unknown_status(mcp):
    async with Client(mcp) as c:
        task = (await c.call_tool("create_task", {"title": "x"})).data
        with pytest.raises(ToolError):
            await c.call_tool("update_task_status", {"task_id": task["task_id"], "status": "archived"})


async def test_not_found_error_is_clear(mcp):
    async with Client(mcp) as c:
        with pytest.raises(ToolError, match="Task not found"):
            await c.call_tool("update_task_status", {"task_id": "nope", "status": "done"})


async def test_list_tasks_empty(mcp):
    async with Client(mcp) as c:
        assert (await c.call_tool("list_tasks", {})).data == []


async def test_status_schema_is_an_enum(mcp):
    async with Client(mcp) as c:
        tools = {t.name: t for t in await c.list_tools()}
    schema = tools["update_task_status"].inputSchema["properties"]["status"]
    assert schema["enum"] == ["todo", "in_progress", "done"]
