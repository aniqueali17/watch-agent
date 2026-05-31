"""
Shared pytest fixtures. pytest auto-loads anything in conftest.py,
so any test in this folder can ask for these fixtures by name.
"""

import os
import tempfile
import pytest

from app import storage


@pytest.fixture
def temp_db(monkeypatch):
    """
    Give each test its own empty SQLite file. We point storage.DB_PATH
    at a temp file before the test, run init_db() to set up the tables,
    and the file is cleaned up after.

    Without this every test would scribble on the same database and
    they'd interfere with each other.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    monkeypatch.setattr(storage, "DB_PATH", tmp.name)
    storage.init_db()

    yield tmp.name

    os.unlink(tmp.name)