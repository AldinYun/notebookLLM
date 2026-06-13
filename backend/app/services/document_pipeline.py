from uuid import uuid4

from app.domain.chunk import ChunkDocument
from app.domain.workspace import Document
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
        document_id = f"doc_{uuid4().hex[:12]}"
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
            file_name=file_name,
            title=title,
            status="indexed",
            chunk_count=len(chunks),
            tags=tags,
        )
        return workspace_store.add_document(document=document, chunks=chunks)

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

