"""Knowledge Foundry — Base Exporter Interface.

Defines the abstract base class that all exporters must implement.
This provides a consistent interface for the export registry to work with.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Union

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

# Type alias for any exportable entity
ExportableEntity = Union[
    ExportableConversation,
    ExportableMessage,
    ExportableRAGRun,
    ExportableEvaluationReport,
]


class BaseExporter(ABC):
    """Abstract base class for export format implementations.

    All exporters must inherit from this class and implement the required methods.
    This ensures consistency across different export formats and enables the
    registry to work with any exporter implementation.

    Example implementation:
        class MyExporter(BaseExporter):
            @property
            def format_id(self) -> str:
                return "my_format"

            @property
            def label(self) -> str:
                return "My Format"

            # ... implement other required methods
    """

    @property
    @abstractmethod
    def format_id(self) -> str:
        """Return the unique machine-readable identifier for this format.

        Examples: "markdown", "pdf", "docx", "json"
        """
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        """Return the human-friendly label for this format.

        Examples: "Markdown", "PDF Document", "Word Document"
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a brief description of this export format.

        Example: "Export as a formatted Markdown document"
        """
        ...

    @property
    @abstractmethod
    def mime_type(self) -> str:
        """Return the MIME type for this format.

        Examples: "text/markdown", "application/pdf", "application/json"
        """
        ...

    @property
    @abstractmethod
    def extension(self) -> str:
        """Return the default file extension for this format.

        Examples: ".md", ".pdf", ".docx", ".json"
        """
        ...

    @property
    @abstractmethod
    def supported_entity_types(self) -> list[EntityType]:
        """Return the list of entity types this exporter supports.

        Most exporters support all types, but some may be specialized.
        """
        ...

    def get_options_schema(self) -> dict[str, Any]:
        """Return a JSON schema describing available export options.

        Override this to expose format-specific options to the UI.
        Default implementation returns the standard options.
        """
        return {
            "type": "object",
            "properties": {
                "include_metadata": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include timestamps, IDs, and other metadata",
                },
                "include_citations": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include source citations",
                },
                "anonymize_user": {
                    "type": "boolean",
                    "default": False,
                    "description": "Mask user identifiers for privacy",
                },
                "include_raw_json_appendix": {
                    "type": "boolean",
                    "default": False,
                    "description": "Append raw JSON data",
                },
            },
        }

    def validate_options(self, options: ExportOptions) -> tuple[bool, str | None]:
        """Validate export options for this format.

        Args:
            options: The export options to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None

    @abstractmethod
    def generate(
        self,
        entity: ExportableEntity,
        options: ExportOptions,
        context: ExportContext,
    ) -> ExportResult:
        """Generate the export content.

        Args:
            entity: The canonical entity data to export
            options: Export configuration options
            context: User/tenant context for the export

        Returns:
            ExportResult containing the generated content or error
        """
        ...

    def generate_filename(
        self,
        entity: ExportableEntity,
        entity_type: EntityType,
    ) -> str:
        """Generate a suggested filename for the export.

        Args:
            entity: The entity being exported
            entity_type: The type of entity

        Returns:
            Suggested filename with extension
        """
        from datetime import datetime

        # Get entity title or ID
        if hasattr(entity, "title"):
            name = entity.title[:30].replace(" ", "-").lower()
        else:
            name = entity.id[:20]

        # Clean up the name (remove special characters)
        import re

        name = re.sub(r"[^a-z0-9-]", "", name)
        if not name:
            name = "export"

        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        return f"{entity_type.value}-{name}-{timestamp}{self.extension}"

    def _anonymize_content(self, content: str) -> str:
        """Anonymize user identifiers in content.

        Basic implementation replaces common patterns. Override for more
        sophisticated anonymization.
        """
        import re

        # Mask email addresses
        content = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "[REDACTED_EMAIL]",
            content,
        )
        # Mask common user ID patterns
        content = re.sub(r"\buser_[a-zA-Z0-9]+\b", "[REDACTED_USER_ID]", content)
        return content
