"""Knowledge Foundry — HTML Exporter.

Exports entities to HTML format with clean styling.
Designed to be print-friendly and suitable for PDF conversion.
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


class HTMLExporter(BaseExporter):
    """Export entities to HTML format.

    Produces well-formatted HTML documents with embedded CSS for
    consistent styling across platforms.
    """

    @property
    def format_id(self) -> str:
        return "html"

    @property
    def label(self) -> str:
        return "HTML"

    @property
    def description(self) -> str:
        return "Export as an HTML document (.html)"

    @property
    def mime_type(self) -> str:
        return "text/html"

    @property
    def extension(self) -> str:
        return ".html"

    @property
    def supported_entity_types(self) -> list[EntityType]:
        return [
            EntityType.CONVERSATION,
            EntityType.MESSAGE,
            EntityType.RAG_RUN,
            EntityType.EVALUATION_REPORT,
        ]

    def _get_css(self) -> str:
        """Return embedded CSS for the HTML export."""
        return """
        :root {
            --primary: #2563eb;
            --primary-light: #dbeafe;
            --text: #1f2937;
            --text-light: #6b7280;
            --bg: #ffffff;
            --bg-alt: #f9fafb;
            --border: #e5e7eb;
            --success: #10b981;
            --error: #ef4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: var(--text);
            background: var(--bg);
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
        }
        h1 { font-size: 1.75rem; margin-bottom: 1rem; color: var(--primary); }
        h2 { font-size: 1.25rem; margin: 1.5rem 0 0.75rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
        h3 { font-size: 1rem; margin: 1rem 0 0.5rem; }
        p, ul, ol { margin-bottom: 1rem; }
        code { background: var(--bg-alt); padding: 0.125rem 0.25rem; border-radius: 3px; font-size: 0.875rem; }
        pre { background: var(--bg-alt); padding: 1rem; border-radius: 6px; overflow-x: auto; margin: 1rem 0; }
        pre code { background: none; padding: 0; }
        .meta { color: var(--text-light); font-size: 0.875rem; margin-bottom: 1rem; }
        .meta-item { display: inline-block; margin-right: 1rem; }
        .message { border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
        .message-user { background: var(--primary-light); border-color: var(--primary); }
        .message-assistant { background: var(--bg-alt); }
        .message-header { font-weight: 600; margin-bottom: 0.5rem; }
        .citation { background: var(--bg-alt); border-left: 3px solid var(--primary); padding: 0.75rem; margin: 0.5rem 0; }
        .context-block { background: var(--bg-alt); border-radius: 6px; padding: 1rem; margin: 0.5rem 0; }
        .score { color: var(--primary); font-weight: 600; }
        table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: var(--bg-alt); font-weight: 600; }
        .status-pass { color: var(--success); }
        .status-fail { color: var(--error); }
        blockquote { border-left: 3px solid var(--primary); padding-left: 1rem; margin: 1rem 0; color: var(--text-light); }
        @media print {
            body { max-width: 100%; padding: 1rem; }
            .message { break-inside: avoid; }
        }
        """

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _nl2br(self, text: str) -> str:
        """Convert newlines to <br> tags."""
        return self._escape_html(text).replace("\n", "<br>\n")

    def generate(
        self,
        entity: ExportableEntity,
        options: ExportOptions,
        context: ExportContext,
    ) -> ExportResult:
        """Generate HTML export."""
        try:
            if isinstance(entity, ExportableConversation):
                body = self._export_conversation(entity, options)
                title = entity.title
            elif isinstance(entity, ExportableMessage):
                body = self._export_message(entity, options)
                title = f"Message - {entity.role}"
            elif isinstance(entity, ExportableRAGRun):
                body = self._export_rag_run(entity, options)
                title = "RAG Query Result"
            elif isinstance(entity, ExportableEvaluationReport):
                body = self._export_evaluation_report(entity, options)
                title = entity.title
            else:
                return ExportResult(
                    success=False,
                    error=f"Unsupported entity type: {type(entity).__name__}",
                )

            html = self._wrap_html(title, body, options)

            if options.anonymize_user:
                html = self._anonymize_content(html)

            return ExportResult(
                success=True,
                content=html.encode("utf-8"),
                mime_type=self.mime_type,
            )
        except Exception as e:
            return ExportResult(success=False, error=str(e))

    def _wrap_html(self, title: str, body: str, options: ExportOptions) -> str:
        """Wrap body content in HTML document structure."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self._escape_html(title)} - Knowledge Foundry Export</title>
    <style>{self._get_css()}</style>
</head>
<body>
{body}
<footer style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--text-light); font-size: 0.875rem;">
    Exported from Knowledge Foundry on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</footer>
