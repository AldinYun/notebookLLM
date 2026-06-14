from fastapi import APIRouter, HTTPException, status

from app.api.schemas import SearchRequest, SearchResponse
from app.services.search_service import search_service
from app.services.model_gateway import ModelGatewayError
from app.services.workspace_store import workspace_store

router = APIRouter()


@router.post("", response_model=SearchResponse)
async def search(payload: SearchRequest) -> SearchResponse:
    if workspace_store.get_notebook(payload.notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    try:
        result = search_service.search(payload)
    except ModelGatewayError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return SearchResponse.model_validate(result)
