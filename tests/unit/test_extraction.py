"""Unit tests for Entity & Relationship Extraction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.interfaces import LLMResponse, ModelTier
from src.graph.extraction import (
    EntityRelationshipExtractor,
    EntityResolutionConfig,
    deduplicate_entities,
    resolve_entity,
    _extract_json,
)
from src.graph.schemas import (
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)


# =============================================================
# Fixtures
# =============================================================


@pytest.fixture
def mock_llm():
    """Return a mocked LLMProvider."""
    llm = AsyncMock()

    # Default entity extraction response
    entity_response = LLMResponse(
        text=json.dumps({
            "entities": [
                {
                    "type": "Technology",
                    "name": "PostgreSQL",
                    "properties": {"category": "database", "version": "16"},
                    "confidence": 0.95,
                    "source_span": "We use PostgreSQL 16",
                },
                {
                    "type": "Product",
                    "name": "Knowledge Foundry",
                    "properties": {"status": "active"},
                    "confidence": 0.9,
                    "source_span": "Knowledge Foundry platform",
                },
            ]
        }),
        model="claude-sonnet-4-20250514",
        tier=ModelTier.SONNET,
    )

    # Default relationship extraction response
    rel_response = LLMResponse(
        text=json.dumps({
            "relationships": [
                {
                    "type": "DEPENDS_ON",
                    "from": {"type": "Product", "name": "Knowledge Foundry"},
                    "to": {"type": "Technology", "name": "PostgreSQL"},
                    "properties": {"criticality": "high"},
                    "confidence": 0.9,
                    "evidence": "KF requires PostgreSQL 16",
                },
            ]
        }),
        model="claude-sonnet-4-20250514",
        tier=ModelTier.SONNET,
    )

    llm.generate = AsyncMock(side_effect=[entity_response, rel_response])
    return llm


@pytest.fixture
def extractor(mock_llm):
    """Return an EntityRelationshipExtractor with mocked LLM."""
    return EntityRelationshipExtractor(llm_provider=mock_llm)


# =============================================================
# Tests: JSON parsing
# =============================================================


class TestJsonParsing:
    def test_parse_plain_json(self):
        """Parse plain JSON object."""
        text = '{"entities": [{"type": "Technology", "name": "Neo4j"}]}'
        result = _extract_json(text)
        assert "entities" in result

    def test_parse_fenced_json(self):
        """Parse JSON inside markdown code fences."""
        text = '```json\n{"entities": []}\n```'
        result = _extract_json(text)
        assert "entities" in result

    def test_parse_embedded_json(self):
        """Parse JSON embedded in other text."""
        text = 'Here is the result:\n{"entities": [{"type": "Person", "name": "Alice"}]}\nDone.'
        result = _extract_json(text)
        assert len(result["entities"]) == 1

    def test_parse_empty_returns_empty_dict(self):
        """Non-JSON text returns empty dict."""
        result = _extract_json("no json here")
        assert result == {}


# =============================================================
# Tests: Entity Extraction
# =============================================================


class TestEntityExtraction:
    async def test_extract_entities_basic(self, extractor, mock_llm):
        """Test basic entity extraction from a chunk."""
        result = await extractor.extract_from_chunk(
            chunk_text="We use PostgreSQL 16 for the Knowledge Foundry platform.",
            document_title="Architecture Doc",
        )

        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 2
        assert result.entities[0].name == "PostgreSQL"
        assert result.entities[0].type == "Technology"
        assert result.entities[0].confidence == 0.95

    async def test_extract_relationships(self, extractor, mock_llm):
        """Test relationship extraction."""
        result = await extractor.extract_from_chunk(
            chunk_text="KF requires PostgreSQL 16.",
            document_title="Architecture Doc",
        )

        assert len(result.relationships) == 1
        assert result.relationships[0].type == "DEPENDS_ON"
        assert result.relationships[0].from_entity == "Knowledge Foundry"
        assert result.relationships[0].to_entity == "PostgreSQL"

    async def test_extract_filters_invalid_types(self, mock_llm):
        """Test that invalid entity types are filtered out."""
        mock_llm.generate = AsyncMock(
            side_effect=[
                LLMResponse(
                    text=json.dumps({
                        "entities": [
                            {"type": "InvalidType", "name": "Foo", "confidence": 0.9},
                            {"type": "Technology", "name": "Redis", "confidence": 0.8},
                        ]
                    }),
                    model="sonnet",
                    tier=ModelTier.SONNET,
                ),
                LLMResponse(
                    text=json.dumps({"relationships": []}),
                    model="sonnet",
                    tier=ModelTier.SONNET,
                ),
            ]
        )

        extractor = EntityRelationshipExtractor(llm_provider=mock_llm)
        result = await extractor.extract_from_chunk("test text")

        assert len(result.entities) == 1
        assert result.entities[0].name == "Redis"


# =============================================================
# Tests: Entity Resolution
# =============================================================


class TestEntityResolution:
    def test_exact_match(self):
        """Test exact name match (case-insensitive)."""
        new = ExtractedEntity(type="Technology", name="PostgreSQL", confidence=0.8)
        existing = [
            ExtractedEntity(type="Technology", name="postgresql", confidence=0.9),
        ]

        match = resolve_entity(new, existing)
        assert match is not None
        assert match.name == "postgresql"

    def test_fuzzy_match(self):
        """Test fuzzy string match."""
        new = ExtractedEntity(type="Technology", name="PostgreSQL 16", confidence=0.8)
        existing = [
            ExtractedEntity(type="Technology", name="PostgreSQL", confidence=0.9),
        ]

        match = resolve_entity(new, existing)
        assert match is not None

    def test_no_match_different_type(self):
        """Test that same name but different type doesn't match."""
        new = ExtractedEntity(type="Person", name="Amazon", confidence=0.8)
        existing = [
            ExtractedEntity(type="Organization", name="Amazon", confidence=0.9),
        ]

        match = resolve_entity(new, existing)
        assert match is None

    def test_no_match_no_existing(self):
        """Test with empty existing list."""
        new = ExtractedEntity(type="Technology", name="Redis", confidence=0.8)
        match = resolve_entity(new, [])
        assert match is None

    def test_deduplicate(self):
        """Test deduplication of entity list."""
        entities = [
            ExtractedEntity(type="Technology", name="PostgreSQL", confidence=0.9),
            ExtractedEntity(type="Technology", name="postgresql", confidence=0.7),
            ExtractedEntity(type="Technology", name="Redis", confidence=0.8),
            ExtractedEntity(type="Technology", name="PostgreSQL 16", confidence=0.95),
        ]

        result = deduplicate_entities(entities)

        # PostgreSQL variants should be merged, Redis stays
        assert len(result) == 2
        names = {e.name for e in result}
        assert "Redis" in names

    def test_deduplicate_keeps_highest_confidence(self):
        """Test that dedup keeps the highest confidence entity."""
        entities = [
            ExtractedEntity(type="Technology", name="Neo4j", confidence=0.5),
            ExtractedEntity(type="Technology", name="neo4j", confidence=0.9),
        ]

        result = deduplicate_entities(entities)
        assert len(result) == 1
        assert result[0].confidence == 0.9


