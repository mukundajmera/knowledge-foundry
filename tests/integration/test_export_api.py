"""Integration tests for Export API endpoints.

Tests the export API routes including listing formats and generating exports.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.export.registry import reset_export_registry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the global registry before each test."""
    reset_export_registry()
    yield
    reset_export_registry()


@pytest.fixture
def app():
    """Create app for testing."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestListFormatsEndpoint:
    """Tests for GET /v1/export/formats endpoint."""

    @pytest.mark.asyncio
    async def test_list_all_formats(self, client: AsyncClient) -> None:
        """Test listing all available formats."""
        resp = await client.get("/v1/export/formats")
        assert resp.status_code == 200

        data = resp.json()
        assert "formats" in data
        assert len(data["formats"]) >= 6  # At least 6 built-in formats

        format_ids = [f["format_id"] for f in data["formats"]]
        assert "markdown" in format_ids
        assert "html" in format_ids
        assert "pdf" in format_ids
        assert "docx" in format_ids
        assert "json" in format_ids
        assert "text" in format_ids

    @pytest.mark.asyncio
    async def test_list_formats_with_entity_type_filter(self, client: AsyncClient) -> None:
        """Test filtering formats by entity type."""
        resp = await client.get("/v1/export/formats?entity_type=conversation")
        assert resp.status_code == 200

        data = resp.json()
        assert data["entity_type"] == "conversation"
        assert len(data["formats"]) >= 6

    @pytest.mark.asyncio
    async def test_list_formats_invalid_entity_type(self, client: AsyncClient) -> None:
        """Test with invalid entity type."""
        resp = await client.get("/v1/export/formats?entity_type=invalid_type")
        assert resp.status_code == 400
        assert "Invalid entity type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_format_info_structure(self, client: AsyncClient) -> None:
        """Test that format info contains expected fields."""
        resp = await client.get("/v1/export/formats")
        assert resp.status_code == 200

        data = resp.json()
        format_info = data["formats"][0]

        assert "format_id" in format_info
        assert "label" in format_info
        assert "description" in format_info
        assert "mime_type" in format_info
        assert "extension" in format_info
        assert "supported_entity_types" in format_info
        assert "options_schema" in format_info


class TestGetFormatInfoEndpoint:
    """Tests for GET /v1/export/formats/{format_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_markdown_format(self, client: AsyncClient) -> None:
        """Test getting info for markdown format."""
        resp = await client.get("/v1/export/formats/markdown")
        assert resp.status_code == 200

        data = resp.json()
        assert data["format_id"] == "markdown"
        assert data["extension"] == ".md"
        assert data["mime_type"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_get_unknown_format(self, client: AsyncClient) -> None:
        """Test getting info for unknown format."""
        resp = await client.get("/v1/export/formats/unknown_format")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestGenerateExportEndpoint:
    """Tests for POST /v1/export/generate endpoint."""

    @pytest.mark.asyncio
    async def test_export_conversation_to_markdown(self, client: AsyncClient) -> None:
        """Test exporting a conversation to markdown."""
        request_body = {
            "entity_type": "conversation",
            "entity_id": "conv_001",
            "format_id": "markdown",
            "options": {
                "include_metadata": True,
                "include_citations": True,
            },
            "entity_data": {
                "id": "conv_001",
                "title": "Test Conversation",
                "messages": [
                    {
                        "id": "msg_001",
                        "role": "user",
                        "content": "What is Python?",
                        "timestamp": 1705312200000,
                    },
                    {
                        "id": "msg_002",
                        "role": "assistant",
                        "content": "Python is a programming language.",
                        "timestamp": 1705312260000,
                        "citations": [
                            {
                                "document_id": "doc_001",
                                "title": "Python Docs",
                                "relevance_score": 0.9,
                            }
                        ],
                    },
                ],
                "createdAt": 1705312200000,
                "updatedAt": 1705312260000,
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 200

        # Check response headers
        assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
        assert "attachment" in resp.headers["content-disposition"]
        assert ".md" in resp.headers["content-disposition"]

        # Check content
        content = resp.text
        assert "Test Conversation" in content
        assert "What is Python?" in content
        assert "Python is a programming language" in content

    @pytest.mark.asyncio
    async def test_export_message_to_json(self, client: AsyncClient) -> None:
        """Test exporting a message to JSON."""
        import json

        request_body = {
            "entity_type": "message",
            "entity_id": "msg_001",
            "format_id": "json",
            "entity_data": {
                "id": "msg_001",
                "role": "assistant",
                "content": "Test response content",
                "timestamp": 1705312260000,
                "model": "claude-sonnet-4",
                "confidence": 0.92,
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 200

        assert resp.headers["content-type"] == "application/json"

        data = json.loads(resp.text)
        assert "_export_metadata" in data
        assert data["_export_metadata"]["entity_type"] == "message"
        assert data["data"]["content"] == "Test response content"

    @pytest.mark.asyncio
    async def test_export_to_html(self, client: AsyncClient) -> None:
        """Test exporting to HTML."""
        request_body = {
            "entity_type": "message",
            "entity_id": "msg_001",
            "format_id": "html",
            "entity_data": {
                "id": "msg_001",
                "role": "assistant",
                "content": "Test HTML export",
                "timestamp": 1705312260000,
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 200

        assert resp.headers["content-type"] == "text/html; charset=utf-8"
        assert "<!DOCTYPE html>" in resp.text
        assert "Test HTML export" in resp.text

    @pytest.mark.asyncio
    async def test_export_to_plain_text(self, client: AsyncClient) -> None:
        """Test exporting to plain text."""
        request_body = {
            "entity_type": "message",
            "entity_id": "msg_001",
            "format_id": "text",
            "entity_data": {
                "id": "msg_001",
                "role": "user",
                "content": "Plain text export test",
                "timestamp": 1705312260000,
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 200

        assert resp.headers["content-type"] == "text/plain; charset=utf-8"
        assert "USER MESSAGE" in resp.text
        assert "Plain text export test" in resp.text

    @pytest.mark.asyncio
    async def test_export_rag_run(self, client: AsyncClient) -> None:
        """Test exporting a RAG run."""
        request_body = {
            "entity_type": "rag_run",
            "entity_id": "run_001",
            "format_id": "markdown",
            "entity_data": {
                "id": "run_001",
                "query": "What is RAG?",
                "answer": "RAG stands for Retrieval-Augmented Generation.",
                "timestamp": 1705312260000,
                "contexts": [
                    {
                        "chunk_id": "chunk_001",
                        "document_id": "doc_001",
                        "title": "RAG Documentation",
                        "text": "RAG combines retrieval with generation...",
                        "score": 0.95,
                    }
                ],
                "latency_ms": 350,
                "evaluation_metrics": {
                    "faithfulness": 0.92,
                },
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 200

        content = resp.text
        assert "RAG Query Result" in content
        assert "What is RAG?" in content
        assert "Retrieved Context" in content

    @pytest.mark.asyncio
    async def test_export_with_anonymization(self, client: AsyncClient) -> None:
        """Test export with anonymization enabled."""
        request_body = {
            "entity_type": "message",
            "entity_id": "msg_001",
            "format_id": "markdown",
            "options": {
                "anonymize_user": True,
            },
            "entity_data": {
                "id": "msg_001",
                "role": "user",
                "content": "Contact me at user@example.com",
                "timestamp": 1705312260000,
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 200

        content = resp.text
        assert "user@example.com" not in content
        assert "[REDACTED_EMAIL]" in content

    @pytest.mark.asyncio
    async def test_export_invalid_entity_type(self, client: AsyncClient) -> None:
        """Test export with invalid entity type."""
        request_body = {
            "entity_type": "invalid_type",
            "entity_id": "id_001",
            "format_id": "markdown",
            "entity_data": {},
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 400
        assert "Invalid entity type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, client: AsyncClient) -> None:
        """Test export with invalid format."""
        request_body = {
            "entity_type": "message",
            "entity_id": "msg_001",
            "format_id": "invalid_format",
            "entity_data": {
                "id": "msg_001",
                "role": "user",
                "content": "Test",
                "timestamp": 1705312260000,
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 400
        assert "Invalid format" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_export_without_entity_data(self, client: AsyncClient) -> None:
        """Test export without providing entity data."""
        request_body = {
            "entity_type": "message",
            "entity_id": "msg_001",
            "format_id": "markdown",
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 400
        assert "entity_data is required" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_export_response_headers(self, client: AsyncClient) -> None:
        """Test that export response includes useful headers."""
        request_body = {
            "entity_type": "message",
            "entity_id": "msg_001",
            "format_id": "markdown",
            "entity_data": {
                "id": "msg_001",
                "role": "assistant",
                "content": "Test content",
                "timestamp": 1705312260000,
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 200

        # Check custom headers
        assert "x-export-size-bytes" in resp.headers
        assert "x-export-generation-time-ms" in resp.headers
        assert int(resp.headers["x-export-size-bytes"]) > 0


class TestExportWithEvaluationReport:
    """Tests for exporting evaluation reports."""

    @pytest.mark.asyncio
    async def test_export_evaluation_report(self, client: AsyncClient) -> None:
        """Test exporting an evaluation report."""
        request_body = {
            "entity_type": "evaluation_report",
            "entity_id": "report_001",
            "format_id": "markdown",
            "entity_data": {
                "id": "report_001",
                "title": "Q1 2024 RAG Evaluation",
                "timestamp": 1705312260000,
                "metrics": [
                    {
                        "name": "Faithfulness",
                        "value": 0.92,
                        "threshold": 0.85,
                        "passed": True,
                    },
                    {
                        "name": "Relevance",
                        "value": 0.75,
                        "threshold": 0.80,
                        "passed": False,
                    },
                ],
                "examples": [
                    {
                        "query": "Test query",
                        "expected": "Expected answer",
                        "actual": "Actual answer",
                        "passed": True,
                    },
                ],
                "overall_score": 0.85,
                "dataset_size": 100,
                "passed_count": 85,
                "failed_count": 15,
            },
        }

        resp = await client.post("/v1/export/generate", json=request_body)
        assert resp.status_code == 200

        content = resp.text
        assert "Q1 2024 RAG Evaluation" in content
        assert "Faithfulness" in content
        assert "Relevance" in content
        assert "85" in content  # passed count
