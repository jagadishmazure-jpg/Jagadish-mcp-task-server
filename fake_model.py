"""A deterministic, offline stand-in for a chat model.

It reads only the latest *user* message and turns a few fixed phrasings into
tool calls. It never reads task text as instructions. This lets the tests and
CI exercise the full LangChain -> MCP -> SQLite path with no API key and no
network. It is a test double, not a language model: it proves the plumbing,
not how a real model behaves under adversarial input.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_ADD = re.compile(
    r"^(?:add|create)\s+(?:a\s+)?(?:new\s+)?task\s+(?:called\s+)?(?P<title>.+?)"
    r"(?:\s+with\s+(?P<prio>low|medium|high)\s+priority)?$",
    re.I,
)
_MARK = re.compile(
    r"^(?:mark|set|move)\s+(?P<title>.+?)\s+(?:as|to)\s+(?P<status>todo|in[ _]progress|done)$",
    re.I,
)
_LIST = re.compile(r"\b(list|show)\b.*\btasks?\b", re.I)
_EDIT = re.compile(r"\b(description|delete|remove|rename)\b", re.I)


def _call(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:8]}"}],
    )


def _tool_payload(msg: ToolMessage) -> Any:
    """Pull JSON out of a ToolMessage, whatever block shape the adapter used."""
    content = msg.content
    if isinstance(content, list):
        content = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return content


def _as_task_list(payload: Any) -> list[dict]:
    if isinstance(payload, dict) and "result" in payload:
        payload = payload["result"]
    if isinstance(payload, dict):
        payload = [payload]
    return [t for t in payload if isinstance(t, dict)] if isinstance(payload, list) else []


class FakeTaskModel(BaseChatModel):
    """Rule-based model: same input, same output, every time."""

    @property
    def _llm_type(self) -> str:
        return "fake-task-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeTaskModel:
        return self  # the rules already know the three tool names

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kw) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._decide(messages))])

    def _decide(self, messages: list[BaseMessage]) -> AIMessage:
        last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        request = str(messages[last_human].content).strip().rstrip(".!?")
        since = messages[last_human + 1 :]
        tool_msgs = [m for m in since if isinstance(m, ToolMessage)]

        if not tool_msgs:  # first step: choose a tool from the user's words
            if m := _MARK.match(request):
                return _call("list_tasks", {})  # need the id first
            if m := _ADD.match(request):
                args = {"title": m["title"].strip("'\"")}
                if m["prio"]:
                    args["priority"] = m["prio"].lower()
                return _call("create_task", args)
            if _EDIT.search(request):
                return AIMessage(
                    content="I can't do that. This server only lets me create tasks, "
                    "list them and change their status."
                )
            if _LIST.search(request):
                return _call("list_tasks", {})
            return AIMessage(content="Try: 'add task <title>', 'list tasks' or 'mark <title> as done'.")

        last = tool_msgs[-1]
        payload = _tool_payload(last)
        if getattr(last, "status", "success") == "error":
            return AIMessage(content=f"The server refused: {payload}")

        if (m := _MARK.match(request)) and last.name == "list_tasks":
            wanted = m["title"].strip("'\"").lower()
            status = m["status"].lower().replace(" ", "_")
            for task in _as_task_list(payload):
                if wanted in (task.get("title", "").lower(), task.get("task_id")):
                    return _call("update_task_status", {"task_id": task["task_id"], "status": status})
            return AIMessage(content=f"I couldn't find a task called '{m['title']}'.")

        tasks = _as_task_list(payload)
        if last.name == "list_tasks":
            if not tasks:
                return AIMessage(content="You have no tasks.")
            lines = [f"- {t['title']} [{t['priority']}] - {t['status']}" for t in tasks]
            return AIMessage(content="Your tasks:\n" + "\n".join(lines))
        if tasks:
            t = tasks[0]
            verb = "Created" if last.name == "create_task" else "Updated"
            return AIMessage(content=f"{verb} '{t['title']}' (status: {t['status']}).")
        return AIMessage(content=str(payload))
