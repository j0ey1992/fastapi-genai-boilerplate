"""Request and response models for logs endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QueryLogItem(BaseModel):
    """Single query log entry."""

    id: int
    user_id: str
    user_role: str
    service_id: str | None
    question: str
    answer: str
    retrieved_chunks: dict[str, Any]
    confidence: str | None
    helpful_feedback: bool | None
    created_at: str


class QueryLogsResponse(BaseModel):
    """Response model for query logs list."""

    logs: list[QueryLogItem]
    total: int
    page: int
    page_size: int


class FeedbackRequest(BaseModel):
    """Request model for updating query feedback."""

    log_id: int = Field(..., description="Query log ID")
    helpful: bool = Field(..., description="Whether the answer was helpful")


class FeedbackResponse(BaseModel):
    """Response model for feedback update."""

    log_id: int
    helpful: bool
    message: str = Field(default="Feedback recorded successfully")
