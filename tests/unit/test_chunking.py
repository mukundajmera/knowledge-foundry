"""Tests for src.retrieval.chunking — SemanticChunker."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.core.exceptions import ChunkingError
from src.core.interfaces import Document
from src.retrieval.chunking import SemanticChunker, _estimate_tokens, _sha256


def _make_document(content: str, title: str = "Test Doc") -> Document:
    return Document(
        document_id=uuid4(),
        tenant_id=uuid4(),
        title=title,
        content=content,
    )


class TestTokenEstimation:
    def test_basic(self) -> None:
        assert _estimate_tokens("hello") >= 1

    def test_empty(self) -> None:
        assert _estimate_tokens("") == 1


class TestSha256:
    def test_deterministic(self) -> None:
        assert _sha256("hello") == _sha256("hello")

    def test_different(self) -> None:
        assert _sha256("hello") != _sha256("world")


class TestSemanticChunker:
    @pytest.fixture
    def chunker(self) -> SemanticChunker:
        return SemanticChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)

    def test_simple_document(self, chunker: SemanticChunker) -> None:
        doc = _make_document("This is a simple document with a few words.")
        chunks = chunker.chunk_document(doc)
        assert len(chunks) >= 1
        assert chunks[0].text == "This is a simple document with a few words."
        assert chunks[0].document_id == str(doc.document_id)
        assert chunks[0].tenant_id == str(doc.tenant_id)

    def test_heading_split(self, chunker: SemanticChunker) -> None:
        content = (
            "## Section 1\n"
            + "Content of section one. " * 20
            + "\n\n## Section 2\n"
            + "Content of section two. " * 20
        )
        doc = _make_document(content)
        chunks = chunker.chunk_document(doc)
        assert len(chunks) >= 2

    def test_paragraph_split(self, chunker: SemanticChunker) -> None:
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        doc = _make_document(content)
        chunks = chunker.chunk_document(doc)
        assert len(chunks) >= 1

    def test_chunk_metadata(self, chunker: SemanticChunker) -> None:
        doc = _make_document("Content here.", title="My Doc")
        chunks = chunker.chunk_document(doc)
        chunk = chunks[0]
        assert chunk.title == "My Doc"
        assert chunk.chunk_index == 0
        assert chunk.total_chunks == len(chunks)
        assert chunk.text_hash
        assert chunk.chunk_id

    def test_empty_content_raises(self, chunker: SemanticChunker) -> None:
        doc = _make_document("")
        with pytest.raises(ChunkingError):
            chunker.chunk_document(doc)

    def test_whitespace_only_raises(self, chunker: SemanticChunker) -> None:
        doc = _make_document("   \n\n   ")
        with pytest.raises(ChunkingError):
            chunker.chunk_document(doc)

    def test_large_document(self) -> None:
        chunker = SemanticChunker(chunk_size=50, chunk_overlap=10, min_chunk_size=5)
        content = "This is a sentence. " * 200
        doc = _make_document(content)
        chunks = chunker.chunk_document(doc)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.text

    def test_tags_propagation(self, chunker: SemanticChunker) -> None:
        doc = _make_document("Content here.")
        doc.tags = ["api", "python"]
        doc.visibility = "internal"
        chunks = chunker.chunk_document(doc)
        assert chunks[0].tags == ["api", "python"]
        assert chunks[0].visibility == "internal"
