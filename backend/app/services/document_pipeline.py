from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.domain.chunk import ChunkDocument
from app.domain.workspace import Document
from app.services.document_parser import document_parser
from app.services.local_storage import local_storage
from app.services.workspace_store import workspace_store


class DocumentPipeline:
    def ingest_text(
        self,
        notebook_id: str,
        file_name: str,
        title: str,
        content: str,
        tags: list[str],
    ) -> Document:
        content_bytes = content.encode("utf-8")
        return self._persist_document(
            notebook_id=notebook_id,
            file_name=file_name,
            title=title,
            content=content,
            source_bytes=content_bytes,
            mime_type="text/plain",
            tags=tags,
        )

    def ingest_file(
        self,
        notebook_id: str,
        file_name: str,
        title: str,
        source_bytes: bytes,
        mime_type: str,
        tags: list[str],
    ) -> Document:
        content = document_parser.parse(file_name, source_bytes)
        return self._persist_document(
            notebook_id=notebook_id,
            file_name=file_name,
            title=title,
            content=content,
            source_bytes=source_bytes,
            mime_type=mime_type,
            tags=tags,
        )

    def delete_document(self, document_id: str) -> bool:
        document = workspace_store.get_document(document_id)
        if document is None:
            return False
        deleted = workspace_store.delete_document(document_id)
        if deleted:
            local_storage.delete(document.storage_object_key)
        return deleted

    def delete_notebook(self, notebook_id: str) -> bool:
        documents = workspace_store.list_documents(notebook_id=notebook_id)
        deleted = workspace_store.delete_notebook(notebook_id)
        if deleted:
            for document in documents:
                local_storage.delete(document.storage_object_key)
        return deleted

    def _persist_document(
        self,
        notebook_id: str,
        file_name: str,
        title: str,
        content: str,
        source_bytes: bytes,
        mime_type: str,
        tags: list[str],
    ) -> Document:
        document_id = f"doc_{uuid4().hex[:12]}"
        safe_name = Path(file_name).name
        object_key = f"{notebook_id}/{document_id}/{safe_name}"
        file_hash = sha256(source_bytes).hexdigest()
        duplicate = workspace_store.get_document_by_hash(notebook_id, file_hash)
        if duplicate is not None:
            raise FileExistsError(
                f"The same file is already indexed as {duplicate.file_name} ({duplicate.document_id})"
            )
        local_storage.save(object_key, source_bytes)
        chunks = self._chunk_text(
            notebook_id=notebook_id,
            document_id=document_id,
            title=title,
            content=content,
            tags=tags,
        )
        document = Document(
            document_id=document_id,
            notebook_id=notebook_id,
            file_name=safe_name,
            title=title,
            status="indexed",
            chunk_count=len(chunks),
            mime_type=mime_type,
            file_size=len(source_bytes),
            file_hash=file_hash,
            storage_object_key=object_key,
            tags=tags,
        )
        try:
            return workspace_store.add_document(document=document, chunks=chunks)
        except Exception:
            local_storage.delete(object_key)
            raise

    def _chunk_text(
        self,
        notebook_id: str,
        document_id: str,
        title: str,
        content: str,
        tags: list[str],
    ) -> list[ChunkDocument]:
        paragraphs = [paragraph.strip() for paragraph in content.splitlines() if paragraph.strip()]
        if not paragraphs:
            paragraphs = [content.strip()]

        chunks: list[ChunkDocument] = []
        for order, paragraph in enumerate(paragraphs, start=1):
            chunk = ChunkDocument(
                tenant_id="local",
                workspace_id="default",
                notebook_id=notebook_id,
                document_id=document_id,
                chunk_id=f"chk_{uuid4().hex[:12]}",
                content=paragraph,
                content_normalized=paragraph.lower(),
                metadata={
                    "document_title": title,
                    "section_title": f"Section {order}",
                    "page_start": order,
                    "chunk_order": order,
                    "tags": tags,
                },
            )
            chunks.append(chunk)
        return chunks


document_pipeline = DocumentPipeline()
