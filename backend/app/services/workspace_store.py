from collections import defaultdict
from uuid import uuid4

from app.domain.chunk import ChunkDocument
from app.domain.workspace import Document, Notebook, utc_now


class WorkspaceStore:
    def __init__(self) -> None:
        self._notebooks: dict[str, Notebook] = {}
        self._documents: dict[str, Document] = {}
        self._chunks_by_notebook: dict[str, list[ChunkDocument]] = defaultdict(list)

    def create_notebook(self, title: str, description: str = "") -> Notebook:
        notebook = Notebook(notebook_id=f"nb_{uuid4().hex[:12]}", title=title, description=description)
        self._notebooks[notebook.notebook_id] = notebook
        return notebook

    def list_notebooks(self) -> list[Notebook]:
        return sorted(self._notebooks.values(), key=lambda notebook: notebook.created_at)

    def get_notebook(self, notebook_id: str) -> Notebook | None:
        return self._notebooks.get(notebook_id)

    def add_document(self, document: Document, chunks: list[ChunkDocument]) -> Document:
        self._documents[document.document_id] = document
        self._chunks_by_notebook[document.notebook_id].extend(chunks)
        notebook = self._notebooks[document.notebook_id]
        notebook.document_count += 1
        notebook.updated_at = utc_now()
        return document

    def list_documents(self, notebook_id: str | None = None) -> list[Document]:
        documents = self._documents.values()
        if notebook_id is not None:
            documents = [document for document in documents if document.notebook_id == notebook_id]
        return sorted(documents, key=lambda document: document.created_at)

    def get_document(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    def list_chunks(self, notebook_id: str) -> list[ChunkDocument]:
        return list(self._chunks_by_notebook.get(notebook_id, []))


workspace_store = WorkspaceStore()

