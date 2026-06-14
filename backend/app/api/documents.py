from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse

from app.api.schemas import (
    DocumentEmbedRequest,
    DocumentEmbedResponse,
    DocumentIngestRequest,
    DocumentResponse,
)
from app.services.embedding_service import embedding_service
from app.services.model_gateway import ModelGatewayError
from app.services.document_pipeline import document_pipeline
from app.services.document_parser import UnsupportedDocumentFormat
from app.services.local_storage import local_storage
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

    try:
        document = document_pipeline.ingest_text(
            notebook_id=payload.notebook_id,
            file_name=payload.file_name,
            title=payload.title,
            content=payload.content,
            tags=payload.tags,
            embedding_connection_id=payload.embedding_connection_id,
            embedding_api_key=payload.embedding_api_key,
        )
    except ModelGatewayError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return DocumentResponse.model_validate(document)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    notebook_id: str,
    title: str,
    file_name: str,
    tags: str = "",
    embedding_connection_id: str | None = None,
    embedding_api_key: str = Header(default="", alias="X-Embedding-API-Key"),
) -> DocumentResponse:
    if workspace_store.get_notebook(notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    if not file_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")
    source_bytes = await request.body()
    if not source_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    try:
        document = document_pipeline.ingest_file(
            notebook_id=notebook_id,
            file_name=file_name,
            title=title,
            source_bytes=source_bytes,
            mime_type=request.headers.get("content-type", "application/octet-stream"),
            tags=[tag.strip() for tag in tags.split(",") if tag.strip()],
            embedding_connection_id=embedding_connection_id,
            embedding_api_key=embedding_api_key,
        )
    except FileExistsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ModelGatewayError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    except (UnsupportedDocumentFormat, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(error)) from error

    return DocumentResponse.model_validate(document)


@router.post("/{document_id}/embed", response_model=DocumentEmbedResponse)
async def embed_document(
    document_id: str,
    payload: DocumentEmbedRequest,
) -> DocumentEmbedResponse:
    if workspace_store.get_document(document_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        count = embedding_service.embed_document(
            document_id,
            payload.embedding_connection_id,
            payload.embedding_api_key,
        )
    except ModelGatewayError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return DocumentEmbedResponse(
        document_id=document_id,
        embedded_chunk_count=count,
        embedding_connection_id=payload.embedding_connection_id,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str) -> DocumentResponse:
    document = workspace_store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/source", response_class=FileResponse)
async def download_document_source(document_id: str) -> FileResponse:
    document = workspace_store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    source_path = local_storage.get_path(document.storage_object_key)
    if source_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found")
    return FileResponse(
        path=source_path,
        media_type=document.mime_type,
        filename=document.file_name,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str) -> Response:
    if not document_pipeline.delete_document(document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
