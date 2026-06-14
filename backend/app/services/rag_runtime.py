from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from app.api.schemas import CitationResponse, RagRunRequest, SearchRequest
from app.services.search_service import SearchResult, search_service
from app.services.model_gateway import ModelGatewayError, model_gateway
from app.services.workspace_store import workspace_store


@dataclass(frozen=True)
class RagRunResult:
    rag_execution_id: str
    question: str
    standalone_query: str
    answer: str
    citations: list[CitationResponse]
    search: SearchResult
    self_corrective_enabled: bool
    excluded_chunk_ids: list[str]
    elapsed_ms: float
    model_connection_id: str | None
    generation_mode: str


class RagRuntime:
    def run(self, request: RagRunRequest) -> RagRunResult:
        started_at = perf_counter()
        rag_execution_id = f"rag_{uuid4().hex[:12]}"
        standalone_query = request.question.strip()
        search_result = search_service.search(
            SearchRequest(
                notebook_id=request.notebook_id,
                query=standalone_query,
                retrievers=request.retrievers,
            )
        )

        selected_hits = []
        excluded_chunk_ids: list[str] = []
        seen_chunk_ids: set[str] = set()

        for hit in search_result.hits:
            if hit.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(hit.chunk_id)
            if request.self_corrective_enabled and hit.score <= 0:
                excluded_chunk_ids.append(hit.chunk_id)
                continue
            selected_hits.append(hit)
            if len(selected_hits) >= request.final_context_limit:
                break

        citations = [
            CitationResponse(
                citation_id=f"C{index}",
                document_title=hit.document_title,
                page_start=hit.page_start,
                section_title=hit.section_title,
                quote=hit.snippet,
            )
            for index, hit in enumerate(selected_hits, start=1)
        ]

        model_connection = None
        generation_mode = "placeholder"
        if request.model_connection_id:
            model_connection = workspace_store.get_model_connection(request.model_connection_id)
            if model_connection is None:
                raise ModelGatewayError("Model connection not found")
            answer = model_gateway.generate(
                connection=model_connection,
                question=request.question,
                citations=[citation.model_dump() for citation in citations],
                api_key=request.model_api_key,
            )
            generation_mode = "model"
        else:
            answer = self._compose_answer(request.question, citations)
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        result = RagRunResult(
            rag_execution_id=rag_execution_id,
            question=request.question,
            standalone_query=standalone_query,
            answer=answer,
            citations=citations,
            search=search_result,
            self_corrective_enabled=request.self_corrective_enabled,
            excluded_chunk_ids=excluded_chunk_ids,
            elapsed_ms=elapsed_ms,
            model_connection_id=request.model_connection_id,
            generation_mode=generation_mode,
        )
        workspace_store.add_rag_execution(
            rag_execution_id=rag_execution_id,
            notebook_id=request.notebook_id,
            question=request.question,
            standalone_query=standalone_query,
            answer=answer,
            citations=[citation.model_dump() for citation in citations],
            search={
                "query": search_result.query,
                "elapsed_ms": search_result.elapsed_ms,
                "retriever_summaries": search_result.retriever_summaries,
                "hits": [hit.__dict__ for hit in search_result.hits],
            },
            self_corrective_enabled=request.self_corrective_enabled,
            excluded_chunk_ids=excluded_chunk_ids,
            elapsed_ms=elapsed_ms,
            model_connection_id=request.model_connection_id,
            generation_mode=generation_mode,
        )
        return result

    def _compose_answer(self, question: str, citations: list[CitationResponse]) -> str:
        if not citations:
            return (
                "No directly relevant evidence was found in the indexed documents. "
                "Add documents or broaden the retrieval profile and try again."
            )

        citation_list = ", ".join(citation.citation_id for citation in citations[:3])
        return (
            f"Draft answer for '{question}' was generated from the current retrieved evidence. "
            f"Primary support is available in {citation_list}. This is a placeholder response "
            "until a real LLM model connection is configured."
        )


rag_runtime = RagRuntime()
