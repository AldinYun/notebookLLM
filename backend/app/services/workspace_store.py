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
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_documents_notebook_id
                    ON documents(notebook_id);

                CREATE INDEX IF NOT EXISTS idx_chunks_notebook_id
                    ON chunks(notebook_id);

                CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                    ON chunks(document_id);

                CREATE INDEX IF NOT EXISTS idx_rag_executions_notebook_id
                    ON rag_executions(notebook_id);
                """
            )
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
                    tags_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.document_id,
                    document.notebook_id,
                    document.file_name,
                    document.title,
                    document.status,
                    document.chunk_count,
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
        query = "SELECT * FROM documents"
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
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return self._document_from_row(row) if row is not None else None

    def list_chunks(self, notebook_id: str) -> list[ChunkDocument]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE notebook_id = ? ORDER BY rowid ASC",
                (notebook_id,),
            ).fetchall()
        return [self._chunk_from_row(row) for row in rows]

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
    ) -> None:
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
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    _serialize_datetime(utc_now()),
                ),
            )
            connection.commit()

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

    def reset(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                DELETE FROM rag_executions;
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
            "created_at": _parse_datetime(row["created_at"]),
        }


workspace_store = WorkspaceStore()
