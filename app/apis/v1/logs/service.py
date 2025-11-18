"""Service layer for audit logs operations."""

from datetime import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.v1.logs.models import QueryLogItem
from app.services.audit.logging_service import AuditLoggingService


async def get_logs_service(
    db_session: AsyncSession,
    user_id: str | None = None,
    service_id: str | None = None,
    user_role: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    high_risk_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[QueryLogItem], int]:
    """
    Retrieve audit logs with optional filters.

    Args:
        db_session: Database session
        user_id: Filter by user ID
        service_id: Filter by service ID
        user_role: Filter by user role
        start_date: Filter by start date
        end_date: Filter by end date
        high_risk_only: Only return high-risk queries
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (log list, total count)
    """
    audit_service = AuditLoggingService(db_session=db_session)

    # Determine which method to call based on filters
    if high_risk_only:
        logs = await audit_service.get_high_risk_queries(
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    elif user_id:
        logs = await audit_service.get_user_logs(
            user_id=user_id,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    elif service_id:
        logs = await audit_service.get_service_logs(
            service_id=service_id,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    elif start_date and end_date:
        logs = await audit_service.get_logs_by_date_range(
            start_date=start_date,
            end_date=end_date,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    else:
        # Get all recent logs (limited)
        from sqlalchemy import select
        from app.models.audit import QueryLog

        query = select(QueryLog).order_by(QueryLog.created_at.desc())

        if user_role:
            query = query.where(QueryLog.user_role == user_role)

        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db_session.execute(query)
        logs = list(result.scalars().all())

    # Convert to response models
    log_items: list[QueryLogItem] = []
    for log in logs:
        log_items.append(
            QueryLogItem(
                id=log.id,
                user_id=log.user_id,
                user_role=log.user_role,
                service_id=log.service_id,
                question=log.question,
                answer=log.answer,
                retrieved_chunks=log.retrieved_chunks,
                confidence=log.confidence,
                helpful_feedback=log.helpful_feedback,
                created_at=log.created_at.isoformat(),
            )
        )

    # For simplicity, return len(logs) as total (in production, would do separate count query)
    total = len(logs)

    logger.info(f"Retrieved {len(log_items)} audit logs")

    return log_items, total


async def update_feedback_service(
    db_session: AsyncSession,
    log_id: int,
    helpful: bool,
) -> QueryLogItem:
    """
    Update feedback for a query log.

    Args:
        db_session: Database session
        log_id: Query log ID
        helpful: Whether the answer was helpful

    Returns:
        Updated QueryLogItem
    """
    audit_service = AuditLoggingService(db_session=db_session)

    log = await audit_service.update_feedback(
        log_id=log_id,
        helpful=helpful,
    )

    logger.info(f"Updated feedback for log {log_id}: helpful={helpful}")

    return QueryLogItem(
        id=log.id,
        user_id=log.user_id,
        user_role=log.user_role,
        service_id=log.service_id,
        question=log.question,
        answer=log.answer,
        retrieved_chunks=log.retrieved_chunks,
        confidence=log.confidence,
        helpful_feedback=log.helpful_feedback,
        created_at=log.created_at.isoformat(),
    )
