"""Request and response models for policy endpoints."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class PolicyUploadResponse(BaseModel):
    """Response model for policy upload."""

    policy_id: int = Field(..., description="Database ID of created policy")
    policy_name: str = Field(..., description="Name of the policy")
    version: str = Field(..., description="Policy version")
    chunks_created: int = Field(..., description="Number of chunks created")
    status: str = Field(default="success", description="Upload status")
    message: str = Field(default="Policy uploaded successfully")


class PolicyListItem(BaseModel):
    """Single policy in list response."""

    id: int
    name: str
    version: str
    status: str
    effective_from: date
    effective_to: date | None
    uploaded_by: str | None
    created_at: str
    chunk_count: int


class PolicyListResponse(BaseModel):
    """Response model for listing policies."""

    policies: list[PolicyListItem]
    total: int
    page: int
    page_size: int


class PolicyDeleteResponse(BaseModel):
    """Response model for policy deletion."""

    policy_id: int
    status: str = Field(default="deleted")
    message: str = Field(default="Policy archived successfully")
