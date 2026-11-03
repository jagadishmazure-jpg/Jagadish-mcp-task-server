import sqlite3

import pytest

import database as db


def test_init_db_is_idempotent(db_path):
    db.init_db(db_path)
    db.init_db(db_path)
    assert db.get_all_tasks(db_path) == []


def test_save_task_applies_defaults(db_path):
    db.init_db(db_path)
    row = db.save_task("t1", "Cooking", db_path=db_path)
    assert row["priority"] == "medium"
    assert row["status"] == "todo"
    assert row["description"] == ""


def test_update_status_changes_only_status(db_path):
    db.init_db(db_path)
    before = db.save_task("t1", "Cooking", "buy chicken", "high", db_path=db_path)
    after = db.update_status("t1", "done", db_path=db_path)
    assert after["status"] == "done"
    assert {k: v for k, v in after.items() if k != "status"} == {
        k: v for k, v in before.items() if k != "status"
    }


def test_update_status_unknown_id_raises(db_path):
    db.init_db(db_path)
    with pytest.raises(db.TaskNotFoundError):
        db.update_status("missing", "done", db_path=db_path)


def test_update_status_rejects_bad_status_in_python(db_path):
    db.init_db(db_path)
    db.save_task("t1", "Cooking", db_path=db_path)
    with pytest.raises(ValueError):
        db.update_status("t1", "archived", db_path=db_path)


def test_check_constraint_blocks_bad_status_even_with_raw_sql(db_path):
    db.init_db(db_path)
    db.save_task("t1", "Cooking", db_path=db_path)
    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("archived", "t1"))
    conn.close()


def test_check_constraint_blocks_bad_priority(db_path):
    db.init_db(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        db.save_task("t1", "Cooking", priority="urgent", db_path=db_path)


def test_duplicate_id_rejected(db_path):
    db.init_db(db_path)
    db.save_task("t1", "A", db_path=db_path)
    with pytest.raises(sqlite3.IntegrityError):
        db.save_task("t1", "B", db_path=db_path)


def test_sql_injection_text_is_stored_as_plain_data(db_path):
    db.init_db(db_path)
    evil = "x'); DROP TABLE tasks; --"
    db.save_task("t1", evil, db_path=db_path)
    rows = db.get_all_tasks(db_path)
    assert rows[0]["title"] == evil


def test_get_all_tasks_keeps_insert_order(db_path):
    db.init_db(db_path)
    for i in range(3):
        db.save_task(f"t{i}", f"Task {i}", db_path=db_path)
    assert [r["title"] for r in db.get_all_tasks(db_path)] == ["Task 0", "Task 1", "Task 2"]


def test_db_path_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TASKS_DB_PATH", str(tmp_path / "env.db"))
    assert db.default_db_path() == tmp_path / "env.db"
