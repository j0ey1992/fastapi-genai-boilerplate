"""RAG retrieval service for policy question answering."""

from dataclasses import dataclass
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy, PolicyChunk
from app.services.llm.gemini_service import GeminiService
from app.services.vector.qdrant_service import QdrantService


@dataclass
class RetrievedChunk:
    """Represents a retrieved policy chunk with metadata."""

    chunk_text: str
    policy_id: int
    policy_name: str
    policy_version: str
    section_name: str | None
    chunk_index: int
    relevance_score: float
    embedding_id: str


class RAGRetrievalService:
    """Service for retrieving relevant policy chunks for RAG."""

    def __init__(
        self,
        gemini_service: GeminiService,
        qdrant_service: QdrantService,
        db_session: AsyncSession,
    ) -> None:
        """
        Initialize RAG retrieval service.

        Args:
            gemini_service: Gemini service for embeddings
            qdrant_service: Qdrant service for vector search
            db_session: Database session for policy metadata
        """
        self.gemini = gemini_service
        self.qdrant = qdrant_service
        self.db = db_session

    async def retrieve_relevant_chunks(
        self,
        question: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
        active_only: bool = True,
    ) -> list[RetrievedChunk]:
        """
        Retrieve relevant policy chunks for a question.

        Args:
            question: User's question
            top_k: Number of chunks to retrieve
            score_threshold: Minimum similarity score (0-1)
            active_only: Only search active policies

        Returns:
            List of retrieved chunks with metadata
        """
        logger.info(f"Retrieving chunks for question: {question[:100]}...")

        try:
            # Step 1: Embed the question
            question_embedding = await self.gemini.generate_embedding(question)

            # Step 2: Get active policy IDs if filtering
            policy_ids: list[int] | None = None
            if active_only:
                query = select(Policy.id).where(Policy.status == "active")
                result = await self.db.execute(query)
                policy_ids = list(result.scalars().all())

                if not policy_ids:
                    logger.warning("No active policies found")
                    return []

            # Step 3: Search Qdrant for similar chunks
            search_results = await self.qdrant.search_similar(
                query_embedding=question_embedding,
                top_k=top_k,
                score_threshold=score_threshold,
                policy_ids=policy_ids,
            )

            if not search_results:
                logger.warning(
                    f"No relevant chunks found (threshold={score_threshold})"
                )
                return []

            # Step 4: Enrich results with policy metadata
            retrieved_chunks: list[RetrievedChunk] = []

            for result in search_results:
                # Get policy metadata
                policy_id = result["policy_id"]
                policy = await self.db.get(Policy, policy_id)

                if not policy:
                    logger.warning(f"Policy ID={policy_id} not found, skipping chunk")
                    continue

                retrieved_chunks.append(
                    RetrievedChunk(
                        chunk_text=result["chunk_text"],
                        policy_id=policy.id,
                        policy_name=policy.name,
                        policy_version=policy.version,
                        section_name=result.get("section_name"),
                        chunk_index=result["chunk_index"],
                        relevance_score=result["score"],
                        embedding_id=result["embedding_id"],
                    )
                )

            logger.info(
                f"Retrieved {len(retrieved_chunks)} chunks "
                f"(avg score: {sum(c.relevance_score for c in retrieved_chunks) / len(retrieved_chunks):.3f})"
            )

            return retrieved_chunks

        except Exception as e:
            logger.error(f"Failed to retrieve chunks: {e}")
            raise

    def format_context(self, chunks: list[RetrievedChunk]) -> str:
        """
        Format retrieved chunks into context for RAG prompt.

        Args:
            chunks: Retrieved chunks

        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant policy information found."

        context_parts = []

        for i, chunk in enumerate(chunks, start=1):
            section_info = (
                f" - {chunk.section_name}" if chunk.section_name else ""
            )

            context_parts.append(
                f"[Source {i}] {chunk.policy_name} (v{chunk.policy_version}){section_info}\n"
                f"{chunk.chunk_text}\n"
            )

        context = "\n---\n\n".join(context_parts)

        logger.debug(f"Formatted context: {len(context)} chars")

        return context

    def calculate_confidence(self, chunks: list[RetrievedChunk]) -> str:
        """
        Calculate confidence level based on retrieval scores.

        Args:
            chunks: Retrieved chunks

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        if not chunks:
            return "low"

        avg_score = sum(c.relevance_score for c in chunks) / len(chunks)
        max_score = max(c.relevance_score for c in chunks)

        # High confidence: top result > 0.85 and avg > 0.75
        if max_score > 0.85 and avg_score > 0.75:
            return "high"
        # Medium confidence: top result > 0.70 and avg > 0.65
        elif max_score > 0.70 and avg_score > 0.65:
            return "medium"
        # Low confidence: anything else
        else:
            return "low"

    def format_sources(self, chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
        """
        Format chunks into source citations for response.

        Args:
            chunks: Retrieved chunks

        Returns:
            List of source dictionaries
        """
        sources = []

        for chunk in chunks:
            sources.append(
                {
                    "policy": chunk.policy_name,
                    "version": chunk.policy_version,
                    "section": chunk.section_name or "General",
                    "relevance_score": round(chunk.relevance_score, 3),
                }
            )

        return sources
