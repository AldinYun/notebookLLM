import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

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
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return RagRunResponse.model_validate(result)


@router.post("/stream", response_class=StreamingResponse)
async def stream_rag(payload: RagRunRequest) -> StreamingResponse:
    if workspace_store.get_notebook(payload.notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    if payload.conversation_id is not None:
        conversation = workspace_store.get_conversation(payload.conversation_id)
        if conversation is None or conversation["notebook_id"] != payload.notebook_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation not found in this notebook",
            )

    def event_stream():
        try:
            for event in rag_runtime.stream(payload):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except ModelGatewayError as error:
            event = {"event": "error", "detail": str(error)}
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
