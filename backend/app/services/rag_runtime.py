from dataclasses import dataclass
from time import perf_counter

from app.api.schemas import CitationResponse, RagRunRequest, SearchRequest
from app.services.search_service import SearchResult, search_service


@dataclass(frozen=True)
class RagRunResult:
    question: str
    standalone_query: str
    answer: str
    citations: list[CitationResponse]
    search: SearchResult
    self_corrective_enabled: bool
    excluded_chunk_ids: list[str]
    elapsed_ms: float


class RagRuntime:
    def run(self, request: RagRunRequest) -> RagRunResult:
        started_at = perf_counter()
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

        answer = self._compose_answer(request.question, citations)
        elapsed_ms = (perf_counter() - started_at) * 1000
        return RagRunResult(
            question=request.question,
            standalone_query=standalone_query,
            answer=answer,
            citations=citations,
            search=search_result,
            self_corrective_enabled=request.self_corrective_enabled,
            excluded_chunk_ids=excluded_chunk_ids,
            elapsed_ms=round(elapsed_ms, 2),
        )

    def _compose_answer(self, question: str, citations: list[CitationResponse]) -> str:
        if not citations:
            return (
                "업로드된 문서에서 질문과 직접 연결되는 근거를 찾지 못했습니다. "
                "문서를 추가하거나 검색 프로필을 넓혀 다시 시도하세요."
            )

        citation_list = ", ".join(citation.citation_id for citation in citations[:3])
        return (
            f"질문 '{question}'에 대해 현재 문서 근거 기준으로 답변 초안을 생성했습니다. "
            f"핵심 근거는 {citation_list}에서 확인할 수 있으며, 실제 LLM 연결 전까지는 "
            "검색된 청크와 사이테이션 구성을 검증하기 위한 플레이스홀더 응답입니다."
        )


rag_runtime = RagRuntime()

