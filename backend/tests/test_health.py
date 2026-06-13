from fastapi.testclient import TestClient

from app.main import create_app


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
