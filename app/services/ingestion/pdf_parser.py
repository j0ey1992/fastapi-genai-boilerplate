"""PDF parsing and text extraction for policy documents."""

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pdfplumber
from loguru import logger


@dataclass
class ChunkMetadata:
    """Metadata for a text chunk."""

    section_name: str | None
    page_number: int
    chunk_index: int
    word_count: int
    char_count: int


def extract_text_from_pdf(pdf_path: str | Path | BytesIO) -> dict[str, Any]:
    """
    Extract text and metadata from PDF file.

    Args:
        pdf_path: Path to PDF file or BytesIO object

    Returns:
        Dictionary containing:
            - full_text: Complete extracted text
            - pages: List of page texts
            - metadata: PDF metadata (title, author, etc.)
            - total_pages: Number of pages
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages: list[str] = []
            full_text_parts: list[str] = []

            # Extract text from each page
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                pages.append(page_text)
                full_text_parts.append(page_text)

                logger.debug(f"Extracted page {page_num}: {len(page_text)} chars")

            full_text = "\n\n".join(full_text_parts)

            # Extract PDF metadata
            metadata = pdf.metadata or {}

            result = {
                "full_text": full_text,
                "pages": pages,
                "metadata": metadata,
                "total_pages": len(pages),
            }

            logger.info(
                f"Extracted {len(full_text)} chars from {len(pages)} pages "
                f"(PDF: {Path(pdf_path).name if isinstance(pdf_path, (str, Path)) else 'upload'})"
            )

            return result

    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise


def clean_text(text: str) -> str:
    """
    Clean extracted PDF text.

    Removes:
        - Headers and footers patterns
        - Page numbers
        - Excessive whitespace
        - Special characters

    Args:
        text: Raw PDF text

    Returns:
        Cleaned text
    """
    # Remove common header/footer patterns
    # Example: "Voyage Care | Safeguarding Policy | Page 5"
    text = re.sub(
        r"^.*?\|.*?\|.*?Page\s+\d+.*?$",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # Remove standalone page numbers
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # Remove "Page X of Y" patterns
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", "", text, flags=re.IGNORECASE)

    # Normalize whitespace (keep single newlines, remove excessive spaces)
    text = re.sub(r" +", " ", text)  # Multiple spaces → single space
    text = re.sub(r"\n{3,}", "\n\n", text)  # Multiple newlines → double newline

    # Remove leading/trailing whitespace
    text = text.strip()

    logger.debug(f"Cleaned text: {len(text)} chars")
    return text


def detect_sections(text: str) -> list[tuple[str, int, int]]:
    """
    Detect sections in policy document.

    Looks for patterns like:
        - "1. Introduction"
        - "1.1 Purpose"
        - "Section 1: Overview"
        - "## Heading"

    Args:
        text: Cleaned policy text

    Returns:
        List of (section_name, start_pos, end_pos) tuples
    """
    sections: list[tuple[str, int, int]] = []

    # Patterns for section headings
    patterns = [
        # Numbered sections: "1.", "1.1", "1.1.1"
        r"^(\d+(?:\.\d+)*\.?\s+[A-Z][^\n]{0,100})$",
        # "Section X: Title"
        r"^(Section\s+\d+:\s+[A-Z][^\n]{0,100})$",
        # Markdown-style headers: "## Title"
        r"^(#{1,3}\s+[A-Z][^\n]{0,100})$",
        # ALL CAPS HEADINGS (at least 3 words)
        r"^([A-Z][A-Z\s]{10,100})$",
    ]

    combined_pattern = "|".join(patterns)

    for match in re.finditer(combined_pattern, text, flags=re.MULTILINE):
        section_name = match.group(0).strip()
        start_pos = match.start()

        # Clean section name
        section_name = re.sub(r"^#{1,3}\s+", "", section_name)  # Remove markdown ##
        section_name = section_name.strip()

        sections.append((section_name, start_pos, -1))  # End position set later

    # Set end positions (end of section = start of next section)
    for i in range(len(sections)):
        if i + 1 < len(sections):
            sections[i] = (sections[i][0], sections[i][1], sections[i + 1][1])
        else:
            sections[i] = (sections[i][0], sections[i][1], len(text))

    logger.info(f"Detected {len(sections)} sections in document")
    for name, start, end in sections[:5]:  # Log first 5 sections
        logger.debug(f"  Section: {name[:50]}... ({start}-{end})")

    return sections


def chunk_text(
    text: str,
    sections: list[tuple[str, int, int]] | None = None,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[tuple[str, ChunkMetadata]]:
    """
    Split text into overlapping chunks for embedding.

    Args:
        text: Clean policy text
        sections: Optional list of (section_name, start, end) tuples
        chunk_size: Target chunk size in characters (tokens ~= chars / 4)
        overlap: Overlap between chunks in characters

    Returns:
        List of (chunk_text, ChunkMetadata) tuples
    """
    chunks: list[tuple[str, ChunkMetadata]] = []

    # If no sections provided, treat entire text as one section
    if not sections:
        sections = [("Document", 0, len(text))]

    chunk_index = 0

    for section_name, section_start, section_end in sections:
        section_text = text[section_start:section_end].strip()

        if not section_text:
            continue

        # Split section into chunks with overlap
        position = 0
        while position < len(section_text):
            # Extract chunk
            chunk_end = min(position + chunk_size, len(section_text))
            chunk = section_text[position:chunk_end].strip()

            # If not at end and chunk ends mid-sentence, extend to sentence end
            if chunk_end < len(section_text):
                # Look for sentence boundary (., !, ?) within next 100 chars
                sentence_end_match = re.search(
                    r"[.!?]\s", section_text[chunk_end : chunk_end + 100]
                )
                if sentence_end_match:
                    chunk_end += sentence_end_match.end()
                    chunk = section_text[position:chunk_end].strip()

            # Skip very small chunks (less than 100 chars)
            if len(chunk) < 100:
                break

            # Create metadata
            metadata = ChunkMetadata(
                section_name=section_name,
                page_number=0,  # Can be enhanced if page tracking needed
                chunk_index=chunk_index,
                word_count=len(chunk.split()),
                char_count=len(chunk),
            )

            chunks.append((chunk, metadata))
            chunk_index += 1

            # Move position forward with overlap
            position += chunk_size - overlap

            # If we've reached the end, break
            if position >= len(section_text):
                break

    logger.info(
        f"Created {len(chunks)} chunks (avg size: {sum(len(c[0]) for c in chunks) // len(chunks) if chunks else 0} chars)"
    )

    return chunks
