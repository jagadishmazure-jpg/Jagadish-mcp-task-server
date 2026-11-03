"""MCP server that exposes a small task list to any MCP client.

Three tools only: create_task, list_tasks, update_task_status.
There is deliberately no tool that edits a description or deletes a task:
an agent connected to this server can do exactly these three things.
"""

from __future__ import annotations

import hmac
import os
import uuid
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import database as db

Status = Literal["todo", "in_progress", "done"]
Priority = Literal["low", "medium", "high"]


class NewTask(BaseModel):
    """Validated input for create_task. Extra keys are rejected."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=db.TITLE_MAX)
    description: str = Field(default="", max_length=db.DESCRIPTION_MAX)
    priority: Priority = "medium"


def build_server(db_path: str | None = None, auth=None) -> FastMCP:
    """Create the FastMCP app. Tests pass a temp db_path; main() passes auth."""
    mcp = FastMCP(
        name="task-server",
        instructions=(
            "Manages a to-do list. You can create tasks, list them and change "
            "their status. You cannot edit descriptions or delete tasks."
        ),
        auth=auth,
    )
    db.init_db(db_path)

    @mcp.tool(
        name="create_task",
        description="Create a new task. It always starts with status 'todo'.",
    )
    def create_task(
        title: Annotated[str, Field(description="Short task name, 1-120 characters")],
        description: Annotated[str, Field(description="Optional details, up to 1000 characters")] = "",
        priority: Annotated[Priority, Field(description="low, medium or high")] = "medium",
    ) -> dict:
        """Validate the input, give the task a random uuid4 id and save it."""
        try:
            task = NewTask(title=title, description=description, priority=priority)
        except ValidationError as exc:
            # Report which field failed, never echo the raw input back.
            fields = ", ".join(str(e["loc"][0]) for e in exc.errors())
            raise ToolError(f"Invalid input for field(s): {fields}") from None
        return db.save_task(str(uuid.uuid4()), task.title, task.description, task.priority, db_path=db_path)

    @mcp.tool(
        name="list_tasks",
        description="List every task with its id, title, description, priority and status.",
    )
    def list_tasks() -> list[dict]:
        """Return all tasks, oldest first."""
        return db.get_all_tasks(db_path=db_path)

    @mcp.tool(
        name="update_task_status",
        description="Change the status of one task. Only the status can change.",
    )
    def update_task_status(
        task_id: Annotated[str, Field(description="The id returned by create_task", max_length=64)],
        status: Annotated[Status, Field(description="todo, in_progress or done")],
    ) -> dict:
        """Set a new status, or fail clearly if the id does not exist."""
        try:
            return db.update_status(task_id, status, db_path=db_path)
        except db.TaskNotFoundError:
            raise ToolError("Task not found. Call list_tasks to see valid task ids.") from None

    return mcp


def bearer_auth_from_env():
    """Return a token check if MCP_AUTH_TOKEN is set, else None (no auth).

    The token lives only in the environment, never in the repo.
    """
    expected = os.environ.get("MCP_AUTH_TOKEN")
    if not expected:
        return None
    from fastmcp.server.auth.providers.debug import DebugTokenVerifier

    return DebugTokenVerifier(validate=lambda token: hmac.compare_digest(token.encode(), expected.encode()))


def main() -> None:
    host = os.environ.get("MCP_HOST", "127.0.0.1")  # loopback unless you opt in
    port = int(os.environ.get("MCP_PORT", "8000"))
    server = build_server(auth=bearer_auth_from_env())
    server.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    main()
