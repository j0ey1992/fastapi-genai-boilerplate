"""Service layer for policy management operations."""

from datetime import date
from io import BytesIO
from typing import Any

from fastapi import UploadFile
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.v1.policy.models import PolicyListItem
from app.models.policy import Policy, PolicyChunk
from app.services.ingestion.policy_ingestion import PolicyIngestionService
from app.services.llm.gemini_service import GeminiService
from app.services.vector.qdrant_service import QdrantService


async def upload_policy_service(
    file: UploadFile,
    policy_name: str,
    version: str,
    effective_from: date,
    db_session: AsyncSession,
    gemini_service: GeminiService,
    qdrant_service: QdrantService,
    uploaded_by: str | None = None,
    effective_to: date | None = None,
    tags: dict[str, Any] | None = None,
) -> tuple[Policy, int]:
    """
    Handle policy upload and ingestion.

    Args:
        file: Uploaded PDF file
        policy_name: Name of the policy
        version: Policy version
        effective_from: Effective date
        db_session: Database session
        gemini_service: Gemini service instance
        qdrant_service: Qdrant service instance
        uploaded_by: User who uploaded
        effective_to: Optional end date
        tags: Optional metadata tags

    Returns:
        Tuple of (Policy object, chunk count)
    """
    logger.info(f"Uploading policy: {policy_name} v{version}")

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are supported")

    # Read file content
    content = await file.read()
    pdf_bytes = BytesIO(content)

    # Create ingestion service
    ingestion_service = PolicyIngestionService(
        gemini_service=gemini_service,
        qdrant_service=qdrant_service,
        db_session=db_session,
    )

    # Ingest policy
    policy, chunk_count = await ingestion_service.ingest_policy(
        pdf_source=pdf_bytes,
        policy_name=policy_name,
        version=version,
        effective_from=effective_from,
        uploaded_by=uploaded_by,
        effective_to=effective_to,
        tags=tags,
        file_path=f"uploads/{policy_name}_{version}.pdf",
    )

    logger.info(
        f"Policy uploaded successfully: ID={policy.id}, chunks={chunk_count}"
    )

    return policy, chunk_count


async def list_policies_service(
    db_session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> tuple[list[PolicyListItem], int]:
    """
    List policies with pagination.

    Args:
        db_session: Database session
        page: Page number (1-indexed)
        page_size: Items per page
        status: Optional status filter (active, inactive, archived)

    Returns:
        Tuple of (policy list, total count)
    """
    # Build query
    query = select(Policy)

    if status:
        query = query.where(Policy.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db_session.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    query = query.order_by(Policy.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db_session.execute(query)
    policies = result.scalars().all()

    # Get chunk counts for each policy
    policy_items: list[PolicyListItem] = []
    for policy in policies:
        # Count chunks
        chunk_count_query = select(func.count()).where(
            PolicyChunk.policy_id == policy.id
        )
        chunk_count_result = await db_session.execute(chunk_count_query)
        chunk_count = chunk_count_result.scalar_one()

        policy_items.append(
            PolicyListItem(
                id=policy.id,
                name=policy.name,
                version=policy.version,
                status=policy.status,
                effective_from=policy.effective_from,
                effective_to=policy.effective_to,
                uploaded_by=policy.uploaded_by,
                created_at=policy.created_at.isoformat(),
                chunk_count=chunk_count,
            )
        )

    return policy_items, total


async def delete_policy_service(
    policy_id: int,
    db_session: AsyncSession,
    qdrant_service: QdrantService,
) -> Policy:
    """
    Delete (archive) a policy.

    Args:
        policy_id: Policy ID to delete
        db_session: Database session
        qdrant_service: Qdrant service instance

    Returns:
        Deleted policy object
    """
    # Get policy
    policy = await db_session.get(Policy, policy_id)
    if not policy:
        raise ValueError(f"Policy ID={policy_id} not found")

    # Mark as archived
    policy.status = "archived"

    # Delete from Qdrant
    await qdrant_service.delete_policy(policy_id)

    await db_session.commit()
    await db_session.refresh(policy)

    logger.info(f"Policy archived: {policy.name} v{policy.version} (ID={policy.id})")

    return policy
