from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Notebook:
    notebook_id: str
    title: str
    description: str = ""
    document_count: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class Document:
    document_id: str
    notebook_id: str
    file_name: str
    title: str
    status: str
    chunk_count: int
    mime_type: str = "text/plain"
    file_size: int = 0
    file_hash: str = ""
    storage_object_key: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
