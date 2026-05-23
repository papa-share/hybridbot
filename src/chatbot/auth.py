from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import chainlit as cl
from chainlit.data import get_data_layer as get_active_data_layer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from chatbot.config import DEFAULT_USER_NAME, config

ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLES = {ROLE_USER, ROLE_ADMIN}

_VERIFY_SQL = """
SELECT identifier, display_name, role
FROM accounts
WHERE identifier = :identifier
  AND active = true
  AND password_hash = crypt(:password, password_hash)
"""

_CREATE_SQL = """
INSERT INTO accounts (identifier, password_hash, role, active, display_name, "createdAt")
VALUES (:identifier, crypt(:password, gen_salt('bf')), :role, true, :display_name, :created_at)
"""

_LIST_SQL = """
SELECT identifier, role, active, display_name, "createdAt"
FROM accounts
ORDER BY identifier
"""

_GET_SQL = """
SELECT identifier, role, active, display_name, "createdAt"
FROM accounts
WHERE identifier = :identifier
"""

_SET_ACTIVE_SQL = """
UPDATE accounts SET active = :active WHERE identifier = :identifier
"""

_RESET_PASSWORD_SQL = """
UPDATE accounts
SET password_hash = crypt(:password, gen_salt('bf'))
WHERE identifier = :identifier
"""

_SET_ROLE_SQL = """
UPDATE accounts SET role = :role WHERE identifier = :identifier
"""

_COUNT_ACTIVE_ADMINS_SQL = """
SELECT COUNT(*) AS n FROM accounts WHERE role = 'admin' AND active = true
"""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_identifier(identifier: str) -> str:
    return identifier.strip()


def user_from_account(row: dict[str, Any]) -> cl.User:
    name = row.get("display_name") or row["identifier"]
    return cl.User(
        identifier=row["identifier"],
        display_name=name,
        metadata={"role": row.get("role") or ROLE_USER, "name": name},
    )


def _legacy_user(identifier: str) -> cl.User:
    user_id = identifier or "local_user"
    return cl.User(
        identifier=user_id,
        display_name=user_id,
        metadata={"role": ROLE_USER, "name": user_id or DEFAULT_USER_NAME},
    )


async def _fetch_one(
    engine: AsyncEngine | None, sql: str, params: dict[str, Any]
) -> dict[str, Any] | None:
    if engine is not None:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            row = result.mappings().first()
            return dict(row) if row else None

    layer = get_active_data_layer()
    if not layer:
        return None
    result = await layer.execute_sql(sql, params)
    if isinstance(result, list) and result:
        return result[0]
    return None


async def _fetch_all(
    engine: AsyncEngine | None, sql: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    if engine is not None:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings().all()]

    layer = get_active_data_layer()
    if not layer:
        return []
    result = await layer.execute_sql(sql, params or {})
    return result if isinstance(result, list) else []


async def _execute(engine: AsyncEngine, sql: str, params: dict[str, Any]) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


async def _execute_update(engine: AsyncEngine, sql: str, params: dict[str, Any]) -> int:
    async with engine.begin() as conn:
        result = await conn.execute(text(sql), params)
        return result.rowcount or 0


@asynccontextmanager
async def _engine_ctx(engine: AsyncEngine | None):
    if engine is not None:
        yield engine
        return
    url = config.DATABASE_URL
    if not url:
        raise ValueError("DATABASE_URL manquant.")
    own_engine = create_async_engine(url)
    try:
        yield own_engine
    finally:
        await own_engine.dispose()


def _validate_role(role: str) -> None:
    if role not in ROLES:
        raise ValueError(f"Rôle invalide : {role}")


async def get_account(identifier: str, engine: AsyncEngine | None = None) -> dict[str, Any] | None:
    login = _normalize_identifier(identifier)
    if not login:
        return None
    async with _engine_ctx(engine) as db:
        return await _fetch_one(db, _GET_SQL, {"identifier": login})


