"""Audit logging service for query compliance and governance."""

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import QueryLog


class AuditLoggingService:
    """Service for logging all RAG queries for CQC compliance."""

    def __init__(self, db_session: AsyncSession) -> None:
        """
        Initialize audit logging service.

        Args:
            db_session: Database session for logging
        """
        self.db = db_session

    async def log_query(
        self,
        user_id: str,
        user_role: str,
        question: str,
        answer: str,
        retrieved_chunks: list[dict[str, Any]],
        service_id: str | None = None,
        confidence: str | None = None,
    ) -> QueryLog:
        """
        Log a query and its response for audit purposes.

        Args:
            user_id: ID of the user who asked the question
            user_role: Role of the user (support_worker, team_leader, manager, ops)
            question: The question asked
            answer: The generated answer
            retrieved_chunks: List of chunk metadata retrieved
            service_id: Optional service/location identifier
            confidence: Answer confidence level

        Returns:
            Created QueryLog object
        """
        try:
            # Format retrieved chunks for storage
            chunks_data = {
                "chunks": [
                    {
                        "policy_id": chunk.get("policy_id"),
                        "policy_name": chunk.get("policy"),
                        "section": chunk.get("section"),
                        "relevance_score": chunk.get("relevance_score"),
                    }
                    for chunk in retrieved_chunks
                ],
                "total_retrieved": len(retrieved_chunks),
            }

            # Create log entry
            query_log = QueryLog(
                user_id=user_id,
                user_role=user_role,
                service_id=service_id,
                question=question,
                answer=answer,
                retrieved_chunks=chunks_data,
                confidence=confidence,
                helpful_feedback=None,  # Can be updated later
            )

            self.db.add(query_log)
            await self.db.commit()
            await self.db.refresh(query_log)

            logger.info(
                f"Logged query: user={user_id}, role={user_role}, "
                f"chunks={len(retrieved_chunks)}, log_id={query_log.id}"
            )

            return query_log

        except Exception as e:
            logger.error(f"Failed to log query: {e}")
            await self.db.rollback()
            raise

    async def get_user_logs(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[QueryLog]:
        """
        Retrieve query logs for a specific user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            List of QueryLog objects
        """
        query = (
            select(QueryLog)
            .where(QueryLog.user_id == user_id)
            .order_by(QueryLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        logger.debug(f"Retrieved {len(logs)} logs for user {user_id}")

        return logs

    async def get_service_logs(
        self,
        service_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[QueryLog]:
        """
        Retrieve query logs for a specific service/location.

        Args:
            service_id: Service ID to filter by
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            List of QueryLog objects
        """
        query = (
            select(QueryLog)
            .where(QueryLog.service_id == service_id)
            .order_by(QueryLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        logger.debug(f"Retrieved {len(logs)} logs for service {service_id}")

        return logs

    async def get_high_risk_queries(
        self,
        keywords: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QueryLog]:
        """
        Retrieve queries containing high-risk keywords.

        Args:
            keywords: List of keywords to search for (default: safety-related)
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            List of QueryLog objects
        """
        if keywords is None:
            # Default high-risk keywords
            keywords = [
                "fall",
                "injury",
                "head",
                "safeguarding",
                "abuse",
                "emergency",
                "999",
                "ambulance",
                "hospital",
                "restraint",
                "medication error",
                "overdose",
            ]

        # Build query with OR condition for any keyword
        query = select(QueryLog).order_by(QueryLog.created_at.desc())

        # Filter by keywords in question or answer
        conditions = []
        for keyword in keywords:
            conditions.append(QueryLog.question.ilike(f"%{keyword}%"))
            conditions.append(QueryLog.answer.ilike(f"%{keyword}%"))

        if conditions:
            from sqlalchemy import or_

            query = query.where(or_(*conditions))

        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        logger.info(f"Retrieved {len(logs)} high-risk queries")

        return logs

    async def update_feedback(
        self,
        log_id: int,
        helpful: bool,
    ) -> QueryLog:
        """
        Update user feedback for a query.

        Args:
            log_id: Query log ID
            helpful: Whether the answer was helpful

        Returns:
            Updated QueryLog object
        """
        log = await self.db.get(QueryLog, log_id)

        if not log:
            raise ValueError(f"Query log ID={log_id} not found")

        log.helpful_feedback = helpful

        await self.db.commit()
        await self.db.refresh(log)

        logger.info(f"Updated feedback for log {log_id}: helpful={helpful}")

        return log

    async def get_logs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[QueryLog]:
        """
        Retrieve query logs within a date range.

        Args:
            start_date: Start datetime (inclusive)
            end_date: End datetime (inclusive)
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            List of QueryLog objects
        """
        query = (
            select(QueryLog)
            .where(QueryLog.created_at >= start_date)
            .where(QueryLog.created_at <= end_date)
            .order_by(QueryLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        logger.info(
            f"Retrieved {len(logs)} logs between {start_date} and {end_date}"
        )

        return logs
