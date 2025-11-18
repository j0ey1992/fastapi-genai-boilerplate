"""Policy management API endpoints."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.v1.policy.models import (
    PolicyDeleteResponse,
    PolicyListResponse,
    PolicyUploadResponse,
)
from app.apis.v1.policy.service import (
    delete_policy_service,
    list_policies_service,
    upload_policy_service,
)
from app.core.responses.json_response import AppJSONResponse
from app.services.llm.gemini_service import get_gemini_service
from app.services.vector.qdrant_service import get_qdrant_service

router = APIRouter()


# Dependency for database session (will be implemented with lifespan)
async def get_db_session() -> AsyncSession:
    """Get database session - placeholder for now."""
    # TODO: Implement proper database session management in lifespan
    raise NotImplementedError("Database session management not yet configured")


@router.post(
    "/upload",
    response_model=PolicyUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload policy PDF",
    description="Upload and process a Voyage Care policy PDF document",
)
async def upload_policy(
    file: UploadFile = File(..., description="PDF file to upload"),
    policy_name: str = Form(..., description="Name of the policy"),
    version: str = Form(..., description="Policy version (e.g., 'v5', '2024.1')"),
    effective_from: date = Form(
        ..., description="Date when policy becomes effective"
    ),
    effective_to: date | None = Form(
        None, description="Optional end date for policy"
    ),
    uploaded_by: str | None = Form(None, description="User who uploaded the policy"),
    tags: str | None = Form(
        None,
        description='Optional JSON tags (e.g., {"topic": ["falls"], "roles": ["support_worker"]})',
    ),
    db: AsyncSession = Depends(get_db_session),
) -> AppJSONResponse:
    """
    Upload and ingest a policy PDF.

    Pipeline:
    1. Validate PDF file
    2. Extract text and detect sections
    3. Chunk text for embedding
    4. Generate embeddings with Gemini
    5. Store in Qdrant vector database
    6. Store metadata in PostgreSQL

    Rate limit: 2 requests per 60 seconds (large file processing)
    """
    try:
        # Parse tags if provided
        tags_dict: dict[str, Any] | None = None
        if tags:
            import json

            try:
                tags_dict = json.loads(tags)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format for tags",
                )

        # Get services
        gemini_service = get_gemini_service()
        qdrant_service = await get_qdrant_service()

        # Upload policy
        policy, chunk_count = await upload_policy_service(
            file=file,
            policy_name=policy_name,
            version=version,
            effective_from=effective_from,
            db_session=db,
            gemini_service=gemini_service,
            qdrant_service=qdrant_service,
            uploaded_by=uploaded_by,
            effective_to=effective_to,
            tags=tags_dict,
        )

        return AppJSONResponse(
            content=PolicyUploadResponse(
                policy_id=policy.id,
                policy_name=policy.name,
                version=policy.version,
                chunks_created=chunk_count,
                status="success",
                message=f"Policy '{policy.name}' v{policy.version} uploaded successfully",
            ).model_dump()
        )

    except ValueError as e:
        logger.warning(f"Policy upload validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Policy upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload policy. Please try again or contact support.",
        )


@router.get(
    "/list",
    response_model=PolicyListResponse,
    summary="List policies",
    description="Get paginated list of policies with optional status filter",
)
async def list_policies(
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> AppJSONResponse:
    """
    List policies with pagination.

    Query parameters:
    - page: Page number (1-indexed)
    - page_size: Items per page (max 100)
    - status_filter: Filter by status (active, inactive, archived)
    """
    try:
        # Validate page size
        if page_size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="page_size cannot exceed 100",
            )

        policies, total = await list_policies_service(
            db_session=db,
            page=page,
            page_size=page_size,
            status=status_filter,
        )

        return AppJSONResponse(
            content=PolicyListResponse(
                policies=policies,
                total=total,
                page=page,
                page_size=page_size,
            ).model_dump()
        )

    except Exception as e:
        logger.error(f"Failed to list policies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve policies",
        )


@router.delete(
    "/{policy_id}",
    response_model=PolicyDeleteResponse,
    summary="Delete policy",
    description="Archive a policy and remove from vector database",
)
async def delete_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> AppJSONResponse:
    """
    Delete (archive) a policy.

    This soft-deletes the policy by marking it as 'archived'
    and removes its embeddings from Qdrant.
    """
    try:
        qdrant_service = await get_qdrant_service()

        policy = await delete_policy_service(
            policy_id=policy_id,
            db_session=db,
            qdrant_service=qdrant_service,
        )

        return AppJSONResponse(
            content=PolicyDeleteResponse(
                policy_id=policy.id,
                status="archived",
                message=f"Policy '{policy.name}' v{policy.version} archived successfully",
            ).model_dump()
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to delete policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete policy",
        )
