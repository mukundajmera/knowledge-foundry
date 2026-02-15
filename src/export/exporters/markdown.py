"""Knowledge Foundry — Markdown Exporter.

Exports entities to Markdown format for easy reading and sharing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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


class MarkdownExporter(BaseExporter):
    """Export entities to Markdown format.

    Produces well-formatted Markdown documents with proper headings,
    lists, and code formatting where appropriate.
    """

    @property
    def format_id(self) -> str:
        return "markdown"

    @property
    def label(self) -> str:
        return "Markdown"

    @property
    def description(self) -> str:
        return "Export as a formatted Markdown document (.md)"

    @property
    def mime_type(self) -> str:
        return "text/markdown"

    @property
    def extension(self) -> str:
        return ".md"

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
        """Generate Markdown export."""
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

    def _format_datetime(self, dt: datetime, locale: str = "en-US") -> str:
        """Format datetime for display."""
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    def _export_conversation(
        self,
        conv: ExportableConversation,
        options: ExportOptions,
    ) -> str:
        """Export a conversation to Markdown."""
        lines: list[str] = []

        # Title
        lines.append(f"# {conv.title}")
        lines.append("")

        # Metadata section
        if options.include_metadata:
            lines.append("## Conversation Details")
            lines.append("")
            lines.append(f"- **ID:** `{conv.id}`")
            lines.append(f"- **Created:** {self._format_datetime(conv.created_at)}")
            lines.append(f"- **Updated:** {self._format_datetime(conv.updated_at)}")
            if conv.model_info:
                lines.append(f"- **Model:** {conv.model_info}")
            lines.append("")

        # Messages
        lines.append("## Messages")
        lines.append("")

        for msg in conv.messages:
            lines.append(self._format_message_in_conversation(msg, options))
            lines.append("")

        # Citations section (if any messages have citations)
        if options.include_citations:
            all_citations = []
            for msg in conv.messages:
                all_citations.extend(msg.citations)

            if all_citations:
                lines.append("## Sources")
                lines.append("")
                seen_ids = set()
                for i, cite in enumerate(all_citations, 1):
                    if cite.document_id in seen_ids:
                        continue
                    seen_ids.add(cite.document_id)
                    lines.append(f"{i}. **{cite.title}**")
                    if cite.section:
                        lines.append(f"   - Section: {cite.section}")
                    lines.append(f"   - Relevance: {cite.relevance_score:.0%}")
                    lines.append("")

        # Raw JSON appendix
        if options.include_raw_json_appendix:
            lines.append("## Raw Data")
            lines.append("")
            lines.append("```json")
            lines.append(self._entity_to_json(conv))
            lines.append("```")

        return "\n".join(lines)

    def _format_message_in_conversation(
        self,
        msg: ExportableMessage,
        options: ExportOptions,
    ) -> str:
        """Format a single message within a conversation."""
        lines: list[str] = []

        # Role indicator
        role_display = "**User:**" if msg.role == "user" else "**Assistant:**"
        if msg.role == "system":
            role_display = "**System:**"

        lines.append(f"### {role_display}")

        if options.include_metadata:
            meta_parts = [self._format_datetime(msg.timestamp)]
            if msg.model:
                meta_parts.append(f"Model: {msg.model}")
            if msg.confidence is not None:
                meta_parts.append(f"Confidence: {msg.confidence:.0%}")
            lines.append(f"*{' | '.join(meta_parts)}*")
            lines.append("")

        lines.append(msg.content)

        return "\n".join(lines)

    def _export_message(
        self,
        msg: ExportableMessage,
        options: ExportOptions,
    ) -> str:
        """Export a single message to Markdown."""
        lines: list[str] = []

        role_display = "User Message" if msg.role == "user" else "Assistant Response"
        if msg.role == "system":
            role_display = "System Message"

        lines.append(f"# {role_display}")
        lines.append("")

        if options.include_metadata:
            lines.append("## Details")
            lines.append("")
            lines.append(f"- **ID:** `{msg.id}`")
            lines.append(f"- **Timestamp:** {self._format_datetime(msg.timestamp)}")
            if msg.model:
                lines.append(f"- **Model:** {msg.model}")
            if msg.confidence is not None:
                lines.append(f"- **Confidence:** {msg.confidence:.0%}")
            if msg.latency_ms:
                lines.append(f"- **Latency:** {msg.latency_ms}ms")
            if msg.cost_usd:
                lines.append(f"- **Cost:** ${msg.cost_usd:.4f}")
            lines.append("")

        lines.append("## Content")
        lines.append("")
        lines.append(msg.content)
        lines.append("")

        if options.include_citations and msg.citations:
            lines.append("## Citations")
            lines.append("")
            for i, cite in enumerate(msg.citations, 1):
                lines.append(f"{i}. **{cite.title}**")
                if cite.section:
                    lines.append(f"   - Section: {cite.section}")
                lines.append(f"   - Relevance: {cite.relevance_score:.0%}")
                lines.append("")

        if options.include_raw_json_appendix:
            lines.append("## Raw Data")
            lines.append("")
            lines.append("```json")
            lines.append(self._entity_to_json(msg))
            lines.append("```")

        return "\n".join(lines)

    def _export_rag_run(
        self,
        run: ExportableRAGRun,
        options: ExportOptions,
    ) -> str:
        """Export a RAG run to Markdown."""
        lines: list[str] = []

        lines.append("# RAG Query Result")
        lines.append("")

        if options.include_metadata:
            lines.append("## Run Details")
            lines.append("")
            lines.append(f"- **ID:** `{run.id}`")
            lines.append(f"- **Timestamp:** {self._format_datetime(run.timestamp)}")
            if run.model:
                lines.append(f"- **Model:** {run.model}")
            if run.model_tier:
                lines.append(f"- **Tier:** {run.model_tier}")
            lines.append(f"- **Latency:** {run.latency_ms}ms")
            lines.append(f"- **Tokens:** {run.input_tokens} in / {run.output_tokens} out")
            if run.cost_usd:
                lines.append(f"- **Cost:** ${run.cost_usd:.4f}")
            if run.confidence is not None:
                lines.append(f"- **Confidence:** {run.confidence:.0%}")
            lines.append("")

        lines.append("## Query")
        lines.append("")
        lines.append(f"> {run.query}")
        lines.append("")

        lines.append("## Answer")
        lines.append("")
        lines.append(run.answer)
        lines.append("")

        if run.contexts:
            lines.append("## Retrieved Context")
            lines.append("")
            for i, ctx in enumerate(run.contexts, 1):
                lines.append(f"### Context {i}: {ctx.title}")
                lines.append(f"*Score: {ctx.score:.0%}*")
                lines.append("")
                lines.append(f"> {ctx.text[:500]}{'...' if len(ctx.text) > 500 else ''}")
                lines.append("")

        if options.include_citations and run.citations:
            lines.append("## Citations")
            lines.append("")
            for i, cite in enumerate(run.citations, 1):
                lines.append(f"{i}. **{cite.title}** (relevance: {cite.relevance_score:.0%})")

        if run.evaluation_metrics:
            lines.append("")
            lines.append("## Evaluation Metrics")
            lines.append("")
            for name, value in run.evaluation_metrics.items():
                lines.append(f"- **{name}:** {value:.2f}")

        if options.include_raw_json_appendix:
            lines.append("")
            lines.append("## Raw Data")
            lines.append("")
            lines.append("```json")
            lines.append(self._entity_to_json(run))
            lines.append("```")

        return "\n".join(lines)

    def _export_evaluation_report(
        self,
        report: ExportableEvaluationReport,
        options: ExportOptions,
    ) -> str:
        """Export an evaluation report to Markdown."""
        lines: list[str] = []

        lines.append(f"# {report.title}")
        lines.append("")

        if options.include_metadata:
            lines.append("## Report Details")
            lines.append("")
            lines.append(f"- **ID:** `{report.id}`")
            lines.append(f"- **Generated:** {self._format_datetime(report.timestamp)}")
            if report.model_info:
                lines.append(f"- **Model:** {report.model_info}")
            lines.append(f"- **Dataset Size:** {report.dataset_size}")
            lines.append(f"- **Passed:** {report.passed_count}")
            lines.append(f"- **Failed:** {report.failed_count}")
            if report.overall_score is not None:
                lines.append(f"- **Overall Score:** {report.overall_score:.2%}")
            lines.append("")

        lines.append("## Metrics")
        lines.append("")
        lines.append("| Metric | Value | Threshold | Status |")
        lines.append("|--------|-------|-----------|--------|")
        for metric in report.metrics:
            threshold = f"{metric.threshold:.2f}" if metric.threshold else "-"
            status = "✅" if metric.passed else "❌" if metric.passed is False else "-"
            lines.append(f"| {metric.name} | {metric.value:.2f} | {threshold} | {status} |")
        lines.append("")

        if report.examples:
            lines.append("## Example Cases")
            lines.append("")
            for i, ex in enumerate(report.examples, 1):
                status = "✅" if ex.passed else "❌"
                lines.append(f"### Example {i} {status}")
                lines.append("")
                lines.append(f"**Query:** {ex.query}")
                lines.append("")
                if ex.expected:
                    lines.append(f"**Expected:** {ex.expected}")
                    lines.append("")
                lines.append(f"**Actual:** {ex.actual}")
                lines.append("")
                if ex.notes:
                    lines.append(f"*Notes: {ex.notes}*")
                    lines.append("")

        if options.include_raw_json_appendix:
            lines.append("## Raw Data")
            lines.append("")
            lines.append("```json")
            lines.append(self._entity_to_json(report))
            lines.append("```")

        return "\n".join(lines)

    def _entity_to_json(self, entity: Any) -> str:
        """Convert entity to JSON string for appendix."""
        import json
        from dataclasses import asdict

        def json_serializer(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        return json.dumps(asdict(entity), indent=2, default=json_serializer)
