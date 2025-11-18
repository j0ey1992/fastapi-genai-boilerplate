"""Audit logging models for compliance and governance."""

from typing import Optional

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class QueryLog(Base):
    """Model for logging all RAG queries and responses for CQC audit compliance."""

    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_role: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # support_worker, team_leader, manager, ops
    service_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )  # Service/location identifier
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunks: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # [{"policy_id": 1, "chunk_id": 5, "score": 0.89}]
    confidence: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # high, medium, low
    helpful_feedback: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True
    )  # User feedback: was this helpful?

    def __repr__(self) -> str:
        return f"<QueryLog(id={self.id}, user_id={self.user_id!r}, user_role={self.user_role!r}, created_at={self.created_at})>"
