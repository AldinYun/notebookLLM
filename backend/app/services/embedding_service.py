from app.domain.workspace import utc_now
from app.services.model_gateway import ModelGatewayError, model_gateway
from app.services.workspace_store import workspace_store


class EmbeddingService:
    batch_size = 32

    def get_connection(self, connection_id: str) -> dict:
        connection = workspace_store.get_model_connection(connection_id)
        if connection is None:
            raise ModelGatewayError("Embedding model connection not found")
        if "embedding" not in connection["capabilities"]:
            raise ModelGatewayError("Selected model connection does not support embeddings")
        return connection

    def embed_texts(
        self,
        connection_id: str,
        texts: list[str],
        api_key: str = "",
    ) -> list[list[float]]:
        connection = self.get_connection(connection_id)
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            embeddings.extend(
                model_gateway.embed(connection, texts[start : start + self.batch_size], api_key)
            )
        return embeddings

    def embed_document(self, document_id: str, connection_id: str, api_key: str = "") -> int:
        chunks = workspace_store.list_document_chunks(document_id)
        embeddings = self.embed_texts(
            connection_id=connection_id,
            texts=[chunk.content for chunk in chunks],
            api_key=api_key,
        )
        return workspace_store.update_chunk_embeddings(document_id, embeddings, utc_now())


embedding_service = EmbeddingService()
