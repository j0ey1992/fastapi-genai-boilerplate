"""Policy and PolicyChunk database models."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Policy(Base):
    """Model for storing policy metadata."""

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", index=True
    )  # active, inactive, archived
    tags: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # {"topic": ["falls", "safeguarding"], "roles": ["support_worker"]}

    # Relationship to chunks
    chunks: Mapped[list["PolicyChunk"]] = relationship(
        "PolicyChunk", back_populates="policy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Policy(id={self.id}, name={self.name!r}, version={self.version!r}, status={self.status!r})>"


class PolicyChunk(Base):
    """Model for storing individual policy chunks with embeddings."""

    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Order within the policy
    section_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # e.g., "3.2 Reporting Procedures"
    embedding_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )  # UUID for Qdrant vector
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # {"page_number": 5, "word_count": 150}

    # Relationship to parent policy
    policy: Mapped["Policy"] = relationship("Policy", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<PolicyChunk(id={self.id}, policy_id={self.policy_id}, chunk_index={self.chunk_index}, section={self.section_name!r})>"
