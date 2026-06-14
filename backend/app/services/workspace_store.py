import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from app.core.config import settings
from app.domain.chunk import ChunkDocument
from app.domain.workspace import Document, Notebook, utc_now


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_datetime(value: str | None) -> datetime:
    if value is None:
        return utc_now()
    return datetime.fromisoformat(value)


class WorkspaceStore:
    def __init__(self, sqlite_path: str = settings.sqlite_path) -> None:
        self.sqlite_path = Path(sqlite_path)
        if self.sqlite_path != Path(":memory:"):
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._memory_connection: sqlite3.Connection | None = None
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self.sqlite_path == Path(":memory:"):
            if self._memory_connection is None:
                self._memory_connection = sqlite3.connect(":memory:")
                self._memory_connection.row_factory = sqlite3.Row
                self._memory_connection.execute("PRAGMA foreign_keys = ON")
            yield self._memory_connection
            return

        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS notebooks (
                    notebook_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL REFERENCES notebooks(notebook_id) ON DELETE CASCADE,
                    file_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    mime_type TEXT NOT NULL DEFAULT 'text/plain',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    file_hash TEXT NOT NULL DEFAULT '',
                    storage_object_key TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    notebook_id TEXT NOT NULL,
                    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    content_normalized TEXT NOT NULL,
                    embedding_json TEXT,
                    metadata_json TEXT NOT NULL,
                    embedded_at TEXT
                );

                CREATE TABLE IF NOT EXISTS rag_executions (
                    rag_execution_id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL REFERENCES notebooks(notebook_id) ON DELETE CASCADE,
                    question TEXT NOT NULL,
                    standalone_query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    citations_json TEXT NOT NULL,
                    search_json TEXT NOT NULL,
                    self_corrective_enabled INTEGER NOT NULL,
                    excluded_chunk_ids_json TEXT NOT NULL,
                    elapsed_ms REAL NOT NULL,
                    model_connection_id TEXT,
                    generation_mode TEXT NOT NULL DEFAULT 'placeholder',
                    correction_evaluations_json TEXT NOT NULL DEFAULT '[]',
                    conversation_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL REFERENCES notebooks(notebook_id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    rag_execution_id TEXT,
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS search_profiles (
                    profile_id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL REFERENCES notebooks(notebook_id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    retrievers_json TEXT NOT NULL,
                    self_corrective_enabled INTEGER NOT NULL,
                    final_context_limit INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_connections (
                    connection_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    api_key_hint TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_documents_notebook_id
                    ON documents(notebook_id);

                CREATE INDEX IF NOT EXISTS idx_chunks_notebook_id
                    ON chunks(notebook_id);

                CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                    ON chunks(document_id);

                CREATE INDEX IF NOT EXISTS idx_rag_executions_notebook_id
                    ON rag_executions(notebook_id);

                CREATE INDEX IF NOT EXISTS idx_conversations_notebook_id
                    ON conversations(notebook_id);

                CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id
                    ON conversation_messages(conversation_id);

                CREATE INDEX IF NOT EXISTS idx_search_profiles_notebook_id
                    ON search_profiles(notebook_id);

                CREATE INDEX IF NOT EXISTS idx_model_connections_workspace_id
                    ON model_connections(workspace_id);
                """
            )
            self._ensure_document_columns(connection)
            self._ensure_rag_execution_columns(connection)
            connection.commit()

    def create_notebook(self, title: str, description: str = "") -> Notebook:
        now = utc_now()
        notebook = Notebook(
            notebook_id=f"nb_{uuid4().hex[:12]}",
            title=title,
            description=description,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notebooks (notebook_id, title, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    notebook.notebook_id,
                    notebook.title,
                    notebook.description,
                    _serialize_datetime(notebook.created_at),
                    _serialize_datetime(notebook.updated_at),
                ),
            )
            self._insert_default_search_profiles(connection, notebook.notebook_id, now)
            connection.commit()
        return notebook

    def list_notebooks(self) -> list[Notebook]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    notebooks.*,
                    COUNT(documents.document_id) AS document_count
                FROM notebooks
                LEFT JOIN documents ON documents.notebook_id = notebooks.notebook_id
                GROUP BY notebooks.notebook_id
                ORDER BY notebooks.created_at ASC
                """
            ).fetchall()
        return [self._notebook_from_row(row) for row in rows]

    def get_notebook(self, notebook_id: str) -> Notebook | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    notebooks.*,
                    COUNT(documents.document_id) AS document_count
                FROM notebooks
                LEFT JOIN documents ON documents.notebook_id = notebooks.notebook_id
                WHERE notebooks.notebook_id = ?
                GROUP BY notebooks.notebook_id
                """,
                (notebook_id,),
            ).fetchone()
        return self._notebook_from_row(row) if row is not None else None

    def delete_notebook(self, notebook_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM notebooks WHERE notebook_id = ?",
                (notebook_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def add_document(self, document: Document, chunks: list[ChunkDocument]) -> Document:
        now = utc_now()
        document.created_at = document.created_at or now
        document.updated_at = now

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    document_id,
                    notebook_id,
                    file_name,
                    title,
                    status,
                    chunk_count,
                    mime_type,
                    file_size,
                    file_hash,
                    storage_object_key,
                    tags_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.document_id,
                    document.notebook_id,
                    document.file_name,
                    document.title,
                    document.status,
                    document.chunk_count,
                    document.mime_type,
                    document.file_size,
                    document.file_hash,
                    document.storage_object_key,
                    json.dumps(document.tags),
                    _serialize_datetime(document.created_at),
                    _serialize_datetime(document.updated_at),
                ),
            )
            connection.executemany(
                """
                INSERT INTO chunks (
                    chunk_id,
                    tenant_id,
                    workspace_id,
                    notebook_id,
                    document_id,
                    content,
                    content_normalized,
                    embedding_json,
                    metadata_json,
                    embedded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.tenant_id,
                        chunk.workspace_id,
                        chunk.notebook_id,
                        chunk.document_id,
                        chunk.content,
                        chunk.content_normalized,
                        json.dumps(chunk.embedding) if chunk.embedding is not None else None,
                        json.dumps(chunk.metadata),
                        _serialize_datetime(chunk.embedded_at),
                    )
                    for chunk in chunks
                ],
            )
            connection.execute(
                "UPDATE notebooks SET updated_at = ? WHERE notebook_id = ?",
                (_serialize_datetime(now), document.notebook_id),
            )
            connection.commit()
        return document

    def list_documents(self, notebook_id: str | None = None) -> list[Document]:
        query = """
            SELECT documents.*,
                (SELECT COUNT(*) FROM chunks
                 WHERE chunks.document_id = documents.document_id
                   AND chunks.embedding_json IS NOT NULL) AS embedded_chunk_count
            FROM documents
        """
        params: tuple[str, ...] = ()
        if notebook_id is not None:
            query += " WHERE notebook_id = ?"
            params = (notebook_id,)
        query += " ORDER BY created_at ASC"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._document_from_row(row) for row in rows]

    def get_document(self, document_id: str) -> Document | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT documents.*,
                    (SELECT COUNT(*) FROM chunks
                     WHERE chunks.document_id = documents.document_id
                       AND chunks.embedding_json IS NOT NULL) AS embedded_chunk_count
                FROM documents WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()
        return self._document_from_row(row) if row is not None else None

    def get_document_by_hash(self, notebook_id: str, file_hash: str) -> Document | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT documents.*,
                    (SELECT COUNT(*) FROM chunks
                     WHERE chunks.document_id = documents.document_id
                       AND chunks.embedding_json IS NOT NULL) AS embedded_chunk_count
                FROM documents
                WHERE notebook_id = ? AND file_hash = ? LIMIT 1
                """,
                (notebook_id, file_hash),
            ).fetchone()
        return self._document_from_row(row) if row is not None else None

    def delete_document(self, document_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM documents WHERE document_id = ?",
                (document_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def list_chunks(self, notebook_id: str) -> list[ChunkDocument]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE notebook_id = ? ORDER BY rowid ASC",
                (notebook_id,),
            ).fetchall()
        return [self._chunk_from_row(row) for row in rows]

    def list_document_chunks(self, document_id: str) -> list[ChunkDocument]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE document_id = ? ORDER BY rowid ASC",
                (document_id,),
            ).fetchall()
        return [self._chunk_from_row(row) for row in rows]

    def update_chunk_embeddings(
        self,
        document_id: str,
        embeddings: list[list[float]],
        embedded_at: datetime,
    ) -> int:
        chunks = self.list_document_chunks(document_id)
        if len(chunks) != len(embeddings):
            raise ValueError("Embedding count does not match document chunk count")
        with self._connect() as connection:
            connection.executemany(
                "UPDATE chunks SET embedding_json = ?, embedded_at = ? WHERE chunk_id = ?",
                [
                    (json.dumps(embedding), _serialize_datetime(embedded_at), chunk.chunk_id)
                    for chunk, embedding in zip(chunks, embeddings, strict=True)
                ],
            )
            connection.commit()
        return len(chunks)

    def add_rag_execution(
        self,
        rag_execution_id: str,
        notebook_id: str,
        question: str,
        standalone_query: str,
        answer: str,
        citations: list[dict],
        search: dict,
        self_corrective_enabled: bool,
        excluded_chunk_ids: list[str],
        elapsed_ms: float,
        model_connection_id: str | None,
        generation_mode: str,
        correction_evaluations: list[dict],
        conversation_id: str,
    ) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rag_executions (
                    rag_execution_id,
                    notebook_id,
                    question,
                    standalone_query,
                    answer,
                    citations_json,
                    search_json,
                    self_corrective_enabled,
                    excluded_chunk_ids_json,
                    elapsed_ms,
                    model_connection_id,
                    generation_mode,
                    correction_evaluations_json,
                    conversation_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rag_execution_id,
                    notebook_id,
                    question,
                    standalone_query,
                    answer,
                    json.dumps(citations),
                    json.dumps(search),
                    1 if self_corrective_enabled else 0,
                    json.dumps(excluded_chunk_ids),
                    elapsed_ms,
                    model_connection_id,
                    generation_mode,
                    json.dumps(correction_evaluations),
                    conversation_id,
                    _serialize_datetime(now),
                ),
            )
            connection.executemany(
                """
                INSERT INTO conversation_messages (
                    message_id, conversation_id, role, content,
                    rag_execution_id, citations_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        f"msg_{uuid4().hex[:12]}",
                        conversation_id,
                        "user",
                        question,
                        rag_execution_id,
                        "[]",
                        _serialize_datetime(now),
                    ),
                    (
                        f"msg_{uuid4().hex[:12]}",
                        conversation_id,
                        "assistant",
                        answer,
                        rag_execution_id,
                        json.dumps(citations),
                        _serialize_datetime(now),
                    ),
                ],
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (_serialize_datetime(now), conversation_id),
            )
            connection.commit()

    def create_conversation(self, notebook_id: str, title: str) -> dict:
        now = utc_now()
        conversation_id = f"conv_{uuid4().hex[:12]}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (
                    conversation_id, notebook_id, title, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    notebook_id,
                    title,
                    _serialize_datetime(now),
                    _serialize_datetime(now),
                ),
            )
            connection.commit()
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise RuntimeError("Conversation was not persisted")
        return conversation

    def list_conversations(self, notebook_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT conversations.*, COUNT(conversation_messages.message_id) AS message_count
                FROM conversations
                LEFT JOIN conversation_messages
                    ON conversation_messages.conversation_id = conversations.conversation_id
                WHERE conversations.notebook_id = ?
                GROUP BY conversations.conversation_id
                ORDER BY conversations.updated_at DESC
                """,
                (notebook_id,),
            ).fetchall()
        return [self._conversation_from_row(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT conversations.*, COUNT(conversation_messages.message_id) AS message_count
                FROM conversations
                LEFT JOIN conversation_messages
                    ON conversation_messages.conversation_id = conversations.conversation_id
                WHERE conversations.conversation_id = ?
                GROUP BY conversations.conversation_id
                """,
                (conversation_id,),
            ).fetchone()
        return self._conversation_from_row(row) if row is not None else None

    def list_conversation_messages(self, conversation_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [self._conversation_message_from_row(row) for row in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def list_rag_executions(self, notebook_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM rag_executions
                WHERE notebook_id = ?
                ORDER BY created_at DESC
                """,
                (notebook_id,),
            ).fetchall()
        return [self._rag_execution_from_row(row) for row in rows]

    def get_rag_execution(self, rag_execution_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM rag_executions WHERE rag_execution_id = ?",
                (rag_execution_id,),
            ).fetchone()
        return self._rag_execution_from_row(row) if row is not None else None

    def create_search_profile(
        self,
        notebook_id: str,
        name: str,
        retrievers: list[dict],
        self_corrective_enabled: bool,
        final_context_limit: int,
    ) -> dict:
        now = utc_now()
        profile_id = f"sp_{uuid4().hex[:12]}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO search_profiles (
                    profile_id,
                    notebook_id,
                    name,
                    retrievers_json,
                    self_corrective_enabled,
                    final_context_limit,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    notebook_id,
                    name,
                    json.dumps(retrievers),
                    1 if self_corrective_enabled else 0,
                    final_context_limit,
                    _serialize_datetime(now),
                    _serialize_datetime(now),
                ),
            )
            connection.commit()
        profile = self.get_search_profile(profile_id)
        if profile is None:
            raise RuntimeError("Search profile was not persisted")
        return profile

    def list_search_profiles(self, notebook_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM search_profiles
                WHERE notebook_id = ?
                ORDER BY created_at ASC
                """,
                (notebook_id,),
            ).fetchall()
        return [self._search_profile_from_row(row) for row in rows]

    def get_search_profile(self, profile_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM search_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        return self._search_profile_from_row(row) if row is not None else None

    def delete_search_profile(self, profile_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM search_profiles WHERE profile_id = ?",
                (profile_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def create_model_connection(
        self,
        workspace_id: str,
        name: str,
        provider: str,
        base_url: str,
        model_id: str,
        api_key: str,
        capabilities: list[str],
    ) -> dict:
        now = utc_now()
        connection_id = f"mc_{uuid4().hex[:12]}"
        api_key_hint = self._api_key_hint(api_key)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO model_connections (
                    connection_id,
                    workspace_id,
                    name,
                    provider,
                    base_url,
                    model_id,
                    api_key_hint,
                    capabilities_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    connection_id,
                    workspace_id,
                    name,
                    provider,
                    base_url,
                    model_id,
                    api_key_hint,
                    json.dumps(capabilities),
                    _serialize_datetime(now),
                    _serialize_datetime(now),
                ),
            )
            connection.commit()
        model_connection = self.get_model_connection(connection_id)
        if model_connection is None:
            raise RuntimeError("Model connection was not persisted")
        return model_connection

    def list_model_connections(self, workspace_id: str = "default") -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM model_connections
                WHERE workspace_id = ?
                ORDER BY created_at ASC
                """,
                (workspace_id,),
            ).fetchall()
        return [self._model_connection_from_row(row) for row in rows]

    def get_model_connection(self, connection_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_connections WHERE connection_id = ?",
                (connection_id,),
            ).fetchone()
        return self._model_connection_from_row(row) if row is not None else None

    def delete_model_connection(self, connection_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM model_connections WHERE connection_id = ?",
                (connection_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def reset(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                DELETE FROM model_connections;
                DELETE FROM rag_executions;
                DELETE FROM conversation_messages;
                DELETE FROM conversations;
                DELETE FROM search_profiles;
                DELETE FROM chunks;
                DELETE FROM documents;
                DELETE FROM notebooks;
                """
            )
            connection.commit()

    def _notebook_from_row(self, row: sqlite3.Row) -> Notebook:
        return Notebook(
            notebook_id=row["notebook_id"],
            title=row["title"],
            description=row["description"],
            document_count=int(row["document_count"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def _document_from_row(self, row: sqlite3.Row) -> Document:
        return Document(
            document_id=row["document_id"],
            notebook_id=row["notebook_id"],
            file_name=row["file_name"],
            title=row["title"],
            status=row["status"],
            chunk_count=int(row["chunk_count"]),
            embedded_chunk_count=(
                int(row["embedded_chunk_count"])
                if "embedded_chunk_count" in row.keys()
                else 0
            ),
            mime_type=row["mime_type"],
            file_size=int(row["file_size"]),
            file_hash=row["file_hash"],
            storage_object_key=row["storage_object_key"],
            tags=json.loads(row["tags_json"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def _chunk_from_row(self, row: sqlite3.Row) -> ChunkDocument:
        return ChunkDocument(
            tenant_id=row["tenant_id"],
            workspace_id=row["workspace_id"],
            notebook_id=row["notebook_id"],
            document_id=row["document_id"],
            chunk_id=row["chunk_id"],
            content=row["content"],
            content_normalized=row["content_normalized"],
            embedding=json.loads(row["embedding_json"]) if row["embedding_json"] else None,
            metadata=json.loads(row["metadata_json"]),
            embedded_at=_parse_datetime(row["embedded_at"]) if row["embedded_at"] else None,
        )

    def _rag_execution_from_row(self, row: sqlite3.Row) -> dict:
        return {
            "rag_execution_id": row["rag_execution_id"],
            "notebook_id": row["notebook_id"],
            "question": row["question"],
            "standalone_query": row["standalone_query"],
            "answer": row["answer"],
            "citations": json.loads(row["citations_json"]),
            "search": json.loads(row["search_json"]),
            "self_corrective_enabled": bool(row["self_corrective_enabled"]),
            "excluded_chunk_ids": json.loads(row["excluded_chunk_ids_json"]),
            "elapsed_ms": float(row["elapsed_ms"]),
            "model_connection_id": row["model_connection_id"],
            "generation_mode": row["generation_mode"],
            "correction_evaluations": json.loads(row["correction_evaluations_json"]),
            "conversation_id": row["conversation_id"],
            "created_at": _parse_datetime(row["created_at"]),
        }

    def _conversation_from_row(self, row: sqlite3.Row) -> dict:
        return {
            "conversation_id": row["conversation_id"],
            "notebook_id": row["notebook_id"],
            "title": row["title"],
            "message_count": int(row["message_count"]),
            "created_at": _parse_datetime(row["created_at"]),
            "updated_at": _parse_datetime(row["updated_at"]),
        }

    def _conversation_message_from_row(self, row: sqlite3.Row) -> dict:
        return {
            "message_id": row["message_id"],
            "conversation_id": row["conversation_id"],
            "role": row["role"],
            "content": row["content"],
            "rag_execution_id": row["rag_execution_id"],
            "citations": json.loads(row["citations_json"]),
            "created_at": _parse_datetime(row["created_at"]),
        }

    def _search_profile_from_row(self, row: sqlite3.Row) -> dict:
        return {
            "profile_id": row["profile_id"],
            "notebook_id": row["notebook_id"],
            "name": row["name"],
            "retrievers": json.loads(row["retrievers_json"]),
            "self_corrective_enabled": bool(row["self_corrective_enabled"]),
            "final_context_limit": int(row["final_context_limit"]),
            "created_at": _parse_datetime(row["created_at"]),
            "updated_at": _parse_datetime(row["updated_at"]),
        }

    def _model_connection_from_row(self, row: sqlite3.Row) -> dict:
        return {
            "connection_id": row["connection_id"],
            "workspace_id": row["workspace_id"],
            "name": row["name"],
            "provider": row["provider"],
            "base_url": row["base_url"],
            "model_id": row["model_id"],
            "api_key_hint": row["api_key_hint"],
            "capabilities": json.loads(row["capabilities_json"]),
            "created_at": _parse_datetime(row["created_at"]),
            "updated_at": _parse_datetime(row["updated_at"]),
        }

    def _api_key_hint(self, api_key: str) -> str:
        if not api_key:
            return "not-set"
        if len(api_key) <= 8:
            return "*" * len(api_key)
        return f"{api_key[:3]}...{api_key[-4:]}"

    def _ensure_document_columns(self, connection: sqlite3.Connection) -> None:
        existing = {
            row["name"] for row in connection.execute("PRAGMA table_info(documents)").fetchall()
        }
        migrations = {
            "mime_type": "ALTER TABLE documents ADD COLUMN mime_type TEXT NOT NULL DEFAULT 'text/plain'",
            "file_size": "ALTER TABLE documents ADD COLUMN file_size INTEGER NOT NULL DEFAULT 0",
            "file_hash": "ALTER TABLE documents ADD COLUMN file_hash TEXT NOT NULL DEFAULT ''",
            "storage_object_key": (
                "ALTER TABLE documents ADD COLUMN storage_object_key TEXT NOT NULL DEFAULT ''"
            ),
        }
        for column, statement in migrations.items():
            if column not in existing:
                connection.execute(statement)

    def _ensure_rag_execution_columns(self, connection: sqlite3.Connection) -> None:
        existing = {
            row["name"] for row in connection.execute("PRAGMA table_info(rag_executions)").fetchall()
        }
        migrations = {
            "model_connection_id": "ALTER TABLE rag_executions ADD COLUMN model_connection_id TEXT",
            "generation_mode": (
                "ALTER TABLE rag_executions ADD COLUMN generation_mode TEXT NOT NULL "
                "DEFAULT 'placeholder'"
            ),
            "correction_evaluations_json": (
                "ALTER TABLE rag_executions ADD COLUMN correction_evaluations_json TEXT NOT NULL "
                "DEFAULT '[]'"
            ),
            "conversation_id": "ALTER TABLE rag_executions ADD COLUMN conversation_id TEXT",
        }
        for column, statement in migrations.items():
            if column not in existing:
                connection.execute(statement)

    def _insert_default_search_profiles(
        self,
        connection: sqlite3.Connection,
        notebook_id: str,
        now: datetime,
    ) -> None:
        profiles = [
            (
                f"sp_{uuid4().hex[:12]}",
                "Fast BM25",
                [{"mode": "bm25", "top_k": 5, "weight": 1.0}],
                0,
                5,
            ),
            (
                f"sp_{uuid4().hex[:12]}",
                "Semantic Vector",
                [{"mode": "vector", "top_k": 5, "weight": 1.0}],
                0,
                5,
            ),
            (
                f"sp_{uuid4().hex[:12]}",
                "Balanced RAG",
                [
                    {"mode": "bm25", "top_k": 5, "weight": 1.0},
                    {"mode": "vector", "top_k": 5, "weight": 1.0},
                ],
                1,
                8,
            ),
        ]
        connection.executemany(
            """
            INSERT INTO search_profiles (
                profile_id,
                notebook_id,
                name,
                retrievers_json,
                self_corrective_enabled,
                final_context_limit,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    profile_id,
                    notebook_id,
                    name,
                    json.dumps(retrievers),
                    self_corrective_enabled,
                    final_context_limit,
                    _serialize_datetime(now),
                    _serialize_datetime(now),
                )
                for (
                    profile_id,
                    name,
                    retrievers,
                    self_corrective_enabled,
                    final_context_limit,
                ) in profiles
            ],
        )


workspace_store = WorkspaceStore()
