"""Knowledge Foundry — JSON Exporter.

Exports entities to JSON format for programmatic access.
"""

from __future__ import annotations

import json
from dataclasses import asdict
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


class JSONExporter(BaseExporter):
    """Export entities to JSON format.

    Produces structured JSON output that can be used for data exchange,
    automation, or import into other systems.
    """

    @property
    def format_id(self) -> str:
        return "json"

    @property
    def label(self) -> str:
        return "JSON"

    @property
    def description(self) -> str:
        return "Export as structured JSON data (.json)"

    @property
    def mime_type(self) -> str:
        return "application/json"

    @property
    def extension(self) -> str:
        return ".json"

    @property
    def supported_entity_types(self) -> list[EntityType]:
        return [
            EntityType.CONVERSATION,
            EntityType.MESSAGE,
            EntityType.RAG_RUN,
            EntityType.EVALUATION_REPORT,
        ]

    def get_options_schema(self) -> dict[str, Any]:
        """Return options schema with JSON-specific options."""
        schema = super().get_options_schema()
        schema["properties"]["pretty_print"] = {
            "type": "boolean",
            "default": True,
            "description": "Format JSON with indentation for readability",
        }
        return schema

    def generate(
        self,
        entity: ExportableEntity,
        options: ExportOptions,
        context: ExportContext,
    ) -> ExportResult:
        """Generate JSON export."""
        try:
            # Convert entity to dictionary
            data = self._entity_to_dict(entity, options)

            # Add export metadata
            export_meta = {
                "export_format": "json",
                "export_version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "entity_type": self._get_entity_type(entity).value,
            }

            # Wrap in export envelope
            output = {
                "_export_metadata": export_meta,
                "data": data,
            }

            # Serialize to JSON
            indent = 2 if getattr(options, "pretty_print", True) else None
            json_str = json.dumps(output, indent=indent, ensure_ascii=False)

            if options.anonymize_user:
                json_str = self._anonymize_content(json_str)

            return ExportResult(
                success=True,
                content=json_str.encode("utf-8"),
                mime_type=self.mime_type,
            )
        except Exception as e:
            return ExportResult(success=False, error=str(e))

    def _get_entity_type(self, entity: ExportableEntity) -> EntityType:
        """Determine entity type from instance."""
        if isinstance(entity, ExportableConversation):
            return EntityType.CONVERSATION
        elif isinstance(entity, ExportableMessage):
            return EntityType.MESSAGE
        elif isinstance(entity, ExportableRAGRun):
            return EntityType.RAG_RUN
        elif isinstance(entity, ExportableEvaluationReport):
            return EntityType.EVALUATION_REPORT
        else:
            raise ValueError(f"Unknown entity type: {type(entity)}")

    def _entity_to_dict(
        self,
        entity: ExportableEntity,
        options: ExportOptions,
    ) -> dict[str, Any]:
        """Convert entity to dictionary with options applied."""

        def json_serializer(obj: Any) -> Any:
            """Custom serializer for non-JSON types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        # Convert dataclass to dict
        data = asdict(entity)

        # Apply options
        if not options.include_metadata:
            # Remove metadata fields
            metadata_fields = ["id", "created_at", "updated_at", "timestamp", "tenant_id", "metadata"]
            for field in metadata_fields:
                data.pop(field, None)

        if not options.include_citations:
            data.pop("citations", None)
            # Also remove citations from nested messages
            if "messages" in data:
                for msg in data["messages"]:
                    msg.pop("citations", None)

        # Serialize datetime objects
        return json.loads(json.dumps(data, default=json_serializer))
