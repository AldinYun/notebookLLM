from fastapi import APIRouter, HTTPException, Response, status

from app.api.schemas import ModelConnectionCreate, ModelConnectionResponse
from app.services.workspace_store import workspace_store

router = APIRouter()


@router.get("/connections", response_model=list[ModelConnectionResponse])
async def list_model_connections(workspace_id: str = "default") -> list[ModelConnectionResponse]:
    connections = workspace_store.list_model_connections(workspace_id=workspace_id)
    return [ModelConnectionResponse.model_validate(connection) for connection in connections]


@router.post(
    "/connections",
    response_model=ModelConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_model_connection(payload: ModelConnectionCreate) -> ModelConnectionResponse:
    connection = workspace_store.create_model_connection(
        workspace_id=payload.workspace_id,
        name=payload.name,
        provider=payload.provider,
        base_url=payload.base_url,
        model_id=payload.model_id,
        api_key=payload.api_key,
        capabilities=payload.capabilities,
    )
    return ModelConnectionResponse.model_validate(connection)


@router.get("/connections/{connection_id}", response_model=ModelConnectionResponse)
async def get_model_connection(connection_id: str) -> ModelConnectionResponse:
    connection = workspace_store.get_model_connection(connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model connection not found")
    return ModelConnectionResponse.model_validate(connection)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_connection(connection_id: str) -> Response:
    if not workspace_store.delete_model_connection(connection_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model connection not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
