"""Knowledge Foundry — PDF Exporter.

Exports entities to PDF format by converting HTML to PDF.
Uses weasyprint for HTML-to-PDF conversion if available,
falls back to basic HTML embedding otherwise.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from src.export.base import BaseExporter, ExportableEntity
from src.export.exporters.html import HTMLExporter
from src.export.models import (
    EntityType,
    ExportContext,
    ExportOptions,
    ExportResult,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Configurable PDF header text (can be customized for white-label deployments)
PDF_HEADER_TEXT = os.environ.get("EXPORT_PDF_HEADER", "Knowledge Foundry Export")


class PDFExporter(BaseExporter):
    """Export entities to PDF format.

    Uses the HTML exporter as a base and converts to PDF using
    weasyprint when available. Falls back to indicating PDF
    generation is not available if weasyprint is not installed.
    """

    def __init__(self) -> None:
        """Initialize PDF exporter and check for weasyprint."""
        self._html_exporter = HTMLExporter()
        self._weasyprint_available = self._check_weasyprint()

    def _check_weasyprint(self) -> bool:
        """Check if weasyprint is available."""
        try:
            import weasyprint  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "weasyprint not installed. PDF export will generate HTML-only content. "
                "Install with: pip install weasyprint"
            )
            return False

    @property
    def format_id(self) -> str:
        return "pdf"

    @property
    def label(self) -> str:
        return "PDF"

    @property
    def description(self) -> str:
        if self._weasyprint_available:
            return "Export as a PDF document (.pdf)"
        return "Export as a PDF document (requires weasyprint)"

    @property
    def mime_type(self) -> str:
        return "application/pdf"

    @property
    def extension(self) -> str:
        return ".pdf"

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
        """Generate PDF export."""
        # First generate HTML content
        html_result = self._html_exporter.generate(entity, options, context)
        if not html_result.success or not html_result.content:
            return ExportResult(
                success=False,
                error=html_result.error or "Failed to generate HTML for PDF",
            )

        if not self._weasyprint_available:
            return ExportResult(
                success=False,
                error="PDF generation requires weasyprint. Install with: pip install weasyprint",
            )

        try:
            import weasyprint

            # Convert HTML to PDF
            html_content = html_result.content.decode("utf-8")

            # Add print-specific styles for better PDF output
            html_with_print_styles = self._add_print_styles(html_content)

            # Generate PDF
            pdf_doc = weasyprint.HTML(string=html_with_print_styles)
            pdf_content = pdf_doc.write_pdf()

            return ExportResult(
                success=True,
                content=pdf_content,
                mime_type=self.mime_type,
            )
        except Exception as e:
            logger.exception("PDF generation failed: %s", e)
            return ExportResult(
                success=False,
                error=f"PDF generation failed: {str(e)}",
            )

    def _add_print_styles(self, html: str) -> str:
        """Add print-specific styles for better PDF output."""
        print_styles = f"""
        @page {{
            size: A4;
            margin: 2cm;
            @top-center {{
                content: "{PDF_HEADER_TEXT}";
                font-size: 9pt;
                color: #6b7280;
            }}
            @bottom-center {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #6b7280;
            }}
        }}
        @media print {{
            body {{ font-size: 10pt; }}
            h1 {{ font-size: 16pt; }}
            h2 {{ font-size: 13pt; page-break-after: avoid; }}
            h3 {{ font-size: 11pt; page-break-after: avoid; }}
            .message {{ page-break-inside: avoid; }}
            .context-block {{ page-break-inside: avoid; }}
            table {{ page-break-inside: avoid; }}
        }}
        """
        # Insert print styles into the existing style block
        return html.replace("</style>", print_styles + "</style>")
