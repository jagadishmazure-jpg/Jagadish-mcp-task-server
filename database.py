"""SQLite storage for the task server.

Every query uses ``?`` placeholders, so user text is never spliced into SQL.
The CHECK constraints repeat the Pydantic rules, so a bad value is stopped
twice: once at the tool boundary and once by the database itself.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

VALID_STATUSES = ("todo", "in_progress", "done")
VALID_PRIORITIES = ("low", "medium", "high")
TITLE_MAX = 120
DESCRIPTION_MAX = 1000

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS tasks (
    task_id     TEXT PRIMARY KEY,
    title       TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND {TITLE_MAX}),
    description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= {DESCRIPTION_MAX}),
    priority    TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
    status      TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""


class TaskNotFoundError(LookupError):
    """Raised when an update targets a task_id that does not exist."""


def default_db_path() -> Path:
    """Database file location; override with the TASKS_DB_PATH variable."""
    return Path(os.environ.get("TASKS_DB_PATH", "tasks.db"))


def _connect(db_path: str | Path | None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or default_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    """Create the tasks table if it is not there yet. Safe to call many times."""
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(SCHEMA)


def save_task(
    task_id: str,
    title: str,
    description: str = "",
    priority: str = "medium",
    db_path: str | Path | None = None,
) -> dict:
    """Insert one task. New tasks always start in status 'todo'."""
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO tasks (task_id, title, description, priority, status) VALUES (?, ?, ?, ?, 'todo')",
            (task_id, title, description, priority),
        )
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return dict(row)


def update_status(task_id: str, status: str, db_path: str | Path | None = None) -> dict:
    """Change only the status column of one task."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}")
    with closing(_connect(db_path)) as conn, conn:
        cur = conn.execute("UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id))
        if cur.rowcount == 0:
            raise TaskNotFoundError(f"No task with id {task_id!r}")
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return dict(row)


def get_all_tasks(db_path: str | Path | None = None) -> list[dict]:
    """Return every task, oldest first."""
    with closing(_connect(db_path)) as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at, rowid").fetchall()
    return [dict(r) for r in rows]
