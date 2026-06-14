from fastapi import APIRouter, HTTPException, Response, status

from app.api.schemas import SearchProfileCreate, SearchProfileResponse
from app.services.workspace_store import workspace_store

router = APIRouter()


@router.get("/search", response_model=list[SearchProfileResponse])
async def list_search_profiles(notebook_id: str) -> list[SearchProfileResponse]:
    if workspace_store.get_notebook(notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    profiles = workspace_store.list_search_profiles(notebook_id)
    return [SearchProfileResponse.model_validate(profile) for profile in profiles]


@router.post("/search", response_model=SearchProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_search_profile(payload: SearchProfileCreate) -> SearchProfileResponse:
    if workspace_store.get_notebook(payload.notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    profile = workspace_store.create_search_profile(
        notebook_id=payload.notebook_id,
        name=payload.name,
        retrievers=[retriever.model_dump() for retriever in payload.retrievers],
        self_corrective_enabled=payload.self_corrective_enabled,
        final_context_limit=payload.final_context_limit,
    )
    return SearchProfileResponse.model_validate(profile)


@router.get("/search/{profile_id}", response_model=SearchProfileResponse)
async def get_search_profile(profile_id: str) -> SearchProfileResponse:
    profile = workspace_store.get_search_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search profile not found")

    return SearchProfileResponse.model_validate(profile)


@router.delete("/search/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_profile(profile_id: str) -> Response:
    if not workspace_store.delete_search_profile(profile_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search profile not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
