"""Unit tests for Export System.

Tests exporter implementations, registry, and API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from src.export import (
    EntityType,
    ExportableConversation,
    ExportableMessage,
    ExportableRAGRun,
    ExportableEvaluationReport,
    ExportContext,
    ExportFormat,
    ExportOptions,
    ExportRegistry,
    get_export_registry,
)
from src.export.models import Citation, RetrievedContext, EvaluationMetric, EvaluationExample
from src.export.exporters.markdown import MarkdownExporter
from src.export.exporters.html import HTMLExporter
from src.export.exporters.json_exporter import JSONExporter
from src.export.exporters.text import TextExporter
from src.export.registry import reset_export_registry


# Test fixtures

@pytest.fixture
def sample_message() -> ExportableMessage:
    """Create a sample message for testing."""
    return ExportableMessage(
        id="msg_001",
        role="assistant",
        content="Python is a high-level programming language known for its simplicity and readability.",
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        citations=[
            Citation(
                document_id="doc_001",
                title="Python Documentation",
                chunk_id="chunk_001",
                section="Introduction",
                relevance_score=0.95,
            ),
        ],
        model="claude-sonnet-4",
        confidence=0.92,
        latency_ms=250,
        cost_usd=0.0015,
    )


@pytest.fixture
def sample_conversation(sample_message: ExportableMessage) -> ExportableConversation:
    """Create a sample conversation for testing."""
    user_msg = ExportableMessage(
        id="msg_000",
        role="user",
        content="What is Python?",
        timestamp=datetime(2024, 1, 15, 10, 29, 0),
        citations=[],
    )
    return ExportableConversation(
        id="conv_001",
        title="Python Programming Discussion",
        messages=[user_msg, sample_message],
        created_at=datetime(2024, 1, 15, 10, 29, 0),
        updated_at=datetime(2024, 1, 15, 10, 30, 0),
        model_info="claude-sonnet-4",
    )


@pytest.fixture
def sample_rag_run() -> ExportableRAGRun:
    """Create a sample RAG run for testing."""
    return ExportableRAGRun(
        id="run_001",
        query="What are the benefits of Python?",
        answer="Python offers several benefits including easy syntax, large standard library, and cross-platform compatibility.",
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        contexts=[
            RetrievedContext(
                chunk_id="chunk_001",
                document_id="doc_001",
                title="Python Benefits",
                text="Python is known for its simple and readable syntax...",
                score=0.92,
            ),
        ],
        citations=[
            Citation(
                document_id="doc_001",
                title="Python Benefits",
                relevance_score=0.92,
            ),
        ],
        model="claude-sonnet-4",
        model_tier="sonnet",
        latency_ms=350,
        input_tokens=150,
        output_tokens=80,
        cost_usd=0.002,
        confidence=0.88,
        evaluation_metrics={"faithfulness": 0.95, "relevance": 0.90},
    )


@pytest.fixture
def sample_evaluation_report() -> ExportableEvaluationReport:
    """Create a sample evaluation report for testing."""
    return ExportableEvaluationReport(
        id="report_001",
        title="RAG Evaluation Report - Q1 2024",
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        metrics=[
            EvaluationMetric(name="Faithfulness", value=0.92, threshold=0.85, passed=True),
            EvaluationMetric(name="Relevance", value=0.88, threshold=0.80, passed=True),
            EvaluationMetric(name="Answer Correctness", value=0.75, threshold=0.85, passed=False),
        ],
        examples=[
            EvaluationExample(
                query="What is Python?",
                expected="A programming language",
                actual="Python is a high-level programming language",
                passed=True,
            ),
        ],
        overall_score=0.85,
        dataset_size=100,
        passed_count=85,
        failed_count=15,
        model_info="claude-sonnet-4",
    )


@pytest.fixture
def default_options() -> ExportOptions:
    """Create default export options."""
    return ExportOptions()


@pytest.fixture
def default_context() -> ExportContext:
    """Create default export context."""
    return ExportContext(user_id="user_001", tenant_id="tenant_001")


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the global registry before each test."""
    reset_export_registry()


# Markdown Exporter Tests

