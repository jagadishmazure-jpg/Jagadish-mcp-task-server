"""LangChain agent -> MCP tools -> SQLite, fully offline with the fake model."""

from fastmcp import Client

import langchain_client as lc
from fake_model import FakeTaskModel


async def _agent(c):
    return await lc.build_agent(c.session, model=FakeTaskModel())


async def test_pick_model_offline_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(lc.pick_model(), FakeTaskModel)


async def test_agent_creates_lists_and_updates(mcp):
    async with Client(mcp) as c:
        agent = await _agent(c)
        assert "Created 'Cooking'" in await lc.ask(agent, "add task Cooking with high priority")
        assert "Cooking [high] - todo" in await lc.ask(agent, "list tasks")
        assert "status: done" in await lc.ask(agent, "mark Cooking as done")
        rows = (await c.call_tool("list_tasks", {})).data
    assert rows[0]["status"] == "done"
    assert rows[0]["priority"] == "high"


async def test_agent_refuses_description_change_and_db_unchanged(mcp):
    async with Client(mcp) as c:
        await c.call_tool("create_task", {"title": "Cooking", "description": "buy chicken"})
        agent = await _agent(c)
        reply = await lc.ask(agent, "change the description of Cooking to don't forget the rice")
        rows = (await c.call_tool("list_tasks", {})).data
    assert "can't" in reply
    assert rows[0]["description"] == "buy chicken"


async def test_agent_reports_unknown_task(mcp):
    async with Client(mcp) as c:
        agent = await _agent(c)
        assert "couldn't find" in await lc.ask(agent, "mark Ghost as done")


async def test_checkpointer_keeps_thread_history(mcp):
    async with Client(mcp) as c:
        agent = await _agent(c)
        await lc.ask(agent, "add task One", thread_id="a")
        await lc.ask(agent, "list tasks", thread_id="a")
        state = await agent.aget_state({"configurable": {"thread_id": "a"}})
        other = await agent.aget_state({"configurable": {"thread_id": "b"}})
    assert len(state.values["messages"]) >= 6
    assert other.values == {} or not other.values.get("messages")


async def test_plain_client_demo_runs_in_memory(mcp, capsys):
    import client

    rows = await client.demo(mcp)
    out = capsys.readouterr().out
    assert "create_task" in out and rows[0]["status"] == "in_progress"
