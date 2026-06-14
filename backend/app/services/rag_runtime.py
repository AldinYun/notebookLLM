from collections.abc import Iterator
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from app.api.schemas import CitationResponse, RagRunRequest, RetrieverRequest, SearchRequest
from app.services.model_gateway import ModelGatewayError, model_gateway
from app.services.search_service import SearchResult, search_service
from app.services.workspace_store import workspace_store


@dataclass(frozen=True)
class PreparedRag:
    rag_execution_id: str
    standalone_query: str
    search: SearchResult
    citations: list[CitationResponse]
    excluded_chunk_ids: list[str]
    correction_evaluations: list[dict]


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
    correction_evaluations: list[dict]


class RagRuntime:
    def run(self, request: RagRunRequest) -> RagRunResult:
        started_at = perf_counter()
        prepared = self._prepare(request)
        connection = self._get_model_connection(request.model_connection_id)
        if connection is not None:
            answer = model_gateway.generate(
                connection=connection,
                question=request.question,
                citations=[citation.model_dump() for citation in prepared.citations],
                api_key=request.model_api_key,
            )
            generation_mode = "model"
        else:
            answer = self._compose_placeholder(request.question, prepared.citations)
            generation_mode = "placeholder"

        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        self._save_execution(request, prepared, answer, elapsed_ms, generation_mode)
        return RagRunResult(
            rag_execution_id=prepared.rag_execution_id,
            question=request.question,
            standalone_query=prepared.standalone_query,
            answer=answer,
            citations=prepared.citations,
            search=prepared.search,
            self_corrective_enabled=request.self_corrective_enabled,
            excluded_chunk_ids=prepared.excluded_chunk_ids,
            elapsed_ms=elapsed_ms,
            model_connection_id=request.model_connection_id,
            generation_mode=generation_mode,
            correction_evaluations=prepared.correction_evaluations,
        )

    def stream(self, request: RagRunRequest) -> Iterator[dict]:
        started_at = perf_counter()
        prepared = self._prepare(request)
        connection = self._get_model_connection(request.model_connection_id)
        generation_mode = "model" if connection is not None else "placeholder"
        yield {
            "event": "metadata",
            "rag_execution_id": prepared.rag_execution_id,
            "standalone_query": prepared.standalone_query,
            "citations": [citation.model_dump() for citation in prepared.citations],
            "search": self._search_payload(prepared.search),
            "generation_mode": generation_mode,
            "model_connection_id": request.model_connection_id,
            "self_corrective_enabled": request.self_corrective_enabled,
            "excluded_chunk_ids": prepared.excluded_chunk_ids,
            "correction_evaluations": prepared.correction_evaluations,
        }

        answer_parts: list[str] = []
        try:
            if connection is not None:
                token_stream = model_gateway.stream_generate(
                    connection=connection,
                    question=request.question,
                    citations=[citation.model_dump() for citation in prepared.citations],
                    api_key=request.model_api_key,
                )
            else:
                placeholder = self._compose_placeholder(request.question, prepared.citations)
                token_stream = (f"{word} " for word in placeholder.split())

            for token in token_stream:
                answer_parts.append(token)
                yield {"event": "token", "content": token}
        except ModelGatewayError as error:
            yield {"event": "error", "detail": str(error)}
            return

        answer = "".join(answer_parts).strip()
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        self._save_execution(request, prepared, answer, elapsed_ms, generation_mode)
        yield {
            "event": "done",
            "rag_execution_id": prepared.rag_execution_id,
            "answer": answer,
            "elapsed_ms": elapsed_ms,
        }

    def _prepare(self, request: RagRunRequest) -> PreparedRag:
        standalone_query = request.question.strip()
        retrievers = request.retrievers
        if request.self_corrective_enabled:
            retrievers = [
                RetrieverRequest(
                    mode=retriever.mode,
                    top_k=min(retriever.top_k * 3, 20),
                    weight=retriever.weight,
                )
                for retriever in request.retrievers
            ]
        search_result = search_service.search(
            SearchRequest(
                notebook_id=request.notebook_id,
                query=standalone_query,
                retrievers=retrievers,
            )
        )
        selected_hits = []
        excluded_chunk_ids: list[str] = []
        correction_evaluations: list[dict] = []
        seen_chunk_ids: set[str] = set()
        query_terms = set(self._terms(standalone_query))
        for hit in search_result.hits:
            if hit.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(hit.chunk_id)
            if request.self_corrective_enabled:
                relevance_score = len(set(hit.matched_terms)) / max(len(query_terms), 1)
                if relevance_score >= 0.67:
                    label = "relevant"
                    included = True
                elif relevance_score >= 0.34:
                    label = "partially_relevant"
                    included = True
                else:
                    label = "irrelevant"
                    included = False
                correction_evaluations.append(
                    {
                        "chunk_id": hit.chunk_id,
                        "label": label,
                        "relevance_score": round(relevance_score, 4),
                        "reason": (
                            f"Matched {len(set(hit.matched_terms))} of {len(query_terms)} query terms"
                        ),
                        "included": included,
                    }
                )
                if not included:
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
        return PreparedRag(
            rag_execution_id=f"rag_{uuid4().hex[:12]}",
            standalone_query=standalone_query,
            search=search_result,
            citations=citations,
            excluded_chunk_ids=excluded_chunk_ids,
            correction_evaluations=correction_evaluations,
        )

    def _get_model_connection(self, connection_id: str | None) -> dict | None:
        if connection_id is None:
            return None
        connection = workspace_store.get_model_connection(connection_id)
        if connection is None:
            raise ModelGatewayError("Model connection not found")
        return connection

    def _save_execution(
        self,
        request: RagRunRequest,
        prepared: PreparedRag,
        answer: str,
        elapsed_ms: float,
        generation_mode: str,
    ) -> None:
        workspace_store.add_rag_execution(
            rag_execution_id=prepared.rag_execution_id,
            notebook_id=request.notebook_id,
            question=request.question,
            standalone_query=prepared.standalone_query,
            answer=answer,
            citations=[citation.model_dump() for citation in prepared.citations],
            search=self._search_payload(prepared.search),
            self_corrective_enabled=request.self_corrective_enabled,
            excluded_chunk_ids=prepared.excluded_chunk_ids,
            elapsed_ms=elapsed_ms,
            model_connection_id=request.model_connection_id,
            generation_mode=generation_mode,
            correction_evaluations=prepared.correction_evaluations,
        )

    def _search_payload(self, search_result: SearchResult) -> dict:
        return {
            "query": search_result.query,
            "elapsed_ms": search_result.elapsed_ms,
            "retriever_summaries": search_result.retriever_summaries,
            "hits": [hit.__dict__ for hit in search_result.hits],
        }

    def _compose_placeholder(self, question: str, citations: list[CitationResponse]) -> str:
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

    def _terms(self, text: str) -> list[str]:
        normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
        return [term for term in normalized.split() if len(term) > 1]


rag_runtime = RagRuntime()
