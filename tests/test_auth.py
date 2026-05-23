import asyncio
from contextlib import asynccontextmanager

import chainlit as cl
import pytest

from chatbot.auth import (
    ROLE_ADMIN,
    ROLE_USER,
    authenticate,
    create_account,
    reset_password,
    set_account_active,
    set_account_role,
    user_from_account,
)


def test_user_from_account():
    user = user_from_account({"identifier": "alice", "display_name": "Alice", "role": ROLE_ADMIN})
    assert user.identifier == "alice"
    assert user.display_name == "Alice"
    assert user.metadata["role"] == ROLE_ADMIN
    assert user.metadata["name"] == "Alice"


def test_user_from_account_fallback_name():
    user = user_from_account({"identifier": "bob", "role": ROLE_USER})
    assert user.display_name == "bob"
    assert user.metadata["name"] == "bob"


def test_authenticate_legacy(monkeypatch):
    monkeypatch.setattr("chatbot.auth.config.DATABASE_URL", "")
    monkeypatch.setattr("chatbot.auth.config.AUTH_PASSWORD", "secret")

    user = asyncio.run(authenticate("alice", "secret"))
    assert user is not None
    assert user.identifier == "alice"
    assert user.metadata["role"] == ROLE_USER

    assert asyncio.run(authenticate("alice", "wrong")) is None
    assert asyncio.run(authenticate("", "secret")) is None


def test_authenticate_db(monkeypatch):
    monkeypatch.setattr(
        "chatbot.auth.config.DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost/db",
    )
    monkeypatch.setattr("chatbot.auth.config.AUTH_PASSWORD", "")

    async def fake_fetch(_engine, sql, params):
        if params["password"] == "ok":
            return {
                "identifier": params["identifier"],
                "display_name": "Test",
                "role": ROLE_ADMIN,
            }
        return None

    monkeypatch.setattr("chatbot.auth._fetch_one", fake_fetch)

    user = asyncio.run(authenticate("admin", "ok"))
    assert user is not None
    assert user.metadata["role"] == ROLE_ADMIN
    assert isinstance(user, cl.User)

    assert asyncio.run(authenticate("admin", "bad")) is None


@pytest.fixture
def mock_db(monkeypatch):
    monkeypatch.setattr("chatbot.auth.config.DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

    class FakeEngine:
        pass

    @asynccontextmanager
    async def fake_ctx(_engine=None):
        yield FakeEngine()

    monkeypatch.setattr("chatbot.auth._engine_ctx", fake_ctx)
    return FakeEngine()


def test_create_duplicate_raises(mock_db, monkeypatch):
    async def fake_fetch_one(_engine, sql, params):
        if "password" not in params:
            return {"identifier": params["identifier"], "role": ROLE_USER, "active": True}
        return None

    monkeypatch.setattr("chatbot.auth._fetch_one", fake_fetch_one)

    with pytest.raises(ValueError, match="déjà existant"):
        asyncio.run(create_account("alice", "secret"))


def test_disable_last_admin_raises(mock_db, monkeypatch):
    admin = {"identifier": "admin", "role": ROLE_ADMIN, "active": True}

    async def fake_require(_engine, identifier):
        return admin

    async def fake_count(_engine):
        return 1

    monkeypatch.setattr("chatbot.auth._require_account", fake_require)
    monkeypatch.setattr("chatbot.auth._count_active_admins", fake_count)

    with pytest.raises(ValueError, match="dernier admin"):
        asyncio.run(set_account_active("admin", active=False))


def test_set_role_last_admin_raises(mock_db, monkeypatch):
    admin = {"identifier": "admin", "role": ROLE_ADMIN, "active": True}

    async def fake_require(_engine, identifier):
        return admin

    async def fake_count(_engine):
        return 1

    monkeypatch.setattr("chatbot.auth._require_account", fake_require)
    monkeypatch.setattr("chatbot.auth._count_active_admins", fake_count)

    with pytest.raises(ValueError, match="dernier admin"):
        asyncio.run(set_account_role("admin", ROLE_USER))


def test_reset_password_unknown(mock_db, monkeypatch):
    async def fake_require(_engine, identifier):
        raise ValueError(f"Compte introuvable : {identifier}")

    monkeypatch.setattr("chatbot.auth._require_account", fake_require)

    with pytest.raises(ValueError, match="introuvable"):
        asyncio.run(reset_password("ghost", "newpass"))


def test_reset_password_ok(mock_db, monkeypatch):
    updated = {}

    async def fake_require(_engine, identifier):
        return {"identifier": identifier, "role": ROLE_USER, "active": True}

    async def fake_update(_engine, sql, params):
        updated.update(params)
        return 1

    monkeypatch.setattr("chatbot.auth._require_account", fake_require)
    monkeypatch.setattr("chatbot.auth._execute_update", fake_update)

    asyncio.run(reset_password("alice", "newsecret"))
    assert updated["identifier"] == "alice"
    assert updated["password"] == "newsecret"
