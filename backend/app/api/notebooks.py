from fastapi import APIRouter, HTTPException, Response, status

from app.api.schemas import NotebookCreate, NotebookResponse
from app.services.workspace_store import workspace_store
from app.services.document_pipeline import document_pipeline

router = APIRouter()


@router.get("", response_model=list[NotebookResponse])
async def list_notebooks() -> list[NotebookResponse]:
    return [NotebookResponse.model_validate(notebook) for notebook in workspace_store.list_notebooks()]


@router.post("", response_model=NotebookResponse, status_code=status.HTTP_201_CREATED)
async def create_notebook(payload: NotebookCreate) -> NotebookResponse:
    notebook = workspace_store.create_notebook(title=payload.title, description=payload.description)
    return NotebookResponse.model_validate(notebook)


@router.get("/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(notebook_id: str) -> NotebookResponse:
    notebook = workspace_store.get_notebook(notebook_id)
    if notebook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    return NotebookResponse.model_validate(notebook)


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(notebook_id: str) -> Response:
    if not document_pipeline.delete_notebook(notebook_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
