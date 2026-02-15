"""Knowledge Foundry — Plain Text Exporter.

Exports entities to plain text format for maximum compatibility.
"""

from __future__ import annotations

from datetime import datetime

from src.export.base import BaseExporter, ExportableEntity
from src.export.models import (
    EntityType,
    ExportableConversation,
    ExportableEvaluationReport,
    ExportableMessage,
    ExportableRAGRun,
    ExportContext,
    ExportOptions,
    ExportResult,
)


class TextExporter(BaseExporter):
    """Export entities to plain text format.

    Produces simple, unformatted text output suitable for
    maximum compatibility with any system.
    """

    @property
    def format_id(self) -> str:
        return "text"

    @property
    def label(self) -> str:
        return "Plain Text"

    @property
    def description(self) -> str:
        return "Export as plain text (.txt)"

    @property
    def mime_type(self) -> str:
        return "text/plain"

    @property
    def extension(self) -> str:
        return ".txt"

    @property
    def supported_entity_types(self) -> list[EntityType]:
        return [
            EntityType.CONVERSATION,
            EntityType.MESSAGE,
            EntityType.RAG_RUN,
            EntityType.EVALUATION_REPORT,
        ]

    def generate(
        self,
        entity: ExportableEntity,
        options: ExportOptions,
        context: ExportContext,
    ) -> ExportResult:
        """Generate plain text export."""
        try:
            if isinstance(entity, ExportableConversation):
                content = self._export_conversation(entity, options)
            elif isinstance(entity, ExportableMessage):
                content = self._export_message(entity, options)
            elif isinstance(entity, ExportableRAGRun):
                content = self._export_rag_run(entity, options)
            elif isinstance(entity, ExportableEvaluationReport):
                content = self._export_evaluation_report(entity, options)
            else:
                return ExportResult(
                    success=False,
                    error=f"Unsupported entity type: {type(entity).__name__}",
                )

            if options.anonymize_user:
                content = self._anonymize_content(content)

            return ExportResult(
                success=True,
                content=content.encode("utf-8"),
                mime_type=self.mime_type,
            )
        except Exception as e:
            return ExportResult(success=False, error=str(e))

    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime for display."""
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _separator(self, char: str = "=", width: int = 60) -> str:
        """Create a separator line."""
        return char * width

    def _export_conversation(
        self,
        conv: ExportableConversation,
        options: ExportOptions,
    ) -> str:
        """Export a conversation to plain text."""
        lines: list[str] = []

        lines.append(self._separator())
        lines.append(conv.title.upper())
        lines.append(self._separator())
        lines.append("")

        if options.include_metadata:
            lines.append(f"ID: {conv.id}")
            lines.append(f"Created: {self._format_datetime(conv.created_at)}")
            lines.append(f"Updated: {self._format_datetime(conv.updated_at)}")
            if conv.model_info:
                lines.append(f"Model: {conv.model_info}")
            lines.append("")
            lines.append(self._separator("-"))
            lines.append("")

        for msg in conv.messages:
            role = msg.role.upper()
            lines.append(f"[{role}]")
            if options.include_metadata:
                lines.append(f"Time: {self._format_datetime(msg.timestamp)}")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
            lines.append(self._separator("-", 40))
            lines.append("")

        if options.include_citations:
            all_citations = []
            for msg in conv.messages:
                all_citations.extend(msg.citations)

            if all_citations:
                lines.append("SOURCES")
                lines.append(self._separator("-", 40))
                seen_ids = set()
                for i, cite in enumerate(all_citations, 1):
                    if cite.document_id in seen_ids:
                        continue
                    seen_ids.add(cite.document_id)
                    lines.append(f"{i}. {cite.title}")
                    if cite.section:
                        lines.append(f"   Section: {cite.section}")
                    lines.append(f"   Relevance: {cite.relevance_score:.0%}")
                    lines.append("")

        lines.append(self._separator())
        lines.append(f"Exported from Knowledge Foundry on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    def _export_message(
        self,
        msg: ExportableMessage,
        options: ExportOptions,
    ) -> str:
        """Export a single message to plain text."""
        lines: list[str] = []

        role_display = "USER MESSAGE" if msg.role == "user" else "ASSISTANT RESPONSE"
        if msg.role == "system":
            role_display = "SYSTEM MESSAGE"

        lines.append(self._separator())
        lines.append(role_display)
        lines.append(self._separator())
        lines.append("")

        if options.include_metadata:
            lines.append(f"ID: {msg.id}")
            lines.append(f"Timestamp: {self._format_datetime(msg.timestamp)}")
            if msg.model:
                lines.append(f"Model: {msg.model}")
            if msg.confidence is not None:
                lines.append(f"Confidence: {msg.confidence:.0%}")
            if msg.latency_ms:
                lines.append(f"Latency: {msg.latency_ms}ms")
            if msg.cost_usd:
                lines.append(f"Cost: ${msg.cost_usd:.4f}")
            lines.append("")
            lines.append(self._separator("-"))
            lines.append("")

        lines.append("CONTENT:")
        lines.append("")
        lines.append(msg.content)
        lines.append("")

        if options.include_citations and msg.citations:
            lines.append(self._separator("-"))
            lines.append("CITATIONS:")
            lines.append("")
            for i, cite in enumerate(msg.citations, 1):
                lines.append(f"{i}. {cite.title}")
                lines.append(f"   Relevance: {cite.relevance_score:.0%}")
                lines.append("")

        lines.append(self._separator())
        lines.append(f"Exported from Knowledge Foundry on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    def _export_rag_run(
        self,
        run: ExportableRAGRun,
        options: ExportOptions,
    ) -> str:
        """Export a RAG run to plain text."""
        lines: list[str] = []

        lines.append(self._separator())
        lines.append("RAG QUERY RESULT")
        lines.append(self._separator())
        lines.append("")

        if options.include_metadata:
            lines.append(f"ID: {run.id}")
            lines.append(f"Timestamp: {self._format_datetime(run.timestamp)}")
            if run.model:
                lines.append(f"Model: {run.model}")
            if run.model_tier:
                lines.append(f"Tier: {run.model_tier}")
            lines.append(f"Latency: {run.latency_ms}ms")
            lines.append(f"Tokens: {run.input_tokens} in / {run.output_tokens} out")
            if run.cost_usd:
                lines.append(f"Cost: ${run.cost_usd:.4f}")
            if run.confidence is not None:
                lines.append(f"Confidence: {run.confidence:.0%}")
            lines.append("")
            lines.append(self._separator("-"))
            lines.append("")

        lines.append("QUERY:")
        lines.append(run.query)
        lines.append("")
        lines.append(self._separator("-"))
        lines.append("")
        lines.append("ANSWER:")
        lines.append(run.answer)
        lines.append("")

        if run.contexts:
            lines.append(self._separator("-"))
            lines.append("RETRIEVED CONTEXT:")
            lines.append("")
            for i, ctx in enumerate(run.contexts, 1):
                lines.append(f"Context {i}: {ctx.title}")
                lines.append(f"Score: {ctx.score:.0%}")
                text_preview = ctx.text[:500] + ("..." if len(ctx.text) > 500 else "")
                lines.append(text_preview)
                lines.append("")

        if options.include_citations and run.citations:
            lines.append(self._separator("-"))
            lines.append("CITATIONS:")
            for cite in run.citations:
                lines.append(f"- {cite.title} (relevance: {cite.relevance_score:.0%})")
            lines.append("")

        if run.evaluation_metrics:
            lines.append(self._separator("-"))
            lines.append("EVALUATION METRICS:")
            for name, value in run.evaluation_metrics.items():
                lines.append(f"- {name}: {value:.2f}")
            lines.append("")

        lines.append(self._separator())
        lines.append(f"Exported from Knowledge Foundry on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    def _export_evaluation_report(
        self,
        report: ExportableEvaluationReport,
        options: ExportOptions,
    ) -> str:
        """Export an evaluation report to plain text."""
        lines: list[str] = []

        lines.append(self._separator())
        lines.append(report.title.upper())
        lines.append(self._separator())
        lines.append("")

        if options.include_metadata:
            lines.append(f"ID: {report.id}")
            lines.append(f"Generated: {self._format_datetime(report.timestamp)}")
            if report.model_info:
                lines.append(f"Model: {report.model_info}")
            lines.append(f"Dataset Size: {report.dataset_size}")
            lines.append(f"Passed: {report.passed_count}")
            lines.append(f"Failed: {report.failed_count}")
            if report.overall_score is not None:
                lines.append(f"Overall Score: {report.overall_score:.2%}")
            lines.append("")
            lines.append(self._separator("-"))
            lines.append("")

        lines.append("METRICS:")
        lines.append("")
        # Table header
        lines.append(f"{'Metric':<30} {'Value':<10} {'Threshold':<10} {'Status':<10}")
        lines.append("-" * 60)
        for metric in report.metrics:
            threshold = f"{metric.threshold:.2f}" if metric.threshold else "-"
            if metric.passed is True:
                status = "PASS"
            elif metric.passed is False:
                status = "FAIL"
            else:
                status = "-"
            lines.append(f"{metric.name:<30} {metric.value:<10.2f} {threshold:<10} {status:<10}")
        lines.append("")

        if report.examples:
            lines.append(self._separator("-"))
            lines.append("EXAMPLE CASES:")
            lines.append("")
            for i, ex in enumerate(report.examples, 1):
                status = "PASS" if ex.passed else "FAIL"
                lines.append(f"Example {i} [{status}]")
                lines.append(f"Query: {ex.query}")
                if ex.expected:
                    lines.append(f"Expected: {ex.expected}")
                lines.append(f"Actual: {ex.actual}")
                if ex.notes:
                    lines.append(f"Notes: {ex.notes}")
                lines.append("")

        lines.append(self._separator())
        lines.append(f"Exported from Knowledge Foundry on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)
