from fastapi import APIRouter, HTTPException, Response, status

from app.api.schemas import (
    ConversationCreate,
    ConversationMessageResponse,
    ConversationResponse,
)
from app.services.workspace_store import workspace_store

router = APIRouter()


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(notebook_id: str) -> list[ConversationResponse]:
    if workspace_store.get_notebook(notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    return [
        ConversationResponse.model_validate(conversation)
        for conversation in workspace_store.list_conversations(notebook_id)
    ]


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate) -> ConversationResponse:
    if workspace_store.get_notebook(payload.notebook_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    conversation = workspace_store.create_conversation(payload.notebook_id, payload.title)
    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str) -> ConversationResponse:
    conversation = workspace_store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
async def list_conversation_messages(
    conversation_id: str,
) -> list[ConversationMessageResponse]:
    if workspace_store.get_conversation(conversation_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return [
        ConversationMessageResponse.model_validate(message)
        for message in workspace_store.list_conversation_messages(conversation_id)
    ]


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str) -> Response:
    if not workspace_store.delete_conversation(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
