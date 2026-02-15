"""Knowledge Foundry — Export Registry.

Central registry for managing export plugins. Handles registration,
lookup, and execution of export operations.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from src.export.models import (
    EntityType,
    ExportContext,
    ExportFormat,
    ExporterInfo,
    ExportOptions,
    ExportResult,
)

if TYPE_CHECKING:
    from src.export.base import BaseExporter, ExportableEntity

logger = logging.getLogger(__name__)


class ExportRegistry:
    """Central registry for export format plugins.

    Manages registration and lookup of exporters, and provides a unified
    interface for executing exports with proper error handling and logging.

    Usage:
        registry = ExportRegistry()
        registry.register(MarkdownExporter())
        registry.register(PDFExporter())

        # List available formats
        formats = registry.list_formats(EntityType.CONVERSATION)

        # Execute an export
        result = registry.export(
            entity=conversation,
            entity_type=EntityType.CONVERSATION,
            format_id=ExportFormat.MARKDOWN,
            options=ExportOptions(),
            context=ExportContext(user_id="123"),
        )
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._exporters: dict[str, BaseExporter] = {}

    def register(self, exporter: BaseExporter) -> None:
        """Register an exporter instance.

        Args:
            exporter: The exporter to register

        Raises:
            ValueError: If an exporter with the same format_id is already registered
        """
        format_id = exporter.format_id
        if format_id in self._exporters:
            logger.warning(
                "Exporter already registered, replacing: %s",
                format_id,
            )
        self._exporters[format_id] = exporter
        logger.info(
            "Registered exporter: %s (%s)",
            format_id,
            exporter.label,
        )

    def unregister(self, format_id: str) -> bool:
        """Unregister an exporter.

        Args:
            format_id: The format ID to unregister

        Returns:
            True if the exporter was found and removed, False otherwise
        """
        if format_id in self._exporters:
            del self._exporters[format_id]
            logger.info("Unregistered exporter: %s", format_id)
            return True
        return False

    def get_exporter(self, format_id: str | ExportFormat) -> BaseExporter | None:
        """Get an exporter by format ID.

        Args:
            format_id: The format ID or ExportFormat enum

        Returns:
            The exporter instance or None if not found
        """
        if isinstance(format_id, ExportFormat):
            format_id = format_id.value
        return self._exporters.get(format_id)

    def list_formats(self, entity_type: EntityType | None = None) -> list[ExporterInfo]:
        """List available export formats.

        Args:
            entity_type: Optional filter by entity type

        Returns:
            List of ExporterInfo for available formats
        """
        result: list[ExporterInfo] = []
        for exporter in self._exporters.values():
            # Filter by entity type if specified
            if entity_type and entity_type not in exporter.supported_entity_types:
                continue

            result.append(
                ExporterInfo(
                    format_id=exporter.format_id,
                    label=exporter.label,
                    description=exporter.description,
                    mime_type=exporter.mime_type,
                    extension=exporter.extension,
                    supported_entity_types=exporter.supported_entity_types,
                    options_schema=exporter.get_options_schema(),
                )
            )
        return result

    def export(
        self,
        entity: ExportableEntity,
        entity_type: EntityType,
        format_id: str | ExportFormat,
        options: ExportOptions,
        context: ExportContext,
    ) -> ExportResult:
        """Execute an export operation.

        Args:
            entity: The entity data to export
            entity_type: The type of entity
            format_id: The target format
            options: Export configuration
            context: User/tenant context

        Returns:
            ExportResult with content or error
        """
        if isinstance(format_id, ExportFormat):
            format_id_str = format_id.value
        else:
            format_id_str = format_id

        # Get the exporter
        exporter = self.get_exporter(format_id_str)
        if not exporter:
            logger.error("Exporter not found: %s", format_id_str)
            return ExportResult(
                success=False,
                error=f"Export format '{format_id_str}' not supported",
                entity_type=entity_type,
                entity_id=getattr(entity, "id", "unknown"),
                format_id=ExportFormat(format_id_str) if format_id_str in [e.value for e in ExportFormat] else None,
            )

        # Check if entity type is supported
        if entity_type not in exporter.supported_entity_types:
            logger.error(
                "Entity type %s not supported by exporter %s",
                entity_type,
                format_id_str,
            )
            return ExportResult(
                success=False,
                error=f"Entity type '{entity_type.value}' not supported by '{format_id_str}' exporter",
                entity_type=entity_type,
                entity_id=getattr(entity, "id", "unknown"),
                format_id=ExportFormat(format_id_str),
            )

        # Validate options
        valid, error_msg = exporter.validate_options(options)
        if not valid:
            logger.error("Invalid export options: %s", error_msg)
            return ExportResult(
                success=False,
                error=f"Invalid export options: {error_msg}",
                entity_type=entity_type,
                entity_id=getattr(entity, "id", "unknown"),
                format_id=ExportFormat(format_id_str),
            )

        # Execute export
        start_time = time.time()
        try:
            result = exporter.generate(entity, options, context)

            # Generate filename if not set
            if result.success and not result.filename:
                result.filename = exporter.generate_filename(entity, entity_type)

            # Set metadata
            result.entity_type = entity_type
            result.entity_id = getattr(entity, "id", "unknown")
            result.format_id = ExportFormat(format_id_str)
            result.generation_time_ms = int((time.time() - start_time) * 1000)

            if result.content:
                result.size_bytes = len(result.content)

            logger.info(
                "Export completed: type=%s, format=%s, size=%d bytes, time=%d ms",
                entity_type.value,
                format_id_str,
                result.size_bytes,
                result.generation_time_ms,
            )
            return result

        except Exception as e:
            logger.exception("Export failed: %s", e)
            return ExportResult(
                success=False,
                error=f"Export generation failed: {str(e)}",
                entity_type=entity_type,
                entity_id=getattr(entity, "id", "unknown"),
                format_id=ExportFormat(format_id_str),
                generation_time_ms=int((time.time() - start_time) * 1000),
            )


# Global registry instance
_registry: ExportRegistry | None = None


def get_export_registry() -> ExportRegistry:
    """Get or create the global export registry.

    Creates the registry and registers all built-in exporters on first call.

    Returns:
        The global ExportRegistry instance
    """
    global _registry

    if _registry is None:
        _registry = ExportRegistry()

        # Import and register all built-in exporters
        from src.export.exporters.markdown import MarkdownExporter
        from src.export.exporters.html import HTMLExporter
        from src.export.exporters.pdf import PDFExporter
        from src.export.exporters.docx import DOCXExporter
        from src.export.exporters.json_exporter import JSONExporter
        from src.export.exporters.text import TextExporter

        _registry.register(MarkdownExporter())
        _registry.register(HTMLExporter())
        _registry.register(PDFExporter())
        _registry.register(DOCXExporter())
        _registry.register(JSONExporter())
        _registry.register(TextExporter())

        logger.info(
            "Export registry initialized with %d exporters",
            len(_registry._exporters),
        )

    return _registry


def reset_export_registry() -> None:
    """Reset the global registry (mainly for testing)."""
    global _registry
    _registry = None
