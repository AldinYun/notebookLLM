from fastapi import APIRouter, HTTPException, status

from app.api.schemas import DocumentIngestRequest, DocumentResponse
from app.services.document_pipeline import document_pipeline
from app.services.workspace_store import workspace_store

router = APIRouter()


@router.get("", response_model=list[DocumentResponse])
async def list_documents(notebook_id: str | None = None) -> list[DocumentResponse]:
    documents = workspace_store.list_documents(notebook_id=notebook_id)
    return [DocumentResponse.model_validate(document) for document in documents]


@router.post("/ingest-text", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def ingest_text_document(payload: DocumentIngestRequest) -> DocumentResponse:
    if workspace_store.get_notebook(payload.notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    document = document_pipeline.ingest_text(
        notebook_id=payload.notebook_id,
        file_name=payload.file_name,
        title=payload.title,
        content=payload.content,
        tags=payload.tags,
    )
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str) -> DocumentResponse:
    document = workspace_store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(document)