class TestMarkdownExporter:
    """Tests for Markdown exporter."""

    def test_format_id(self):
        exporter = MarkdownExporter()
        assert exporter.format_id == "markdown"
        assert exporter.extension == ".md"
        assert exporter.mime_type == "text/markdown"

    def test_supported_entity_types(self):
        exporter = MarkdownExporter()
        assert EntityType.CONVERSATION in exporter.supported_entity_types
        assert EntityType.MESSAGE in exporter.supported_entity_types
        assert EntityType.RAG_RUN in exporter.supported_entity_types
        assert EntityType.EVALUATION_REPORT in exporter.supported_entity_types

    def test_export_conversation(
        self,
        sample_conversation: ExportableConversation,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        result = exporter.generate(sample_conversation, default_options, default_context)

        assert result.success is True
        assert result.content is not None
        content = result.content.decode("utf-8")

        # Check content contains expected elements
        assert "Python Programming Discussion" in content
        assert "What is Python?" in content
        assert "User" in content or "**User:**" in content
        assert "Assistant" in content or "**Assistant:**" in content
        assert "Python Documentation" in content  # Citation

    def test_export_message(
        self,
        sample_message: ExportableMessage,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        result = exporter.generate(sample_message, default_options, default_context)

        assert result.success is True
        assert result.content is not None
        content = result.content.decode("utf-8")

        assert "Assistant Response" in content
        assert "Python is a high-level" in content
        assert "Python Documentation" in content

    def test_export_rag_run(
        self,
        sample_rag_run: ExportableRAGRun,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        result = exporter.generate(sample_rag_run, default_options, default_context)

        assert result.success is True
        assert result.content is not None
        content = result.content.decode("utf-8")

        assert "RAG Query Result" in content
        assert "What are the benefits of Python?" in content
        assert "Retrieved Context" in content
        assert "faithfulness" in content.lower()

    def test_export_evaluation_report(
        self,
        sample_evaluation_report: ExportableEvaluationReport,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        result = exporter.generate(sample_evaluation_report, default_options, default_context)

        assert result.success is True
        assert result.content is not None
        content = result.content.decode("utf-8")

        assert "RAG Evaluation Report" in content
        assert "Faithfulness" in content
        assert "85" in content  # passed count or score
        assert "Example Cases" in content or "Example" in content

    def test_anonymize_option(
        self,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        msg = ExportableMessage(
            id="msg_001",
            role="user",
            content="Contact me at user@example.com or user_12345",
            timestamp=datetime.now(),
        )

        default_options.anonymize_user = True
        result = exporter.generate(msg, default_options, default_context)

        assert result.success is True
        content = result.content.decode("utf-8")
        assert "user@example.com" not in content
        assert "[REDACTED_EMAIL]" in content

    def test_exclude_metadata(
        self,
        sample_message: ExportableMessage,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        options = ExportOptions(include_metadata=False)
        result = exporter.generate(sample_message, options, default_context)

        assert result.success is True
        content = result.content.decode("utf-8")
        # Should not have detailed metadata section
        assert "msg_001" not in content


# HTML Exporter Tests

class TestHTMLExporter:
    """Tests for HTML exporter."""

    def test_format_id(self):
        exporter = HTMLExporter()
        assert exporter.format_id == "html"
        assert exporter.extension == ".html"
        assert exporter.mime_type == "text/html"

    def test_export_conversation(
        self,
        sample_conversation: ExportableConversation,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = HTMLExporter()
        result = exporter.generate(sample_conversation, default_options, default_context)

        assert result.success is True
        assert result.content is not None
        content = result.content.decode("utf-8")

        # Check HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "<style>" in content
        assert "Python Programming Discussion" in content

    def test_html_escaping(
        self,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = HTMLExporter()
        msg = ExportableMessage(
            id="msg_001",
            role="user",
            content="Test <script>alert('xss')</script> content",
            timestamp=datetime.now(),
        )
        result = exporter.generate(msg, default_options, default_context)

        assert result.success is True
        content = result.content.decode("utf-8")
        assert "<script>" not in content
        assert "&lt;script&gt;" in content


# JSON Exporter Tests

class TestJSONExporter:
    """Tests for JSON exporter."""

    def test_format_id(self):
        exporter = JSONExporter()
        assert exporter.format_id == "json"
        assert exporter.extension == ".json"
        assert exporter.mime_type == "application/json"

    def test_export_conversation(
        self,
        sample_conversation: ExportableConversation,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        import json

        exporter = JSONExporter()
        result = exporter.generate(sample_conversation, default_options, default_context)

        assert result.success is True
        assert result.content is not None

        # Verify it's valid JSON
        data = json.loads(result.content.decode("utf-8"))
        assert "_export_metadata" in data
        assert "data" in data
        assert data["data"]["title"] == "Python Programming Discussion"

    def test_json_structure(
        self,
        sample_message: ExportableMessage,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        import json

        exporter = JSONExporter()
        result = exporter.generate(sample_message, default_options, default_context)

        data = json.loads(result.content.decode("utf-8"))
        assert data["_export_metadata"]["entity_type"] == "message"
        assert data["data"]["role"] == "assistant"


# Text Exporter Tests

class TestTextExporter:
    """Tests for plain text exporter."""

    def test_format_id(self):
        exporter = TextExporter()
        assert exporter.format_id == "text"
        assert exporter.extension == ".txt"
        assert exporter.mime_type == "text/plain"

    def test_export_conversation(
        self,
        sample_conversation: ExportableConversation,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = TextExporter()
        result = exporter.generate(sample_conversation, default_options, default_context)

        assert result.success is True
        assert result.content is not None
        content = result.content.decode("utf-8")

        assert "PYTHON PROGRAMMING DISCUSSION" in content
        assert "[USER]" in content
        assert "[ASSISTANT]" in content


# Export Registry Tests

class TestExportRegistry:
    """Tests for export registry."""

    def test_register_exporter(self):
        registry = ExportRegistry()
        exporter = MarkdownExporter()
        registry.register(exporter)

        assert registry.get_exporter("markdown") is exporter

    def test_list_formats(self):
        registry = ExportRegistry()
        registry.register(MarkdownExporter())
        registry.register(HTMLExporter())

        formats = registry.list_formats()
        assert len(formats) == 2

        format_ids = [f.format_id for f in formats]
        assert "markdown" in format_ids
        assert "html" in format_ids

    def test_list_formats_by_entity_type(self):
        registry = ExportRegistry()
        registry.register(MarkdownExporter())
        registry.register(HTMLExporter())

        formats = registry.list_formats(EntityType.CONVERSATION)
        assert len(formats) == 2

    def test_export_success(
        self,
        sample_conversation: ExportableConversation,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        registry = ExportRegistry()
        registry.register(MarkdownExporter())

        result = registry.export(
            entity=sample_conversation,
            entity_type=EntityType.CONVERSATION,
            format_id="markdown",
            options=default_options,
            context=default_context,
        )

        assert result.success is True
        assert result.content is not None
        assert result.mime_type == "text/markdown"
        assert result.entity_type == EntityType.CONVERSATION
        assert result.format_id == ExportFormat.MARKDOWN

    def test_export_unknown_format(
        self,
        sample_conversation: ExportableConversation,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        registry = ExportRegistry()

        result = registry.export(
            entity=sample_conversation,
            entity_type=EntityType.CONVERSATION,
            format_id="unknown_format",
            options=default_options,
            context=default_context,
        )

        assert result.success is False
        assert "not supported" in result.error.lower()


class TestGlobalRegistry:
    """Tests for global registry initialization."""

    def test_get_export_registry(self):
        registry = get_export_registry()

        assert registry is not None
        formats = registry.list_formats()

        # Should have all built-in exporters
        format_ids = [f.format_id for f in formats]
        assert "markdown" in format_ids
        assert "html" in format_ids
        assert "pdf" in format_ids
        assert "docx" in format_ids
        assert "json" in format_ids
        assert "text" in format_ids

    def test_registry_is_singleton(self):
        registry1 = get_export_registry()
        registry2 = get_export_registry()

        assert registry1 is registry2


# Edge Cases

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_conversation(
        self,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        conv = ExportableConversation(
            id="empty_001",
            title="Empty Conversation",
            messages=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        result = exporter.generate(conv, default_options, default_context)
        assert result.success is True

    def test_very_long_content(
        self,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        msg = ExportableMessage(
            id="long_001",
            role="assistant",
            content="x" * 100000,  # 100K characters
            timestamp=datetime.now(),
        )

        result = exporter.generate(msg, default_options, default_context)
        assert result.success is True
        assert len(result.content) > 100000

    def test_special_characters(
        self,
        default_options: ExportOptions,
        default_context: ExportContext,
    ):
        exporter = MarkdownExporter()
        msg = ExportableMessage(
            id="special_001",
            role="assistant",
            content="Test with special chars: é è ü ñ 中文 🎉 $100 & <tag>",
            timestamp=datetime.now(),
        )

        result = exporter.generate(msg, default_options, default_context)
        assert result.success is True
        content = result.content.decode("utf-8")
        assert "é" in content
        assert "中文" in content
        assert "🎉" in content

    def test_filename_generation(
        self,
        sample_conversation: ExportableConversation,
    ):
        exporter = MarkdownExporter()
        filename = exporter.generate_filename(sample_conversation, EntityType.CONVERSATION)

        assert filename.endswith(".md")
        assert "conversation" in filename
        assert "-" in filename  # Contains date
