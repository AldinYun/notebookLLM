from fastapi.testclient import TestClient

from app.main import create_app
from app.services.workspace_store import WorkspaceStore, workspace_store


def setup_function() -> None:
    workspace_store.reset()


def test_health_check() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_text_ingestion_search_and_rag_flow() -> None:
    client = TestClient(create_app())

    notebook_response = client.post(
        "/notebooks",
        json={"title": "MVP Research", "description": "NotebookLM style requirements"},
    )
    assert notebook_response.status_code == 201
    notebook_id = notebook_response.json()["notebook_id"]

    document_response = client.post(
        "/documents/ingest-text",
        json={
            "notebook_id": notebook_id,
            "file_name": "requirements.md",
            "title": "Insight Notebook Requirements",
            "content": "OpenSearch enables BM25 and vector retrieval.\nRAG answers require citations.",
            "tags": ["mvp", "rag"],
        },
    )
    assert document_response.status_code == 201
    assert document_response.json()["chunk_count"] == 2

    search_response = client.post(
        "/search",
        json={
            "notebook_id": notebook_id,
            "query": "BM25 vector retrieval",
            "retrievers": [{"mode": "bm25", "top_k": 5}, {"mode": "vector", "top_k": 5}],
        },
    )
    assert search_response.status_code == 200
    assert search_response.json()["hits"]

    rag_response = client.post(
        "/rag/run",
        json={
            "notebook_id": notebook_id,
            "question": "How does retrieval work?",
            "self_corrective_enabled": True,
        },
    )
    assert rag_response.status_code == 200
    assert "answer" in rag_response.json()


def test_workspace_store_persists_documents(tmp_path) -> None:
    db_path = tmp_path / "workspace.db"
    first_store = WorkspaceStore(str(db_path))

    notebook = first_store.create_notebook("Persistent Notebook", "SQLite backed")
    document_response = client_document_fixture(first_store, notebook.notebook_id)

    second_store = WorkspaceStore(str(db_path))

    notebooks = second_store.list_notebooks()
    documents = second_store.list_documents(notebook_id=notebook.notebook_id)
    chunks = second_store.list_chunks(notebook_id=notebook.notebook_id)

    assert notebooks[0].document_count == 1
    assert documents[0].document_id == document_response.document_id
    assert len(chunks) == 2


def client_document_fixture(store: WorkspaceStore, notebook_id: str):
    from app.domain.chunk import ChunkDocument
    from app.domain.workspace import Document

    document = Document(
        document_id="doc_test",
        notebook_id=notebook_id,
        file_name="persistent.md",
        title="Persistent Document",
        status="indexed",
        chunk_count=2,
        tags=["test"],
    )
    chunks = [
        ChunkDocument(
            tenant_id="local",
            workspace_id="default",
            notebook_id=notebook_id,
            document_id=document.document_id,
            chunk_id="chk_one",
            content="BM25 retrieval persists.",
            content_normalized="bm25 retrieval persists.",
            metadata={
                "document_title": document.title,
                "section_title": "Section 1",
                "page_start": 1,
            },
        ),
        ChunkDocument(
            tenant_id="local",
            workspace_id="default",
            notebook_id=notebook_id,
            document_id=document.document_id,
            chunk_id="chk_two",
            content="Vector retrieval persists.",
            content_normalized="vector retrieval persists.",
            metadata={
                "document_title": document.title,
                "section_title": "Section 2",
                "page_start": 2,
            },
        ),
    ]
    return store.add_document(document, chunks)
