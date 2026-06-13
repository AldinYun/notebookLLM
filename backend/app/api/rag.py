from fastapi import APIRouter, HTTPException, status

from app.api.schemas import RagRunRequest, RagRunResponse
from app.services.rag_runtime import rag_runtime
from app.services.workspace_store import workspace_store

router = APIRouter()


@router.post("/run", response_model=RagRunResponse)
async def run_rag(payload: RagRunRequest) -> RagRunResponse:
    if workspace_store.get_notebook(payload.notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    result = rag_runtime.run(payload)
    return RagRunResponse.model_validate(result)

