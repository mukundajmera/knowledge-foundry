"""Knowledge Foundry — Semantic Chunking Engine.

Heading-aware recursive chunker per phase-1.2 spec §2.1.
Splits documents at semantic boundaries (headings, paragraphs)
then recursively splits oversized chunks at sentence boundaries.
"""

from __future__ import annotations

import hashlib
import re
import logging
from uuid import uuid4

from src.core.exceptions import ChunkingError
from src.core.interfaces import Chunk, Document

logger = logging.getLogger(__name__)

# Default chunking parameters per spec
DEFAULT_CHUNK_SIZE = 800  # tokens
DEFAULT_CHUNK_OVERLAP = 100  # tokens
MIN_CHUNK_SIZE = 50  # tokens — chunks below this are merged
MAX_CHUNKS_PER_DOCUMENT = 100  # safety limit

# Approximate token-to-char ratio for English text
CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _sha256(text: str) -> str:
    """Compute SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SemanticChunker:
    """Heading-aware recursive document chunker.

    Strategy:
    1. Split at heading boundaries (## in Markdown).
    2. For non-Markdown: split at paragraph boundaries (double newline).
    3. If any chunk exceeds ``chunk_size``, recursively split at sentences
       with ``chunk_overlap`` token overlap.
    4. Merge tiny chunks (<50 tokens) with adjacent chunks.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        min_chunk_size: int = MIN_CHUNK_SIZE,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self._chunk_size_chars = chunk_size * CHARS_PER_TOKEN
        self._overlap_chars = chunk_overlap * CHARS_PER_TOKEN
        self._min_chunk_chars = min_chunk_size * CHARS_PER_TOKEN

    def chunk_document(self, document: Document) -> list[Chunk]:
        """Split a document into chunks with metadata.

        Args:
            document: The Document to chunk.

        Returns:
            List of Chunk objects with text, metadata, and text_hash.

        Raises:
            ChunkingError: If chunking fails.
        """
        try:
            content = document.content.strip()
            if not content:
                raise ChunkingError(
                    "Document content is empty",
                    details={"document_id": str(document.document_id)},
                )

            # Step 1: Split at semantic boundaries
            raw_chunks = self._split_semantic(content)

            # Step 2: Handle oversized chunks
            sized_chunks: list[str] = []
            for chunk_text in raw_chunks:
                if _estimate_tokens(chunk_text) > self.chunk_size:
                    sub_chunks = self._split_recursive(chunk_text)
                    sized_chunks.extend(sub_chunks)
                else:
                    sized_chunks.append(chunk_text)

            # Step 3: Merge tiny chunks
            merged_chunks = self._merge_tiny(sized_chunks)

            # Step 4: Safety limit
            if len(merged_chunks) > MAX_CHUNKS_PER_DOCUMENT:
                logger.warning(
                    "Document %s produced %d chunks (limit %d), truncating",
                    document.document_id,
                    len(merged_chunks),
                    MAX_CHUNKS_PER_DOCUMENT,
                )
                merged_chunks = merged_chunks[:MAX_CHUNKS_PER_DOCUMENT]

            # Step 5: Build Chunk objects
            total_chunks = len(merged_chunks)
            result: list[Chunk] = []

            for i, text in enumerate(merged_chunks):
                chunk_id = str(uuid4())
                result.append(
                    Chunk(
                        chunk_id=chunk_id,
                        document_id=str(document.document_id),
                        tenant_id=str(document.tenant_id),
                        text=text,
                        text_hash=_sha256(text),
                        chunk_index=i,
                        total_chunks=total_chunks,
                        title=document.title,
                        source_system=document.source_system,
                        source_url=document.source_url,
                        content_type=document.content_type,
                        tags=document.tags,
                        visibility=document.visibility,
                        created_date=document.created_date,
                        updated_date=document.updated_date,
                    )
                )

            logger.info(
                "Chunked document %s into %d chunks",
                document.document_id,
                total_chunks,
            )
            return result

        except ChunkingError:
            raise
        except Exception as exc:
            raise ChunkingError(
                f"Chunking failed for document {document.document_id}: {exc}",
                details={"document_id": str(document.document_id)},
            ) from exc

    def _split_semantic(self, text: str) -> list[str]:
        """Split text at semantic boundaries.

        Priority: Markdown headings → double newlines → single newlines.
        """
        # Try markdown headings first
        heading_pattern = r"(?=^#{1,4}\s)"
        sections = re.split(heading_pattern, text, flags=re.MULTILINE)
        sections = [s.strip() for s in sections if s.strip()]

        if len(sections) > 1:
            return sections

        # Fall back to paragraph breaks
        paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if len(paragraphs) > 1:
            return paragraphs

        # Single block — return as-is (will be recursively split if too large)
        return [text]

    def _split_recursive(self, text: str) -> list[str]:
        """Recursively split oversized text at sentence boundaries with overlap."""
        if _estimate_tokens(text) <= self.chunk_size:
            return [text]

        # Split at sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= 1:
            # Can't split further — split at word boundaries
            return self._split_at_words(text)

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            if current_length + sentence_length > self._chunk_size_chars and current_chunk:
                # Save current chunk
                chunks.append(" ".join(current_chunk))

                # Start new chunk with overlap
                overlap_chars = 0
                overlap_sentences: list[str] = []
                for s in reversed(current_chunk):
                    overlap_chars += len(s)
                    if overlap_chars > self._overlap_chars:
                        break
                    overlap_sentences.insert(0, s)

                current_chunk = overlap_sentences
                current_length = sum(len(s) for s in current_chunk)

            current_chunk.append(sentence)
            current_length += sentence_length

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_at_words(self, text: str) -> list[str]:
        """Last-resort split at word boundaries."""
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []
        current_length = 0

        for word in words:
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length > self._chunk_size_chars and current:
                chunks.append(" ".join(current))
                # Overlap
                overlap_words = current[-(self._overlap_chars // 6) :] if current else []
                current = list(overlap_words)
                current_length = sum(len(w) + 1 for w in current)

            current.append(word)
            current_length += word_length

        if current:
            chunks.append(" ".join(current))

        return chunks

    def _merge_tiny(self, chunks: list[str]) -> list[str]:
        """Merge chunks smaller than min_chunk_size with adjacent chunks."""
        if len(chunks) <= 1:
            return chunks

        merged: list[str] = []
        buffer = ""

        for chunk in chunks:
            if buffer:
                combined = buffer + "\n\n" + chunk
                if _estimate_tokens(combined) <= self.chunk_size:
                    buffer = combined
                else:
                    merged.append(buffer)
                    buffer = chunk
            elif _estimate_tokens(chunk) < self.min_chunk_size:
                buffer = chunk
            else:
                buffer = chunk

        if buffer:
            if merged and _estimate_tokens(buffer) < self.min_chunk_size:
                merged[-1] = merged[-1] + "\n\n" + buffer
            else:
                merged.append(buffer)

        return merged
