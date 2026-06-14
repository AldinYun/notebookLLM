from fastapi import APIRouter, HTTPException, status

from app.api.schemas import RagExecutionResponse, RagRunRequest, RagRunResponse
from app.services.rag_runtime import rag_runtime
from app.services.model_gateway import ModelGatewayError
from app.services.workspace_store import workspace_store

router = APIRouter()


@router.post("/run", response_model=RagRunResponse)
async def run_rag(payload: RagRunRequest) -> RagRunResponse:
    if workspace_store.get_notebook(payload.notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    try:
        result = rag_runtime.run(payload)
    except ModelGatewayError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return RagRunResponse.model_validate(result)


@router.get("/executions", response_model=list[RagExecutionResponse])
async def list_rag_executions(notebook_id: str) -> list[RagExecutionResponse]:
    if workspace_store.get_notebook(notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    executions = workspace_store.list_rag_executions(notebook_id)
    return [RagExecutionResponse.model_validate(execution) for execution in executions]


@router.get("/executions/{rag_execution_id}", response_model=RagExecutionResponse)
async def get_rag_execution(rag_execution_id: str) -> RagExecutionResponse:
    execution = workspace_store.get_rag_execution(rag_execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG execution not found")

    return RagExecutionResponse.model_validate(execution)