async def _count_active_admins(engine: AsyncEngine) -> int:
    rows = await _fetch_all(engine, _COUNT_ACTIVE_ADMINS_SQL)
    if not rows:
        return 0
    return int(rows[0].get("n") or 0)


async def _ensure_not_last_admin(engine: AsyncEngine, account: dict[str, Any]) -> None:
    if account.get("role") != ROLE_ADMIN or not account.get("active"):
        return
    if await _count_active_admins(engine) <= 1:
        raise ValueError("Impossible : dernier admin actif.")


async def _require_account(engine: AsyncEngine, identifier: str) -> dict[str, Any]:
    account = await _fetch_one(engine, _GET_SQL, {"identifier": identifier})
    if not account:
        raise ValueError(f"Compte introuvable : {identifier}")
    return account


async def authenticate(identifier: str, password: str) -> cl.User | None:
    login = _normalize_identifier(identifier)
    if not login or not password:
        return None

    if not config.DATABASE_URL:
        if config.AUTH_PASSWORD and password == config.AUTH_PASSWORD:
            return _legacy_user(login)
        return None

    row = await _fetch_one(
        None,
        _VERIFY_SQL,
        {"identifier": login, "password": password},
    )
    return user_from_account(row) if row else None


async def create_account(
    identifier: str,
    password: str,
    *,
    role: str = ROLE_USER,
    display_name: str | None = None,
    engine: AsyncEngine | None = None,
) -> None:
    login = _normalize_identifier(identifier)
    if not login or not password:
        raise ValueError("Identifiant et mot de passe requis.")
    _validate_role(role)

    async with _engine_ctx(engine) as db:
        if await _fetch_one(db, _GET_SQL, {"identifier": login}):
            raise ValueError(f"Compte déjà existant : {login}")
        await _execute(
            db,
            _CREATE_SQL,
            {
                "identifier": login,
                "password": password,
                "role": role,
                "display_name": display_name or login,
                "created_at": _utc_now(),
            },
        )


async def list_accounts(engine: AsyncEngine | None = None) -> list[dict[str, Any]]:
    async with _engine_ctx(engine) as db:
        return await _fetch_all(db, _LIST_SQL)


async def set_account_active(
    identifier: str,
    *,
    active: bool,
    engine: AsyncEngine | None = None,
) -> None:
    login = _normalize_identifier(identifier)
    if not login:
        raise ValueError("Identifiant requis.")

    async with _engine_ctx(engine) as db:
        account = await _require_account(db, login)
        if bool(account.get("active")) == active:
            state = "actif" if active else "inactif"
            raise ValueError(f"Compte déjà {state} : {login}")
        if not active:
            await _ensure_not_last_admin(db, account)
        updated = await _execute_update(
            db, _SET_ACTIVE_SQL, {"identifier": login, "active": active}
        )
        if updated == 0:
            raise ValueError(f"Compte introuvable : {login}")


async def reset_password(
    identifier: str,
    password: str,
    *,
    engine: AsyncEngine | None = None,
) -> None:
    login = _normalize_identifier(identifier)
    if not login or not password:
        raise ValueError("Identifiant et mot de passe requis.")

    async with _engine_ctx(engine) as db:
        await _require_account(db, login)
        updated = await _execute_update(
            db, _RESET_PASSWORD_SQL, {"identifier": login, "password": password}
        )
        if updated == 0:
            raise ValueError(f"Compte introuvable : {login}")


async def set_account_role(
    identifier: str,
    role: str,
    *,
    engine: AsyncEngine | None = None,
) -> None:
    login = _normalize_identifier(identifier)
    if not login:
        raise ValueError("Identifiant requis.")
    _validate_role(role)

    async with _engine_ctx(engine) as db:
        account = await _require_account(db, login)
        if account.get("role") == role:
            raise ValueError(f"Compte déjà {role} : {login}")
        if role == ROLE_USER:
            await _ensure_not_last_admin(db, account)
        updated = await _execute_update(db, _SET_ROLE_SQL, {"identifier": login, "role": role})
        if updated == 0:
            raise ValueError(f"Compte introuvable : {login}")
