import json
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

from chatbot.config import DEFAULT_THREAD_NAME, config


class SQLiteDataLayer:

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or config.DB_PATH
        self._initialized = False

    async def _init_db(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            cursor = await conn.cursor()

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    identifier TEXT UNIQUE NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    user_id TEXT,
                    metadata TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    parent_id TEXT,
                    name TEXT,
                    type TEXT,
                    input TEXT,
                    output TEXT,
                    metadata TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (thread_id) REFERENCES threads(id)
                )
            """)
            await cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_steps_thread_id ON steps(thread_id)"
            )
            await cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_identifier ON users(identifier)"
            )
            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_threads_user_id_created
                ON threads(user_id, created_at DESC)
            """)
            await conn.commit()

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self._init_db()
            self._initialized = True

    @asynccontextmanager
    async def _get_connection(self):
        conn = await aiosqlite.connect(self.db_path)
        try:
            yield conn
        finally:
            await conn.close()

    async def get_user(self, identifier: str) -> dict[str, Any] | None:
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, identifier, metadata FROM users WHERE identifier = ?",
                (identifier,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "identifier": row[1],
                "metadata": json.loads(row[2]) if row[2] else {},
            }

    async def create_user(self, user: dict[str, Any]) -> dict[str, Any] | None:
        await self._ensure_initialized()
        user_id = user.get("id", user["identifier"])
        metadata_json = json.dumps(user.get("metadata", {}))
        try:
            async with self._get_connection() as conn:
                await conn.execute(
                    "INSERT INTO users (id, identifier, metadata) VALUES (?, ?, ?)",
                    (user_id, user["identifier"], metadata_json),
                )
                await conn.commit()
                return {
                    "id": user_id,
                    "identifier": user["identifier"],
                    "metadata": user.get("metadata", {}),
                }
        except aiosqlite.IntegrityError:
            return await self.get_user(user["identifier"])

    async def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, user_id, metadata, tags, created_at FROM threads WHERE id = ?",
                (thread_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            cursor2 = await conn.execute(
                "SELECT id, parent_id, name, type, input, output, metadata, tags, created_at "
                "FROM steps WHERE thread_id = ? ORDER BY created_at",
                (thread_id,),
            )
            steps = [
                {
                    "id": s[0],
                    "parentId": s[1],
                    "name": s[2],
                    "type": s[3],
                    "input": s[4],
                    "output": s[5],
                    "metadata": json.loads(s[6]) if s[6] else {},
                    "tags": json.loads(s[7]) if s[7] else [],
                    "createdAt": s[8],
                }
                for s in await cursor2.fetchall()
            ]

            return {
                "id": row[0],
                "name": row[1],
                "userId": row[2],
                "metadata": json.loads(row[3]) if row[3] else {},
                "tags": json.loads(row[4]) if row[4] else [],
                "createdAt": row[5],
                "steps": steps,
            }

    async def list_threads(self, pagination: dict, filters: dict) -> dict[str, Any]:
        await self._ensure_initialized()
        user_id = filters.get("userId")
        if not user_id:
            return {"data": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}

        limit = pagination.get("first", 20)
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, user_id, metadata, tags, created_at "
                "FROM threads WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )
            rows = await cursor.fetchall()

        threads = [
            {
                "id": row[0],
                "name": row[1],
                "userId": row[2],
                "metadata": json.loads(row[3]) if row[3] else {},
                "tags": json.loads(row[4]) if row[4] else [],
                "createdAt": row[5],
            }
            for row in rows
        ]
        return {
            "data": threads,
            "pageInfo": {
                "hasNextPage": len(threads) >= limit,
                "endCursor": threads[-1]["id"] if threads else None,
            },
        }

    async def create_thread(self, thread: dict[str, Any]) -> dict[str, Any] | None:
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            await conn.execute(
                "INSERT INTO threads (id, name, user_id, metadata, tags) VALUES (?, ?, ?, ?, ?)",
                (
                    thread.get("id"),
                    thread.get("name", DEFAULT_THREAD_NAME),
                    thread.get("userId"),
                    json.dumps(thread.get("metadata", {})),
                    json.dumps(thread.get("tags", [])),
                ),
            )
            await conn.commit()
        return thread

    async def update_thread(
        self,
        thread_id: str,
        name: str | None = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
    ):
        await self._ensure_initialized()
        updates: list[str] = []
        params: list[Any] = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if not updates:
            return

        params.append(thread_id)
        async with self._get_connection() as conn:
            await conn.execute(
                f"UPDATE threads SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            await conn.commit()

    async def delete_thread(self, thread_id: str):
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            await conn.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
            await conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            await conn.commit()

    async def create_step(self, step: dict[str, Any]):
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            await conn.execute(
                "INSERT INTO steps (id, thread_id, parent_id, name, type, input, output, "
                "metadata, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    step.get("id"),
                    step.get("threadId"),
                    step.get("parentId"),
                    step.get("name", ""),
                    step.get("type", "user_message"),
                    step.get("input", ""),
                    step.get("output", ""),
                    json.dumps(step.get("metadata", {})),
                    json.dumps(step.get("tags", [])),
                ),
            )
            await conn.commit()

    async def update_step(
        self, step_id: str, output: str | None = None, metadata: dict | None = None
    ):
        await self._ensure_initialized()
        updates: list[str] = []
        params: list[Any] = []
        if output is not None:
            updates.append("output = ?")
            params.append(output)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        if not updates:
            return
        params.append(step_id)
        async with self._get_connection() as conn:
            await conn.execute(f"UPDATE steps SET {', '.join(updates)} WHERE id = ?", params)
            await conn.commit()

    async def delete_step(self, step_id: str):
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            await conn.execute("DELETE FROM steps WHERE id = ?", (step_id,))
            await conn.commit()

    async def get_thread_author(self, thread_id: str) -> str:
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT user_id FROM threads WHERE id = ?", (thread_id,))
            row = await cursor.fetchone()
            return row[0] if row else ""

    async def delete_feedback(self, _feedback_id: str) -> bool:
        return True

    async def upsert_feedback(self, feedback):
        return feedback

    async def get_element(self, thread_id: str, _element_id: str):
        return None

    async def create_element(self, element):
        return element

    async def delete_element(self, _element_id: str):
        pass

    def build_debug_url(self) -> str:
        return ""

    async def close(self):
        pass

    async def get_favorite_steps(self, pagination: dict, filters: dict):
        return {"data": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}