# =============================================================
# Tests: to_graph_models
# =============================================================


class TestToGraphModels:
    async def test_convert_to_graph_models(self, extractor):
        """Test conversion of extraction result to graph models."""
        extraction_result = ExtractionResult(
            entities=[
                ExtractedEntity(
                    type="Product",
                    name="Knowledge Foundry",
                    properties={"status": "active"},
                    confidence=0.9,
                ),
                ExtractedEntity(
                    type="Technology",
                    name="PostgreSQL",
                    properties={"category": "database"},
                    confidence=0.95,
                ),
            ],
            relationships=[
                ExtractedRelationship(
                    type="DEPENDS_ON",
                    from_entity="Knowledge Foundry",
                    from_type="Product",
                    to_entity="PostgreSQL",
                    to_type="Technology",
                    confidence=0.9,
                    evidence="KF uses PostgreSQL",
                ),
            ],
        )

        entities, relationships = extractor.to_graph_models(extraction_result, "tenant1")

        assert len(entities) == 2
        assert len(relationships) == 1
        assert entities[0].entity_type == "Product"
        assert entities[0].tenant_id == "tenant1"
        assert relationships[0].relationship_type == "DEPENDS_ON"

    async def test_convert_missing_entity_ref(self, extractor):
        """Test that relationships with missing entity refs are skipped."""
        extraction_result = ExtractionResult(
            entities=[
                ExtractedEntity(type="Product", name="KF", confidence=0.9),
            ],
            relationships=[
                ExtractedRelationship(
                    type="DEPENDS_ON",
                    from_entity="KF",
                    from_type="Product",
                    to_entity="Missing",
                    to_type="Technology",
                    confidence=0.9,
                ),
            ],
        )

        entities, relationships = extractor.to_graph_models(extraction_result, "t1")

        assert len(entities) == 1
        assert len(relationships) == 0  # Skipped (missing target)


# =============================================================
# Tests: extract_from_document
# =============================================================


class TestMultiChunkExtraction:
    async def test_extract_from_document(self, mock_llm):
        """Test multi-chunk extraction with deduplication."""
        # Set up LLM to return same entities for both chunks
        entity_resp = LLMResponse(
            text=json.dumps({
                "entities": [
                    {"type": "Technology", "name": "PostgreSQL", "confidence": 0.9},
                ]
            }),
            model="sonnet",
            tier=ModelTier.SONNET,
        )
        rel_resp = LLMResponse(
            text=json.dumps({"relationships": []}),
            model="sonnet",
            tier=ModelTier.SONNET,
        )

        mock_llm.generate = AsyncMock(
            side_effect=[entity_resp, rel_resp, entity_resp, rel_resp]
        )

        extractor = EntityRelationshipExtractor(llm_provider=mock_llm)
        result = await extractor.extract_from_document(
            chunks=["chunk 1 about PostgreSQL", "chunk 2 also about PostgreSQL"],
            document_title="Test Doc",
        )

        # Should be deduplicated to 1 entity
        assert len(result.entities) == 1
        assert result.entities[0].name == "PostgreSQL"
