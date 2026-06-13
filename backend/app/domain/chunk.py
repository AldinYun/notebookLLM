from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ChunkDocument:
    tenant_id: str
    workspace_id: str
    notebook_id: str
    document_id: str
    chunk_id: str
    content: str
    content_normalized: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    embedded_at: datetime | None = None

