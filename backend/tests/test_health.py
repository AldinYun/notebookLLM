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

    model_response = client.post(
        "/models/connections",
        json={
            "name": "Local vLLM",
            "provider": "openai-compatible",
            "base_url": "http://localhost:8001/v1",
            "model_id": "local-model",
            "api_key": "sk-test-secret",
            "capabilities": ["chat", "embedding"],
        },
    )
    assert model_response.status_code == 201
    assert model_response.json()["api_key_hint"] == "sk-...cret"

    notebook_response = client.post(
        "/notebooks",
        json={"title": "MVP Research", "description": "NotebookLM style requirements"},
    )
    assert notebook_response.status_code == 201
    notebook_id = notebook_response.json()["notebook_id"]

    profiles_response = client.get(f"/profiles/search?notebook_id={notebook_id}")
    assert profiles_response.status_code == 200
    assert [profile["name"] for profile in profiles_response.json()] == [
        "Fast BM25",
        "Semantic Vector",
        "Balanced RAG",
    ]

    custom_profile_response = client.post(
        "/profiles/search",
        json={
            "notebook_id": notebook_id,
            "name": "Hybrid Debug",
            "retrievers": [{"mode": "hybrid", "top_k": 10, "weight": 1.0}],
            "self_corrective_enabled": True,
            "final_context_limit": 8,
        },
    )
    assert custom_profile_response.status_code == 201

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
    rag_payload = rag_response.json()
    assert "answer" in rag_payload
    assert rag_payload["rag_execution_id"].startswith("rag_")

    history_response = client.get(f"/rag/executions?notebook_id={notebook_id}")
    assert history_response.status_code == 200
    assert history_response.json()[0]["rag_execution_id"] == rag_payload["rag_execution_id"]

    execution_response = client.get(f"/rag/executions/{rag_payload['rag_execution_id']}")
    assert execution_response.status_code == 200
    assert execution_response.json()["question"] == "How does retrieval work?"


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
