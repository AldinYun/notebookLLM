from dataclasses import dataclass, field
from enum import StrEnum


class RetrieverType(StrEnum):
    TEXT = "text"
    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID = "hybrid"


class FusionStrategy(StrEnum):
    NORMALIZED_WEIGHTED_SUM = "normalized_weighted_sum"
    RRF = "rrf"


@dataclass(frozen=True)
class RetrieverConfig:
    retriever_type: RetrieverType
    top_k: int
    weight: float = 1.0
    min_score: float | None = None


@dataclass(frozen=True)
class RagProfile:
    profile_id: str
    name: str
    retrievers: list[RetrieverConfig]
    fusion_strategy: FusionStrategy = FusionStrategy.RRF
    self_corrective_enabled: bool = False
    final_context_limit: int = 10
    metadata_filters: dict[str, str] = field(default_factory=dict)

