# Export System

The Knowledge Foundry Export System provides a pluggable architecture for exporting conversations, messages, RAG runs, and evaluation reports to multiple formats.

## Overview

The export system allows users to download their data in various formats:

| Format | Extension | MIME Type | Description |
|--------|-----------|-----------|-------------|
| Markdown | `.md` | `text/markdown` | Formatted markdown document |
| HTML | `.html` | `text/html` | Styled HTML document |
| PDF | `.pdf` | `application/pdf` | PDF document (requires weasyprint) |
| DOCX | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Microsoft Word document (requires python-docx) |
| JSON | `.json` | `application/json` | Structured JSON data |
| Plain Text | `.txt` | `text/plain` | Simple text format |

## Supported Entity Types

- **Conversation**: Full chat sessions with all messages
- **Message**: Individual user or assistant messages
- **RAG Run**: Query results including retrieved context and citations
- **Evaluation Report**: Model evaluation metrics and examples

## API Endpoints

### List Available Formats

```http
GET /v1/export/formats?entity_type=conversation
```

**Response:**
```json
{
  "formats": [
    {
      "format_id": "markdown",
      "label": "Markdown",
      "description": "Export as a formatted Markdown document (.md)",
      "mime_type": "text/markdown",
      "extension": ".md",
      "supported_entity_types": ["conversation", "message", "rag_run", "evaluation_report"],
      "options_schema": {...}
    }
  ]
}
```

### Generate Export

```http
POST /v1/export/generate
Content-Type: application/json

{
  "entity_type": "conversation",
  "entity_id": "conv_001",
  "format_id": "markdown",
  "options": {
    "include_metadata": true,
    "include_citations": true,
    "anonymize_user": false
  },
  "entity_data": {
    "id": "conv_001",
    "title": "My Conversation",
    "messages": [...]
  }
}
```

**Response:** Binary file download with appropriate Content-Type header.

### Get Format Details

```http
GET /v1/export/formats/{format_id}
```

Returns detailed information about a specific export format.

## Export Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `include_metadata` | boolean | `true` | Include timestamps, IDs, and other metadata |
| `include_citations` | boolean | `true` | Include source citations in export |
| `anonymize_user` | boolean | `false` | Mask user identifiers (emails, user IDs) |
| `include_raw_json_appendix` | boolean | `false` | Append raw JSON data at end (Markdown only) |
| `locale` | string | `"en-US"` | Locale for date/time formatting |

## Using the Export UI

### Exporting a Conversation

1. Open a conversation with messages
2. Click the **📥 Export Conversation** button at the top of the messages area
3. Select your desired format from the format grid
4. Adjust export options as needed
5. Click **Export** to download

### Exporting a Single Message

1. Locate an AI assistant message
2. Click the **📥 Export** button in the message actions
3. Select your format and options
4. Click **Export** to download

## Adding New Exporters

The export system uses a pluggable architecture. To add a new exporter:

### 1. Create the Exporter Class

Create a new file in `src/export/exporters/`:

```python
# src/export/exporters/csv.py
from src.export.base import BaseExporter, ExportableEntity
from src.export.models import (
    EntityType,
    ExportableConversation,
    ExportContext,
    ExportOptions,
    ExportResult,
)

class CSVExporter(BaseExporter):
    @property
    def format_id(self) -> str:
        return "csv"

    @property
    def label(self) -> str:
        return "CSV"

    @property
    def description(self) -> str:
        return "Export as comma-separated values (.csv)"

    @property
    def mime_type(self) -> str:
        return "text/csv"

    @property
    def extension(self) -> str:
        return ".csv"

    @property
    def supported_entity_types(self) -> list[EntityType]:
        return [EntityType.CONVERSATION, EntityType.EVALUATION_REPORT]

    def generate(
        self,
        entity: ExportableEntity,
        options: ExportOptions,
        context: ExportContext,
    ) -> ExportResult:
        # Implementation here
        ...
```

### 2. Register the Exporter

Update `src/export/registry.py`:

```python
def get_export_registry() -> ExportRegistry:
    global _registry

    if _registry is None:
        _registry = ExportRegistry()

        # ... existing exporters ...
        from src.export.exporters.csv import CSVExporter
        _registry.register(CSVExporter())

    return _registry
```

### 3. Update Package Exports (Optional)

If you want the exporter to be importable from the package:

```python
# src/export/exporters/__init__.py
from src.export.exporters.csv import CSVExporter

__all__ = [
    # ... existing exports ...
    "CSVExporter",
]
```

### 4. Add Tests

Create tests for your new exporter in `tests/unit/test_export.py`:

```python
class TestCSVExporter:
    def test_format_id(self):
        exporter = CSVExporter()
        assert exporter.format_id == "csv"
        assert exporter.extension == ".csv"

    def test_export_conversation(self, sample_conversation, default_options, default_context):
        exporter = CSVExporter()
        result = exporter.generate(sample_conversation, default_options, default_context)
        assert result.success is True
        # Add more assertions
```

## Security Considerations

### Access Control

- Exports respect the existing access control model
- Users can only export entities they have permission to view
- All export operations are logged in the audit trail

### Data Privacy

- Use `anonymize_user: true` to mask email addresses and user IDs
- PII redaction patterns:
  - Email addresses → `[REDACTED_EMAIL]`
  - User IDs → `[REDACTED_USER_ID]`

### Audit Logging

Each export operation logs:
- User ID and tenant ID
- Entity type and ID
- Export format
- Timestamp
- Result (success/failure)
- File size and generation time

## Performance

### Size Limits

- Exports are generated synchronously for small entities
- Consider pagination for very large conversations
- The system includes reasonable timeouts

### Best Practices

- Use JSON format for programmatic access
- Use Markdown or HTML for human-readable exports
- Use PDF for formal documentation

## Troubleshooting

### PDF Export Not Available

PDF generation requires weasyprint:
```bash
pip install weasyprint
```

### DOCX Export Not Available

DOCX generation requires python-docx:
```bash
pip install python-docx
```

### Export Times Out

For very large exports:
1. Try exporting fewer messages
2. Use JSON format (fastest)
3. Disable `include_raw_json_appendix`

### Malformed Export Content

1. Check that entity data is complete
2. Verify timestamps are valid (milliseconds since epoch for frontend data)
3. Check the server logs for detailed error messages
