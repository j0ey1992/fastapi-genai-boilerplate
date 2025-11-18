"""Policy ingestion orchestration service."""

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy, PolicyChunk
from app.services.ingestion.pdf_parser import (
    chunk_text,
    clean_text,
    detect_sections,
    extract_text_from_pdf,
)
from app.services.llm.gemini_service import GeminiService
from app.services.vector.qdrant_service import QdrantService


class PolicyIngestionService:
    """Orchestrates policy ingestion from PDF to vector database."""

    def __init__(
        self,
        gemini_service: GeminiService,
        qdrant_service: QdrantService,
        db_session: AsyncSession,
    ) -> None:
        """
        Initialize policy ingestion service.

        Args:
            gemini_service: Gemini service for embeddings
            qdrant_service: Qdrant service for vector storage
            db_session: SQLAlchemy async session for PostgreSQL
        """
        self.gemini = gemini_service
        self.qdrant = qdrant_service
        self.db = db_session

    async def ingest_policy(
        self,
        pdf_source: str | Path | BytesIO,
        policy_name: str,
        version: str,
        effective_from: date,
        uploaded_by: str | None = None,
        effective_to: date | None = None,
        tags: dict[str, Any] | None = None,
        file_path: str | None = None,
    ) -> tuple[Policy, int]:
        """
        Ingest policy from PDF into the system.

        Pipeline:
            1. Extract text from PDF
            2. Clean and detect sections
            3. Chunk text with metadata
            4. Generate embeddings (Gemini)
            5. Store embeddings in Qdrant
            6. Store policy metadata in PostgreSQL

        Args:
            pdf_source: Path to PDF file or BytesIO object
            policy_name: Human-readable policy name
            version: Policy version (e.g., "v5", "2024.1")
            effective_from: Date policy becomes effective
            uploaded_by: User who uploaded the policy
            effective_to: Optional end date for policy
            tags: Optional tags {"topic": ["falls"], "roles": ["support_worker"]}
            file_path: Optional storage path for the PDF

        Returns:
            Tuple of (Policy object, number of chunks created)
        """
        logger.info(
            f"Starting policy ingestion: {policy_name} {version} "
            f"(effective: {effective_from})"
        )

        try:
            # Step 1: Extract text from PDF
            logger.info("Step 1/6: Extracting text from PDF...")
            pdf_data = extract_text_from_pdf(pdf_source)
            full_text = pdf_data["full_text"]
            total_pages = pdf_data["total_pages"]

            if not full_text.strip():
                raise ValueError("PDF contains no extractable text")

            # Step 2: Clean text
            logger.info("Step 2/6: Cleaning text...")
            cleaned_text = clean_text(full_text)

            # Step 3: Detect sections
            logger.info("Step 3/6: Detecting sections...")
            sections = detect_sections(cleaned_text)

            # Step 4: Chunk text
            logger.info("Step 4/6: Chunking text...")
            chunks = chunk_text(
                text=cleaned_text,
                sections=sections,
                chunk_size=800,  # ~200 tokens
                overlap=100,  # ~25 tokens overlap
            )

            if not chunks:
                raise ValueError("No chunks generated from PDF")

            logger.info(f"Generated {len(chunks)} chunks")

            # Step 5: Generate embeddings
            logger.info("Step 5/6: Generating embeddings with Gemini...")
            chunk_texts = [chunk[0] for chunk in chunks]
            embeddings = await self.gemini.generate_embeddings_batch(
                texts=chunk_texts, batch_size=100
            )

            if len(embeddings) != len(chunks):
                raise ValueError(
                    f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)} chunks"
                )

            # Step 6a: Create policy record in PostgreSQL
            logger.info("Step 6a/6: Storing policy metadata in PostgreSQL...")
            policy = Policy(
                name=policy_name,
                version=version,
                file_path=file_path or f"policies/{policy_name}_{version}.pdf",
                uploaded_by=uploaded_by,
                effective_from=effective_from,
                effective_to=effective_to,
                status="active",
                tags=tags or {},
            )

            self.db.add(policy)
            await self.db.flush()  # Get policy.id without committing

            logger.info(f"Created policy record: ID={policy.id}")

            # Step 6b: Store embeddings in Qdrant
            logger.info("Step 6b/6: Storing embeddings in Qdrant...")
            chunk_indices = [chunk[1].chunk_index for chunk in chunks]
            section_names = [chunk[1].section_name for chunk in chunks]
            metadatas = [
                {
                    "word_count": chunk[1].word_count,
                    "char_count": chunk[1].char_count,
                    "policy_name": policy_name,
                    "policy_version": version,
                }
                for chunk in chunks
            ]

            embedding_ids = await self.qdrant.upsert_vectors(
                embeddings=embeddings,
                policy_id=policy.id,
                chunk_texts=chunk_texts,
                chunk_indices=chunk_indices,
                section_names=section_names,
                metadatas=metadatas,
            )

            # Step 6c: Create PolicyChunk records in PostgreSQL
            logger.info("Step 6c/6: Creating PolicyChunk records...")
            for i, (chunk_text, chunk_metadata) in enumerate(chunks):
                policy_chunk = PolicyChunk(
                    policy_id=policy.id,
                    chunk_text=chunk_text,
                    chunk_index=chunk_metadata.chunk_index,
                    section_name=chunk_metadata.section_name,
                    embedding_id=embedding_ids[i],
                    metadata={
                        "word_count": chunk_metadata.word_count,
                        "char_count": chunk_metadata.char_count,
                        "page_number": chunk_metadata.page_number,
                    },
                )
                self.db.add(policy_chunk)

            # Commit all database changes
            await self.db.commit()
            await self.db.refresh(policy)

            logger.info(
                f"✅ Policy ingestion complete: {policy_name} {version} "
                f"({len(chunks)} chunks, {total_pages} pages, ID={policy.id})"
            )

            return policy, len(chunks)

        except Exception as e:
            logger.error(f"Policy ingestion failed: {e}")
            await self.db.rollback()
            raise

    async def update_policy(
        self,
        old_policy_id: int,
        pdf_source: str | Path | BytesIO,
        new_version: str,
        effective_from: date,
        uploaded_by: str | None = None,
        effective_to: date | None = None,
        tags: dict[str, Any] | None = None,
        file_path: str | None = None,
    ) -> tuple[Policy, int]:
        """
        Update existing policy with new version.

        Steps:
            1. Mark old policy as inactive
            2. Delete old embeddings from Qdrant
            3. Ingest new version

        Args:
            old_policy_id: ID of policy to replace
            pdf_source: New PDF file
            new_version: New version string
            effective_from: Effective date for new version
            uploaded_by: User who uploaded update
            effective_to: Optional end date
            tags: Optional tags
            file_path: Optional storage path

        Returns:
            Tuple of (new Policy object, number of chunks)
        """
        logger.info(f"Updating policy ID={old_policy_id} to version {new_version}")

        try:
            # Get old policy
            old_policy = await self.db.get(Policy, old_policy_id)
            if not old_policy:
                raise ValueError(f"Policy ID={old_policy_id} not found")

            # Mark old policy as inactive
            old_policy.status = "inactive"
            old_policy.effective_to = effective_from  # End date = new policy start date

            # Delete old embeddings from Qdrant
            logger.info(f"Deleting old embeddings for policy ID={old_policy_id}")
            await self.qdrant.delete_policy(old_policy_id)

            # Ingest new version
            new_policy, chunk_count = await self.ingest_policy(
                pdf_source=pdf_source,
                policy_name=old_policy.name,
                version=new_version,
                effective_from=effective_from,
                uploaded_by=uploaded_by,
                effective_to=effective_to,
                tags=tags or old_policy.tags,
                file_path=file_path,
            )

            logger.info(
                f"✅ Policy updated: {old_policy.name} "
                f"({old_policy.version} → {new_version})"
            )

            return new_policy, chunk_count

        except Exception as e:
            logger.error(f"Policy update failed: {e}")
            await self.db.rollback()
            raise

    async def delete_policy(self, policy_id: int) -> None:
        """
        Soft delete policy (mark as archived).

        Args:
            policy_id: Policy ID to delete
        """
        logger.info(f"Deleting policy ID={policy_id}")

        try:
            # Get policy
            policy = await self.db.get(Policy, policy_id)
            if not policy:
                raise ValueError(f"Policy ID={policy_id} not found")

            # Mark as archived
            policy.status = "archived"

            # Delete embeddings from Qdrant
            await self.qdrant.delete_policy(policy_id)

            await self.db.commit()

            logger.info(f"✅ Policy archived: {policy.name} {policy.version}")

        except Exception as e:
            logger.error(f"Policy deletion failed: {e}")
            await self.db.rollback()
            raise
