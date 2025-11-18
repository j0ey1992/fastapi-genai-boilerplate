"""Qdrant vector database service for policy embeddings."""

from typing import Any
from uuid import uuid4

from loguru import logger
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings


class QdrantService:
    """Service for managing policy embeddings in Qdrant vector database."""

    def __init__(self) -> None:
        """Initialize Qdrant client."""
        self.client: AsyncQdrantClient | None = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.embedding_dimension = settings.EMBEDDING_DIMENSION

    async def initialize(self) -> None:
        """Initialize async Qdrant client and create collection if needed."""
        try:
            # Initialize client
            if settings.QDRANT_API_KEY:
                self.client = AsyncQdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=30,
                )
            else:
                # For local Qdrant without API key
                self.client = AsyncQdrantClient(
                    url=settings.QDRANT_URL,
                    timeout=30,
                )

            # Check if collection exists, create if not
            collections = await self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                await self.create_collection()
                logger.info(
                    f"Qdrant collection '{self.collection_name}' created successfully"
                )
            else:
                logger.info(
                    f"Qdrant collection '{self.collection_name}' already exists"
                )

        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise

    async def create_collection(self) -> None:
        """Create Qdrant collection for policy embeddings."""
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")

        try:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.embedding_dimension,
                    distance=models.Distance.COSINE,
                ),
                # Optimize for high-precision retrieval
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=10000,
                ),
                # Enable payload indexing for filtering
                on_disk_payload=False,
            )
            logger.info(
                f"Created Qdrant collection: {self.collection_name} "
                f"(dimension: {self.embedding_dimension})"
            )
        except UnexpectedResponse as e:
            if "already exists" in str(e).lower():
                logger.warning(f"Collection {self.collection_name} already exists")
            else:
                raise

    async def upsert_vectors(
        self,
        embeddings: list[list[float]],
        policy_id: int,
        chunk_texts: list[str],
        chunk_indices: list[int],
        section_names: list[str | None],
        metadatas: list[dict[str, Any]],
    ) -> list[str]:
        """
        Insert or update policy chunk embeddings in Qdrant.

        Args:
            embeddings: List of embedding vectors
            policy_id: Database policy ID
            chunk_texts: List of chunk text content
            chunk_indices: List of chunk order indices
            section_names: List of section names (can contain None)
            metadatas: List of additional metadata dicts

        Returns:
            List of generated embedding IDs (UUIDs)
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")

        if not (
            len(embeddings)
            == len(chunk_texts)
            == len(chunk_indices)
            == len(section_names)
            == len(metadatas)
        ):
            raise ValueError("All input lists must have the same length")

        try:
            # Generate UUIDs for each chunk
            embedding_ids = [str(uuid4()) for _ in range(len(embeddings))]

            # Create points for Qdrant
            points = []
            for i, embedding_id in enumerate(embedding_ids):
                payload = {
                    "policy_id": policy_id,
                    "chunk_text": chunk_texts[i],
                    "chunk_index": chunk_indices[i],
                    "section_name": section_names[i],
                    "embedding_id": embedding_id,
                    **metadatas[i],  # Merge additional metadata
                }

                points.append(
                    models.PointStruct(
                        id=embedding_id,
                        vector=embeddings[i],
                        payload=payload,
                    )
                )

            # Upsert in batches of 100 for efficiency
            batch_size = 100
            for batch_start in range(0, len(points), batch_size):
                batch = points[batch_start : batch_start + batch_size]
                await self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                )

            logger.info(
                f"Upserted {len(points)} vectors for policy_id={policy_id} "
                f"to collection '{self.collection_name}'"
            )

            return embedding_ids

        except Exception as e:
            logger.error(f"Failed to upsert vectors: {e}")
            raise

    async def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        score_threshold: float = 0.7,
        policy_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar policy chunks by embedding.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            score_threshold: Minimum similarity score (0-1)
            policy_ids: Optional list of policy IDs to filter by

        Returns:
            List of matching chunks with metadata and scores
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")

        try:
            # Build filter if policy_ids provided
            query_filter = None
            if policy_ids:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="policy_id",
                            match=models.MatchAny(any=policy_ids),
                        )
                    ]
                )

            # Search
            results = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=True,
            )

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "embedding_id": result.id,
                        "score": result.score,
                        "policy_id": result.payload.get("policy_id"),  # type: ignore
                        "chunk_text": result.payload.get("chunk_text"),  # type: ignore
                        "chunk_index": result.payload.get("chunk_index"),  # type: ignore
                        "section_name": result.payload.get("section_name"),  # type: ignore
                        "metadata": {
                            k: v
                            for k, v in result.payload.items()  # type: ignore
                            if k
                            not in [
                                "policy_id",
                                "chunk_text",
                                "chunk_index",
                                "section_name",
                                "embedding_id",
                            ]
                        },
                    }
                )

            logger.info(
                f"Found {len(formatted_results)} similar chunks "
                f"(threshold={score_threshold}, top_k={top_k})"
            )

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search similar vectors: {e}")
            raise

    async def delete_policy(self, policy_id: int) -> int:
        """
        Delete all chunks for a specific policy.

        Args:
            policy_id: Database policy ID

        Returns:
            Number of vectors deleted
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")

        try:
            # Delete by filter
            result = await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="policy_id",
                                match=models.MatchValue(value=policy_id),
                            )
                        ]
                    )
                ),
            )

            logger.info(f"Deleted vectors for policy_id={policy_id}")
            return result.operation_id if result else 0

        except Exception as e:
            logger.error(f"Failed to delete policy vectors: {e}")
            raise

    async def close(self) -> None:
        """Close Qdrant client connection."""
        if self.client:
            await self.client.close()
            logger.info("Qdrant client closed")


# Global instance
_qdrant_service: QdrantService | None = None


async def get_qdrant_service() -> QdrantService:
    """Get or create singleton Qdrant service instance."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
        await _qdrant_service.initialize()
    return _qdrant_service
