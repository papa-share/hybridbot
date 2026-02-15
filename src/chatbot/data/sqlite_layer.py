"""Data Layer SQLite pour Chainlit."""

import json
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

from chainlit.data import BaseDataLayer

from chatbot.config import config
from chatbot.constants import DEFAULT_THREAD_NAME

ThreadDict = dict[str, Any]
StepDict = dict[str, Any]
UserDict = dict[str, Any]
PaginatedResponse = dict[str, Any]


class SQLiteDataLayer(BaseDataLayer):
    """
    Implémentation SQLite du Data Layer Chainlit.

    Gère la persistance des utilisateurs, threads (conversations) et steps (messages).
    Les éléments média (images, fichiers) ne sont pas persistés.
    """

    def __init__(self, db_path: str = None):
        """
        Initialise le Data Layer SQLite.

        La base n'est créée qu'au premier appel async (initialisation paresseuse).

        Args:
            db_path: Chemin vers la base SQLite (défaut: config.DEFAULT_DB_PATH)
        """
        self.db_path = db_path or config.DEFAULT_DB_PATH
        self._initialized = False

    async def _init_db(self):
        """
        Crée les tables SQLite si elles n'existent pas.

        Schéma :
        - users: Identifiants et métadonnées utilisateurs
        - threads: Conversations avec métadonnées
        - steps: Messages individuels dans les threads
        """
        async with aiosqlite.connect(self.db_path) as conn:
            # Activer le mode WAL pour meilleure concurrence
            await conn.execute("PRAGMA journal_mode=WAL")
            
            cursor = await conn.cursor()

            # Table users
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    identifier TEXT UNIQUE NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table threads (conversations)
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

            # Table steps (messages)
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

            # Index pour accélérer les requêtes
            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_steps_thread_id
                ON steps(thread_id)
            """)
            
            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_identifier
                ON users(identifier)
            """)
            
            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_threads_user_id_created
                ON threads(user_id, created_at DESC)
            """)

            await conn.commit()

    async def _ensure_initialized(self) -> None:
        """Garantit que la base est initialisée (lazy init)."""
        if not self._initialized:
            await self._init_db()
            self._initialized = True

    @asynccontextmanager
    async def _get_connection(self):
        """
        Context manager pour une connexion à la base de données.

        Yields:
            Connexion SQLite asynchrone
        """
        conn = await aiosqlite.connect(self.db_path)
        try:
            yield conn
        finally:
            await conn.close()

    async def get_user(self, identifier: str) -> UserDict | None:
        """Récupère un utilisateur par son identifiant."""
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, identifier, metadata FROM users WHERE identifier = ?", (identifier,)
            )
            row = await cursor.fetchone()

            if row:
                return {
                    "id": row[0],
                    "identifier": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                }
            return None

    async def create_user(self, user: UserDict) -> UserDict | None:
        """
        Crée un nouvel utilisateur dans la base de données.

        Args:
            user: Dictionnaire avec 'identifier' et optionnellement 'id' et 'metadata'

        Returns:
            Utilisateur créé ou existant si duplication
        """
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

    async def get_thread(self, thread_id: str) -> ThreadDict | None:
        """Récupère un thread par son ID."""
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
            steps_rows = await cursor2.fetchall()

            steps = []
            for step_row in steps_rows:
                steps.append(
                    {
                        "id": step_row[0],
                        "parentId": step_row[1],
                        "name": step_row[2],
                        "type": step_row[3],
                        "input": step_row[4],
                        "output": step_row[5],
                        "metadata": json.loads(step_row[6]) if step_row[6] else {},
                        "tags": json.loads(step_row[7]) if step_row[7] else [],
                        "createdAt": step_row[8],
                    }
                )

            return {
                "id": row[0],
                "name": row[1],
                "userId": row[2],
                "metadata": json.loads(row[3]) if row[3] else {},
                "tags": json.loads(row[4]) if row[4] else [],
                "createdAt": row[5],
                "steps": steps,
            }

    async def list_threads(self, pagination: dict, filters: dict) -> PaginatedResponse:
        """
        Liste les threads d'un utilisateur avec pagination.

        Args:
            pagination: Paramètres de pagination (first: nombre de résultats)
            filters: Filtres de recherche (userId requis)

        Returns:
            Dictionnaire avec 'data' (threads) et 'pageInfo' (pagination)
        """
        await self._ensure_initialized()
        user_id = filters.get("userId")
        if not user_id:
            return {"data": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}

        limit = pagination.get("first", config.DEFAULT_PAGINATION_LIMIT)
        
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, user_id, metadata, tags, created_at "
                "FROM threads WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )
            rows = await cursor.fetchall()

            threads = []
            for row in rows:
                threads.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "userId": row[2],
                        "metadata": json.loads(row[3]) if row[3] else {},
                        "tags": json.loads(row[4]) if row[4] else [],
                        "createdAt": row[5],
                    }
                )

            return {
                "data": threads,
                "pageInfo": {
                    "hasNextPage": len(threads) >= limit,
                    "endCursor": threads[-1]["id"] if threads else None,
                },
            }

    async def create_thread(self, thread: ThreadDict) -> ThreadDict | None:
        """Crée un nouveau thread."""
        await self._ensure_initialized()
        thread_id = thread.get("id")
        name = thread.get("name", DEFAULT_THREAD_NAME)
        user_id = thread.get("userId")
        metadata_json = json.dumps(thread.get("metadata", {}))
        tags_json = json.dumps(thread.get("tags", []))

        async with self._get_connection() as conn:
            await conn.execute(
                "INSERT INTO threads (id, name, user_id, metadata, tags) VALUES (?, ?, ?, ?, ?)",
                (thread_id, name, user_id, metadata_json, tags_json),
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
        """
        Met à jour les propriétés d'un thread.

        Args:
            thread_id: Identifiant du thread à modifier
            name: Nouveau nom (optionnel)
            metadata: Nouvelles métadonnées (optionnel)
            tags: Nouveaux tags (optionnel)
        """
        await self._ensure_initialized()
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if updates:
            params.append(thread_id)
            async with self._get_connection() as conn:
                await conn.execute(f"UPDATE threads SET {', '.join(updates)} WHERE id = ?", params)
                await conn.commit()

    async def delete_thread(self, thread_id: str):
        """Supprime un thread et ses steps."""
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            await conn.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
            await conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            await conn.commit()

    async def create_step(self, step: StepDict):
        """
        Crée un nouveau step (message) dans un thread.

        Args:
            step: Dictionnaire avec 'id', 'threadId', 'type', 'output' et autres champs optionnels
        """
        await self._ensure_initialized()
        step_id = step.get("id")
        thread_id = step.get("threadId")
        parent_id = step.get("parentId")
        name = step.get("name", "")
        step_type = step.get("type", "user_message")
        input_data = step.get("input", "")
        output_data = step.get("output", "")
        metadata_json = json.dumps(step.get("metadata", {}))
        tags_json = json.dumps(step.get("tags", []))

        async with self._get_connection() as conn:
            await conn.execute(
                "INSERT INTO steps (id, thread_id, parent_id, name, type, input, output, "
                "metadata, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    step_id,
                    thread_id,
                    parent_id,
                    name,
                    step_type,
                    input_data,
                    output_data,
                    metadata_json,
                    tags_json,
                ),
            )
            await conn.commit()

    async def update_step(
        self, step_id: str, output: str | None = None, metadata: dict | None = None
    ):
        """Met à jour un step."""
        await self._ensure_initialized()
        updates = []
        params = []

        if output is not None:
            updates.append("output = ?")
            params.append(output)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if updates:
            params.append(step_id)
            async with self._get_connection() as conn:
                await conn.execute(f"UPDATE steps SET {', '.join(updates)} WHERE id = ?", params)
                await conn.commit()

    async def delete_step(self, step_id: str):
        """
        Supprime un step de la base de données.

        Args:
            step_id: Identifiant du step à supprimer
        """
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            await conn.execute("DELETE FROM steps WHERE id = ?", (step_id,))
            await conn.commit()

    async def get_thread_author(self, thread_id: str) -> str:
        """
        Retourne l'identifiant de l'auteur d'un thread (optimisé).

        Args:
            thread_id: Identifiant du thread

        Returns:
            userId de l'auteur, ou chaîne vide si non trouvé
        """
        await self._ensure_initialized()
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT user_id FROM threads WHERE id = ?", (thread_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else ""

    async def delete_feedback(self, _feedback_id: str) -> bool:
        """
        Supprime un feedback (non implémenté).

        Cette méthode est requise par BaseDataLayer mais n'est pas utilisée
        dans cette implémentation simple de persistance.

        Returns:
            True pour indiquer la réussite (stub)
        """
        await self._ensure_initialized()
        return True

    async def upsert_feedback(self, feedback):
        """
        Crée ou met à jour un feedback (non implémenté).

        Cette méthode est requise par BaseDataLayer mais n'est pas utilisée
        dans cette implémentation simple de persistance.

        Returns:
            Le feedback tel que fourni (stub)
        """
        await self._ensure_initialized()
        return feedback

    async def get_element(self, thread_id: str, _element_id: str):
        """
        Récupère un élément média (non implémenté).

        Les éléments média (images, fichiers) ne sont pas persistés dans cette
        implémentation. Seuls les textes des conversations sont sauvegardés.

        Returns:
            None car les éléments ne sont pas persistés
        """
        await self._ensure_initialized()
        return None

    async def create_element(self, element):
        """
        Crée un élément média (non implémenté).

        Les éléments média (images, fichiers) ne sont pas persistés dans cette
        implémentation. Seuls les textes des conversations sont sauvegardés.

        Returns:
            L'élément tel que fourni (stub)
        """
        await self._ensure_initialized()
        return element

    async def delete_element(self, _element_id: str):
        """
        Supprime un élément média (non implémenté).

        Les éléments média ne sont pas persistés, donc aucune action n'est nécessaire.
        """
        await self._ensure_initialized()

    def build_debug_url(self) -> str:
        """
        Construit une URL de débogage (non utilisé).

        Cette méthode est requise par BaseDataLayer mais n'est pas pertinente
        pour une base SQLite locale.

        Returns:
            Chaîne vide
        """
        return ""
