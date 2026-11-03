import pytest

import server


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "tasks.db")


@pytest.fixture
def mcp(db_path):
    return server.build_server(db_path)
