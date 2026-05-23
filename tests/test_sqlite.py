import os
import tempfile

import pytest

from chatbot.sqlite import SQLiteDataLayer


@pytest.fixture
async def db():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.db")
        layer = SQLiteDataLayer(path)
        yield layer


@pytest.mark.asyncio
async def test_create_user_and_thread(db):
    user = await db.create_user({"identifier": "alice", "metadata": {"name": "Alice"}})
    assert user
    assert user["identifier"] == "alice"

    thread = await db.create_thread(
        {"id": "t1", "name": "Test", "userId": user["id"], "metadata": {}}
    )
    assert thread["id"] == "t1"

    fetched = await db.get_thread("t1")
    assert fetched
    assert fetched["name"] == "Test"
    assert fetched["steps"] == []


@pytest.mark.asyncio
async def test_create_step(db):
    user = await db.create_user({"identifier": "bob", "metadata": {}})
    await db.create_thread({"id": "t2", "userId": user["id"], "metadata": {}})
    await db.create_step(
        {
            "id": "s1",
            "threadId": "t2",
            "type": "user_message",
            "output": "Salut",
        }
    )

    thread = await db.get_thread("t2")
    assert len(thread["steps"]) == 1
    assert thread["steps"][0]["output"] == "Salut"
