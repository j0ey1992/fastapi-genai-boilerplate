"""RAG chat service for policy-based question answering."""

from pathlib import Path
from typing import Any, AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit.logging_service import AuditLoggingService
from app.services.llm.gemini_service import GeminiService
from app.services.rag.retrieval_service import RAGRetrievalService
from app.services.vector.qdrant_service import QdrantService


class RAGChatService:
    """Service for RAG-based policy question answering."""

    def __init__(
        self,
        gemini_service: GeminiService,
        qdrant_service: QdrantService,
        db_session: AsyncSession,
        enable_audit_logging: bool = True,
    ) -> None:
        """
        Initialize RAG chat service.

        Args:
            gemini_service: Gemini service for LLM
            qdrant_service: Qdrant service for retrieval
            db_session: Database session
            enable_audit_logging: Whether to log queries for compliance
        """
        self.gemini = gemini_service
        self.retrieval = RAGRetrievalService(
            gemini_service=gemini_service,
            qdrant_service=qdrant_service,
            db_session=db_session,
        )
        self.enable_audit_logging = enable_audit_logging

        # Initialize audit logging if enabled
        if enable_audit_logging:
            self.audit_logger = AuditLoggingService(db_session=db_session)
        else:
            self.audit_logger = None

        # Load prompt templates
        self.system_prompt_template = self._load_prompt("rag_system_prompt.txt")
        self.user_prompt_template = self._load_prompt("rag_user_prompt.txt")

    def _load_prompt(self, filename: str) -> str:
        """Load prompt template from file."""
        prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / filename
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {filename}, using fallback")
            return ""

    async def answer_question(
        self,
        question: str,
        user_id: str | None = None,
        user_role: str | None = None,
        service_id: str | None = None,
        top_k: int = 5,
        score_threshold: float = 0.7,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """
        Answer a policy question using RAG.

        Args:
            question: User's question
            user_id: User ID for audit logging
            user_role: User role for audit logging
            service_id: Service ID for audit logging
            top_k: Number of chunks to retrieve
            score_threshold: Minimum relevance score
            temperature: LLM sampling temperature

        Returns:
            Dictionary with answer, sources, and confidence
        """
        logger.info(f"Answering question: {question[:100]}...")

        try:
            # Step 1: Retrieve relevant chunks
            chunks = await self.retrieval.retrieve_relevant_chunks(
                question=question,
                top_k=top_k,
                score_threshold=score_threshold,
                active_only=True,
            )

            # Step 2: Check if we have relevant chunks
            if not chunks:
                result = {
                    "answer": (
                        "I cannot find this in our current policies. "
                        "Please escalate to your manager or on-call coordinator for guidance."
                    ),
                    "sources": [],
                    "confidence": "none",
                    "chunks_retrieved": 0,
                }

                # Log query with no results
                await self._log_query(
                    question=question,
                    answer=result["answer"],
                    sources=result["sources"],
                    confidence=result["confidence"],
                    user_id=user_id,
                    user_role=user_role,
                    service_id=service_id,
                )

                return result

            # Step 3: Format context
            context = self.retrieval.format_context(chunks)

            # Step 4: Build prompts
            system_prompt = self.system_prompt_template.format(context=context)
            user_prompt = self.user_prompt_template.format(question=question)

            # Step 5: Generate answer
            answer = await self.gemini.generate_chat_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=2048,
            )

            # Step 6: Calculate confidence
            confidence = self.retrieval.calculate_confidence(chunks)

            # Step 7: Format sources
            sources = self.retrieval.format_sources(chunks)

            logger.info(
                f"Answer generated (confidence: {confidence}, "
                f"sources: {len(sources)}, chunks: {len(chunks)})"
            )

            result = {
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
                "chunks_retrieved": len(chunks),
            }

            # Step 8: Log query for audit (async, non-blocking)
            await self._log_query(
                question=question,
                answer=answer,
                sources=sources,
                confidence=confidence,
                user_id=user_id,
                user_role=user_role,
                service_id=service_id,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to answer question: {e}")
            # Return safe fallback
            result = {
                "answer": (
                    "I encountered an error processing your question. "
                    "Please contact your manager or on-call coordinator for assistance."
                ),
                "sources": [],
                "confidence": "error",
                "chunks_retrieved": 0,
            }

            # Log error
            await self._log_query(
                question=question,
                answer=result["answer"],
                sources=result["sources"],
                confidence=result["confidence"],
                user_id=user_id,
                user_role=user_role,
                service_id=service_id,
            )

            return result

    async def answer_question_stream(
        self,
        question: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        """
        Answer a policy question using RAG with streaming response.

        Args:
            question: User's question
            top_k: Number of chunks to retrieve
            score_threshold: Minimum relevance score
            temperature: LLM sampling temperature

        Yields:
            Answer text chunks
        """
        logger.info(f"Answering question (stream): {question[:100]}...")

        try:
            # Step 1: Retrieve relevant chunks
            chunks = await self.retrieval.retrieve_relevant_chunks(
                question=question,
                top_k=top_k,
                score_threshold=score_threshold,
                active_only=True,
            )

            # Step 2: Check if we have relevant chunks
            if not chunks:
                yield (
                    "I cannot find this in our current policies. "
                    "Please escalate to your manager or on-call coordinator for guidance."
                )
                return

            # Step 3: Format context
            context = self.retrieval.format_context(chunks)

            # Step 4: Build prompts
            system_prompt = self.system_prompt_template.format(context=context)
            user_prompt = self.user_prompt_template.format(question=question)

            # Step 5: Generate answer (streaming)
            async for chunk in self.gemini.generate_chat_response_stream(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=2048,
            ):
                yield chunk

            # Step 6: Send sources metadata as final chunk (JSON format)
            sources = self.retrieval.format_sources(chunks)
            confidence = self.retrieval.calculate_confidence(chunks)

            sources_json = f'\n\n__SOURCES__:{{"sources":{sources},"confidence":"{confidence}"}}'
            yield sources_json

            logger.info(
                f"Streaming answer complete (confidence: {confidence}, sources: {len(sources)})"
            )

        except Exception as e:
            logger.error(f"Failed to stream answer: {e}")
            yield (
                "I encountered an error processing your question. "
                "Please contact your manager or on-call coordinator for assistance."
            )

    async def _log_query(
        self,
        question: str,
        answer: str,
        sources: list[dict[str, Any]],
        confidence: str,
        user_id: str | None,
        user_role: str | None,
        service_id: str | None,
    ) -> None:
        """
        Log query to audit database if enabled.

        Args:
            question: User's question
            answer: Generated answer
            sources: Source citations
            confidence: Confidence level
            user_id: User ID
            user_role: User role
            service_id: Service ID
        """
        if not self.enable_audit_logging or not self.audit_logger:
            return

        if not user_id or not user_role:
            logger.warning("Audit logging enabled but user_id or user_role not provided")
            return

        try:
            await self.audit_logger.log_query(
                user_id=user_id,
                user_role=user_role,
                question=question,
                answer=answer,
                retrieved_chunks=sources,
                service_id=service_id,
                confidence=confidence,
            )
        except Exception as e:
            # Don't fail the request if logging fails
            logger.error(f"Failed to log query for audit: {e}")
