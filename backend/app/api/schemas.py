from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NotebookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = ""


class NotebookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notebook_id: str
    title: str
    description: str
    document_count: int
    created_at: datetime
    updated_at: datetime


class DocumentIngestRequest(BaseModel):
    notebook_id: str
    file_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    notebook_id: str
    file_name: str
    title: str
    status: str
    chunk_count: int
    mime_type: str
    file_size: int
    file_hash: str
    storage_object_key: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


RetrieverMode = Literal["text", "bm25", "vector", "hybrid"]


class RetrieverRequest(BaseModel):
    mode: RetrieverMode
    top_k: int = Field(default=5, ge=1, le=20)
    weight: float = Field(default=1.0, ge=0.0, le=10.0)


class SearchRequest(BaseModel):
    notebook_id: str
    query: str = Field(min_length=1)
    retrievers: list[RetrieverRequest] = Field(default_factory=lambda: [RetrieverRequest(mode="bm25")])


class SearchHitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_id: str
    document_title: str
    retriever: RetrieverMode
    rank: int
    score: float
    page_start: int
    section_title: str
    snippet: str
    matched_terms: list[str]


class SearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    elapsed_ms: float
    hits: list[SearchHitResponse]
    retriever_summaries: dict[str, int]


class RagRunRequest(BaseModel):
    notebook_id: str
    conversation_id: str | None = None
    question: str = Field(min_length=1)
    retrievers: list[RetrieverRequest] = Field(
        default_factory=lambda: [
            RetrieverRequest(mode="bm25", top_k=5),
            RetrieverRequest(mode="vector", top_k=5),
        ]
    )
    self_corrective_enabled: bool = False
    final_context_limit: int = Field(default=8, ge=1, le=20)
    model_connection_id: str | None = None
    model_api_key: str = Field(default="", max_length=500)


class CitationResponse(BaseModel):
    citation_id: str
    document_title: str
    page_start: int
    section_title: str
    quote: str


class CorrectionEvaluationResponse(BaseModel):
    chunk_id: str
    label: Literal["relevant", "partially_relevant", "irrelevant"]
    relevance_score: float
    reason: str
    included: bool


class RagRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rag_execution_id: str
    conversation_id: str | None
    question: str
    standalone_query: str
    answer: str
    citations: list[CitationResponse]
    search: SearchResponse
    self_corrective_enabled: bool
    excluded_chunk_ids: list[str]
    elapsed_ms: float
    model_connection_id: str | None
    generation_mode: Literal["placeholder", "model"]
    correction_evaluations: list[CorrectionEvaluationResponse]


class RagExecutionResponse(RagRunResponse):
    notebook_id: str
    created_at: datetime


class ConversationCreate(BaseModel):
    notebook_id: str
    title: str = Field(min_length=1, max_length=120)


class ConversationResponse(BaseModel):
    conversation_id: str
    notebook_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationMessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    rag_execution_id: str | None
    citations: list[CitationResponse]
    created_at: datetime


class SearchProfileCreate(BaseModel):
    notebook_id: str
    name: str = Field(min_length=1, max_length=120)
    retrievers: list[RetrieverRequest] = Field(min_length=1)
    self_corrective_enabled: bool = False
    final_context_limit: int = Field(default=8, ge=1, le=20)


class SearchProfileResponse(BaseModel):
    profile_id: str
    notebook_id: str
    name: str
    retrievers: list[RetrieverRequest]
    self_corrective_enabled: bool
    final_context_limit: int
    created_at: datetime
    updated_at: datetime


class ModelConnectionCreate(BaseModel):
    workspace_id: str = "default"
    name: str = Field(min_length=1, max_length=120)
    provider: str = Field(default="openai-compatible", min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=500)
    model_id: str = Field(min_length=1, max_length=160)
    api_key: str = Field(default="", max_length=500)
    capabilities: list[Literal["chat", "embedding", "evaluation"]] = Field(
        default_factory=lambda: ["chat"]
    )


class ModelConnectionResponse(BaseModel):
    connection_id: str
    workspace_id: str
    name: str
    provider: str
    base_url: str
    model_id: str
    api_key_hint: str
    capabilities: list[str]
    created_at: datetime
    updated_at: datetime


class ModelConnectionTestRequest(BaseModel):
    api_key: str = Field(default="", max_length=500)


class ModelConnectionTestResponse(BaseModel):
    status: Literal["ok"]
    models: list[str]