</body>
</html>"""

    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime for display."""
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    def _export_conversation(
        self,
        conv: ExportableConversation,
        options: ExportOptions,
    ) -> str:
        """Export a conversation to HTML."""
        parts: list[str] = []

        parts.append(f"<h1>{self._escape_html(conv.title)}</h1>")

        if options.include_metadata:
            parts.append('<div class="meta">')
            parts.append(f'<span class="meta-item"><strong>ID:</strong> {self._escape_html(conv.id)}</span>')
            parts.append(f'<span class="meta-item"><strong>Created:</strong> {self._format_datetime(conv.created_at)}</span>')
            parts.append(f'<span class="meta-item"><strong>Updated:</strong> {self._format_datetime(conv.updated_at)}</span>')
            if conv.model_info:
                parts.append(f'<span class="meta-item"><strong>Model:</strong> {self._escape_html(conv.model_info)}</span>')
            parts.append("</div>")

        parts.append("<h2>Messages</h2>")

        for msg in conv.messages:
            role_class = "message-user" if msg.role == "user" else "message-assistant"
            role_display = "User" if msg.role == "user" else "Assistant"
            if msg.role == "system":
                role_display = "System"

            parts.append(f'<div class="message {role_class}">')
            parts.append(f'<div class="message-header">{role_display}</div>')

            if options.include_metadata:
                meta_parts = [self._format_datetime(msg.timestamp)]
                if msg.model:
                    meta_parts.append(f"Model: {msg.model}")
                if msg.confidence is not None:
                    meta_parts.append(f"Confidence: {msg.confidence:.0%}")
                parts.append(f'<div class="meta">{" | ".join(meta_parts)}</div>')

            parts.append(f"<p>{self._nl2br(msg.content)}</p>")
            parts.append("</div>")

        # Citations
        if options.include_citations:
            all_citations = []
            for msg in conv.messages:
                all_citations.extend(msg.citations)

            if all_citations:
                parts.append("<h2>Sources</h2>")
                seen_ids = set()
                for cite in all_citations:
                    if cite.document_id in seen_ids:
                        continue
                    seen_ids.add(cite.document_id)
                    parts.append('<div class="citation">')
                    parts.append(f"<strong>{self._escape_html(cite.title)}</strong>")
                    if cite.section:
                        parts.append(f"<br><em>Section: {self._escape_html(cite.section)}</em>")
                    parts.append(f'<br><span class="score">Relevance: {cite.relevance_score:.0%}</span>')
                    parts.append("</div>")

        return "\n".join(parts)

    def _export_message(
        self,
        msg: ExportableMessage,
        options: ExportOptions,
    ) -> str:
        """Export a single message to HTML."""
        parts: list[str] = []

        role_display = "User Message" if msg.role == "user" else "Assistant Response"
        if msg.role == "system":
            role_display = "System Message"

        parts.append(f"<h1>{role_display}</h1>")

        if options.include_metadata:
            parts.append("<h2>Details</h2>")
            parts.append('<div class="meta">')
            parts.append(f"<p><strong>ID:</strong> <code>{self._escape_html(msg.id)}</code></p>")
            parts.append(f"<p><strong>Timestamp:</strong> {self._format_datetime(msg.timestamp)}</p>")
            if msg.model:
                parts.append(f"<p><strong>Model:</strong> {self._escape_html(msg.model)}</p>")
            if msg.confidence is not None:
                parts.append(f"<p><strong>Confidence:</strong> {msg.confidence:.0%}</p>")
            if msg.latency_ms:
                parts.append(f"<p><strong>Latency:</strong> {msg.latency_ms}ms</p>")
            if msg.cost_usd:
                parts.append(f"<p><strong>Cost:</strong> ${msg.cost_usd:.4f}</p>")
            parts.append("</div>")

        parts.append("<h2>Content</h2>")
        parts.append(f"<p>{self._nl2br(msg.content)}</p>")

        if options.include_citations and msg.citations:
            parts.append("<h2>Citations</h2>")
            for cite in msg.citations:
                parts.append('<div class="citation">')
                parts.append(f"<strong>{self._escape_html(cite.title)}</strong>")
                if cite.section:
                    parts.append(f"<br><em>Section: {self._escape_html(cite.section)}</em>")
                parts.append(f'<br><span class="score">Relevance: {cite.relevance_score:.0%}</span>')
                parts.append("</div>")

        return "\n".join(parts)

    def _export_rag_run(
        self,
        run: ExportableRAGRun,
        options: ExportOptions,
    ) -> str:
        """Export a RAG run to HTML."""
        parts: list[str] = []

        parts.append("<h1>RAG Query Result</h1>")

        if options.include_metadata:
            parts.append("<h2>Run Details</h2>")
            parts.append('<div class="meta">')
            parts.append(f"<p><strong>ID:</strong> <code>{self._escape_html(run.id)}</code></p>")
            parts.append(f"<p><strong>Timestamp:</strong> {self._format_datetime(run.timestamp)}</p>")
            if run.model:
                parts.append(f"<p><strong>Model:</strong> {self._escape_html(run.model)}</p>")
            if run.model_tier:
                parts.append(f"<p><strong>Tier:</strong> {self._escape_html(run.model_tier)}</p>")
            parts.append(f"<p><strong>Latency:</strong> {run.latency_ms}ms</p>")
            parts.append(f"<p><strong>Tokens:</strong> {run.input_tokens} in / {run.output_tokens} out</p>")
            if run.cost_usd:
                parts.append(f"<p><strong>Cost:</strong> ${run.cost_usd:.4f}</p>")
            if run.confidence is not None:
                parts.append(f"<p><strong>Confidence:</strong> {run.confidence:.0%}</p>")
            parts.append("</div>")

        parts.append("<h2>Query</h2>")
        parts.append(f"<blockquote>{self._nl2br(run.query)}</blockquote>")

        parts.append("<h2>Answer</h2>")
        parts.append(f"<p>{self._nl2br(run.answer)}</p>")

        if run.contexts:
            parts.append("<h2>Retrieved Context</h2>")
            for i, ctx in enumerate(run.contexts, 1):
                parts.append('<div class="context-block">')
                parts.append(f"<h3>Context {i}: {self._escape_html(ctx.title)}</h3>")
                parts.append(f'<p class="score">Score: {ctx.score:.0%}</p>')
                text_preview = ctx.text[:500] + ("..." if len(ctx.text) > 500 else "")
                parts.append(f"<blockquote>{self._nl2br(text_preview)}</blockquote>")
                parts.append("</div>")

        if options.include_citations and run.citations:
            parts.append("<h2>Citations</h2>")
            for cite in run.citations:
                parts.append('<div class="citation">')
                parts.append(f"<strong>{self._escape_html(cite.title)}</strong>")
                parts.append(f' <span class="score">(relevance: {cite.relevance_score:.0%})</span>')
                parts.append("</div>")

        if run.evaluation_metrics:
            parts.append("<h2>Evaluation Metrics</h2>")
            parts.append("<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>")
            for name, value in run.evaluation_metrics.items():
                parts.append(f"<tr><td>{self._escape_html(name)}</td><td>{value:.2f}</td></tr>")
            parts.append("</tbody></table>")

        return "\n".join(parts)

    def _export_evaluation_report(
        self,
        report: ExportableEvaluationReport,
        options: ExportOptions,
    ) -> str:
        """Export an evaluation report to HTML."""
        parts: list[str] = []

        parts.append(f"<h1>{self._escape_html(report.title)}</h1>")

        if options.include_metadata:
            parts.append("<h2>Report Details</h2>")
            parts.append('<div class="meta">')
            parts.append(f"<p><strong>ID:</strong> <code>{self._escape_html(report.id)}</code></p>")
            parts.append(f"<p><strong>Generated:</strong> {self._format_datetime(report.timestamp)}</p>")
            if report.model_info:
                parts.append(f"<p><strong>Model:</strong> {self._escape_html(report.model_info)}</p>")
            parts.append(f"<p><strong>Dataset Size:</strong> {report.dataset_size}</p>")
            parts.append(f'<p><strong>Passed:</strong> <span class="status-pass">{report.passed_count}</span></p>')
            parts.append(f'<p><strong>Failed:</strong> <span class="status-fail">{report.failed_count}</span></p>')
            if report.overall_score is not None:
                parts.append(f"<p><strong>Overall Score:</strong> {report.overall_score:.2%}</p>")
            parts.append("</div>")

        parts.append("<h2>Metrics</h2>")
        parts.append("<table><thead><tr><th>Metric</th><th>Value</th><th>Threshold</th><th>Status</th></tr></thead><tbody>")
        for metric in report.metrics:
            threshold = f"{metric.threshold:.2f}" if metric.threshold else "-"
            if metric.passed is True:
                status = '<span class="status-pass">✓ Pass</span>'
            elif metric.passed is False:
                status = '<span class="status-fail">✗ Fail</span>'
            else:
                status = "-"
            parts.append(f"<tr><td>{self._escape_html(metric.name)}</td><td>{metric.value:.2f}</td><td>{threshold}</td><td>{status}</td></tr>")
        parts.append("</tbody></table>")

        if report.examples:
            parts.append("<h2>Example Cases</h2>")
            for i, ex in enumerate(report.examples, 1):
                status_class = "status-pass" if ex.passed else "status-fail"
                status = "✓ Pass" if ex.passed else "✗ Fail"
                parts.append(f'<div class="context-block">')
                parts.append(f'<h3>Example {i} <span class="{status_class}">{status}</span></h3>')
                parts.append(f"<p><strong>Query:</strong> {self._nl2br(ex.query)}</p>")
                if ex.expected:
                    parts.append(f"<p><strong>Expected:</strong> {self._nl2br(ex.expected)}</p>")
                parts.append(f"<p><strong>Actual:</strong> {self._nl2br(ex.actual)}</p>")
                if ex.notes:
                    parts.append(f"<p><em>Notes: {self._nl2br(ex.notes)}</em></p>")
                parts.append("</div>")

        return "\n".join(parts)
