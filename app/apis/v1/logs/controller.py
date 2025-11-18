"""Audit logs API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.v1.logs.models import (
    FeedbackRequest,
    FeedbackResponse,
    QueryLogsResponse,
)
from app.apis.v1.logs.service import get_logs_service, update_feedback_service
from app.core.responses.json_response import AppJSONResponse

router = APIRouter()


# Dependency for database session (will be implemented with lifespan)
async def get_db_session() -> AsyncSession:
    """Get database session - placeholder for now."""
    # TODO: Implement proper database session management in lifespan
    raise NotImplementedError("Database session management not yet configured")


@router.get(
    "",
    response_model=QueryLogsResponse,
    summary="Get audit logs",
    description="Retrieve query audit logs with optional filters (manager/ops only)",
)
async def get_logs(
    user_id: str | None = Query(None, description="Filter by user ID"),
    service_id: str | None = Query(None, description="Filter by service ID"),
    user_role: str | None = Query(None, description="Filter by user role"),
    start_date: datetime | None = Query(None, description="Filter by start date"),
    end_date: datetime | None = Query(None, description="Filter by end date"),
    high_risk_only: bool = Query(
        False, description="Only return high-risk queries (falls, injuries, etc.)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_db_session),
) -> AppJSONResponse:
    """
    Get audit logs.

    Filters:
    - user_id: Get logs for specific user
    - service_id: Get logs for specific service/location
    - user_role: Filter by role (support_worker, team_leader, manager, ops)
    - start_date & end_date: Date range filter
    - high_risk_only: Only queries containing keywords like "fall", "injury", "safeguarding"

    Access control:
    - TODO: Add role-based access control (manager/ops only)
    """
    try:
        logs, total = await get_logs_service(
            db_session=db,
            user_id=user_id,
            service_id=service_id,
            user_role=user_role,
            start_date=start_date,
            end_date=end_date,
            high_risk_only=high_risk_only,
            page=page,
            page_size=page_size,
        )

        return AppJSONResponse(
            content=QueryLogsResponse(
                logs=logs,
                total=total,
                page=page,
                page_size=page_size,
            ).model_dump()
        )

    except NotImplementedError:
        # Temporary response until DB is configured
        return AppJSONResponse(
            content={
                "logs": [],
                "total": 0,
                "page": 1,
                "page_size": 50,
            }
        )
    except Exception as e:
        logger.error(f"Failed to retrieve logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs",
        )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Update query feedback",
    description="Record whether a query answer was helpful",
)
async def update_feedback(
    request_params: FeedbackRequest,
    db: AsyncSession = Depends(get_db_session),
) -> AppJSONResponse:
    """
    Update user feedback for a query.

    This helps track answer quality and identify areas for improvement.
    """
    try:
        log = await update_feedback_service(
            db_session=db,
            log_id=request_params.log_id,
            helpful=request_params.helpful,
        )

        return AppJSONResponse(
            content=FeedbackResponse(
                log_id=log.id,
                helpful=request_params.helpful,
                message="Feedback recorded successfully",
            ).model_dump()
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except NotImplementedError:
        return AppJSONResponse(
            content={
                "log_id": request_params.log_id,
                "helpful": request_params.helpful,
                "message": "Database not yet configured",
            }
        )
    except Exception as e:
        logger.error(f"Failed to update feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feedback",
        )
