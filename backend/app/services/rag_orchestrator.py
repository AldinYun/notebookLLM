from dataclasses import dataclass

from app.domain.rag_profile import RagProfile


@dataclass(frozen=True)
class RagRequest:
    tenant_id: str
    workspace_id: str
    notebook_id: str
    question: str
    profile: RagProfile


@dataclass(frozen=True)
class RagPlan:
    standalone_query: str
    retriever_count: int
    self_corrective_enabled: bool
    final_context_limit: int


class RagOrchestrator:
    """Coordinates retrieval, correction, augmentation, and generation."""

    async def plan(self, request: RagRequest) -> RagPlan:
        return RagPlan(
            standalone_query=request.question,
            retriever_count=len(request.profile.retrievers),
            self_corrective_enabled=request.profile.self_corrective_enabled,
            final_context_limit=request.profile.final_context_limit,
        )

