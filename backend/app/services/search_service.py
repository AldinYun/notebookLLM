from collections import Counter, defaultdict
from dataclasses import dataclass
from time import perf_counter

from app.api.schemas import SearchRequest
from app.domain.chunk import ChunkDocument
from app.services.workspace_store import workspace_store


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    document_title: str
    retriever: str
    rank: int
    score: float
    page_start: int
    section_title: str
    snippet: str
    matched_terms: list[str]


@dataclass(frozen=True)
class SearchResult:
    query: str
    elapsed_ms: float
    hits: list[SearchHit]
    retriever_summaries: dict[str, int]


class SearchService:
    def search(self, request: SearchRequest) -> SearchResult:
        started_at = perf_counter()
        chunks = workspace_store.list_chunks(request.notebook_id)
        hits: list[SearchHit] = []

        for retriever in request.retrievers:
            ranked = self._rank_chunks(chunks, request.query, retriever.mode)
            for rank, (chunk, score, matched_terms) in enumerate(ranked[: retriever.top_k], start=1):
                hits.append(
                    SearchHit(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        document_title=str(chunk.metadata.get("document_title", "Untitled")),
                        retriever=retriever.mode,
                        rank=rank,
                        score=round(score * retriever.weight, 4),
                        page_start=int(chunk.metadata.get("page_start", 1)),
                        section_title=str(chunk.metadata.get("section_title", "")),
                        snippet=self._snippet(chunk.content, matched_terms),
                        matched_terms=matched_terms,
                    )
                )

        summaries = Counter(hit.retriever for hit in hits)
        elapsed_ms = (perf_counter() - started_at) * 1000
        return SearchResult(
            query=request.query,
            elapsed_ms=round(elapsed_ms, 2),
            hits=hits,
            retriever_summaries=dict(summaries),
        )

    def _rank_chunks(
        self,
        chunks: list[ChunkDocument],
        query: str,
        mode: str,
    ) -> list[tuple[ChunkDocument, float, list[str]]]:
        query_terms = self._terms(query)
        ranked: list[tuple[ChunkDocument, float, list[str]]] = []
        document_frequency = self._document_frequency(chunks)
        total_chunks = max(len(chunks), 1)

        for chunk in chunks:
            chunk_terms = self._terms(chunk.content_normalized)
            term_counts = Counter(chunk_terms)
            matched_terms = sorted(set(query_terms).intersection(chunk_terms))
            if not matched_terms:
                continue

            if mode == "text":
                score = len(matched_terms) / max(len(set(query_terms)), 1)
            elif mode == "vector":
                score = self._cosine_like_score(query_terms, chunk_terms)
            elif mode == "hybrid":
                score = 0.55 * self._bm25_like_score(
                    query_terms, term_counts, document_frequency, total_chunks
                ) + 0.45 * self._cosine_like_score(query_terms, chunk_terms)
            else:
                score = self._bm25_like_score(query_terms, term_counts, document_frequency, total_chunks)

            ranked.append((chunk, score, matched_terms))

        return sorted(ranked, key=lambda item: item[1], reverse=True)

    def _terms(self, text: str) -> list[str]:
        normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
        return [term for term in normalized.split() if len(term) > 1]

    def _document_frequency(self, chunks: list[ChunkDocument]) -> dict[str, int]:
        frequency: defaultdict[str, int] = defaultdict(int)
        for chunk in chunks:
            for term in set(self._terms(chunk.content_normalized)):
                frequency[term] += 1
        return dict(frequency)

    def _bm25_like_score(
        self,
        query_terms: list[str],
        term_counts: Counter[str],
        document_frequency: dict[str, int],
        total_chunks: int,
    ) -> float:
        score = 0.0
        for term in query_terms:
            if term_counts[term] == 0:
                continue
            inverse_frequency = total_chunks / (1 + document_frequency.get(term, 0))
            score += term_counts[term] * inverse_frequency
        return score

    def _cosine_like_score(self, query_terms: list[str], chunk_terms: list[str]) -> float:
        query_counter = Counter(query_terms)
        chunk_counter = Counter(chunk_terms)
        numerator = sum(query_counter[term] * chunk_counter[term] for term in query_counter)
        query_norm = sum(value * value for value in query_counter.values()) ** 0.5
        chunk_norm = sum(value * value for value in chunk_counter.values()) ** 0.5
        if query_norm == 0 or chunk_norm == 0:
            return 0.0
        return numerator / (query_norm * chunk_norm)

    def _snippet(self, content: str, matched_terms: list[str]) -> str:
        if not matched_terms:
            return content[:260]
        lowered = content.lower()
        first_match = min(
            (lowered.find(term) for term in matched_terms if lowered.find(term) >= 0),
            default=0,
        )
        start = max(first_match - 80, 0)
        return content[start : start + 260]


search_service = SearchService()

