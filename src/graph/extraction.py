"""Knowledge Foundry — Entity & Relationship Extraction.

Uses Sonnet LLM to extract entities and relationships from document chunks.
Includes entity resolution via fuzzy matching + embedding similarity.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from rapidfuzz import fuzz

from src.core.interfaces import (
    Entity,
    LLMConfig,
    LLMProvider,
    ModelTier,
    Relationship,
)
from src.graph.schemas import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
    RelationshipType,
)

logger = structlog.get_logger(__name__)

# =============================================================
# EXTRACTION PROMPTS
# =============================================================

ENTITY_EXTRACTION_PROMPT = """\
<system>
You are a knowledge graph entity extractor for an enterprise knowledge management system.
Extract named entities from the document chunk below.
Return ONLY valid JSON. Do not include explanations.
</system>

<context>
Document Title: {document_title}
Source System: {source_system}
Content Type: {content_type}
</context>

<chunk>
{chunk_text}
</chunk>

<entity_types>
Extract these entity types:
- Person: {{ name, role, team, expertise_areas[] }}
- Organization: {{ name, org_type (customer|supplier|partner|regulator), industry }}
- Product: {{ name, version, status (active|deprecated|planning|eol), criticality }}
- Technology: {{ name, category (database|language|framework|cloud|tool), version }}
- Regulation: {{ name, short_name, jurisdiction (EU|US|Global), status }}
- Process: {{ name, description, data_category (PII|financial|public) }}
- Concept: {{ name, category (business|technical|domain), description }}
</entity_types>

<rules>
1. Only extract entities explicitly mentioned in the chunk.
2. Do NOT infer entities not present in the text.
3. Use canonical names (e.g., "PostgreSQL" not "postgres").
4. Include confidence score (0.0-1.0) for each entity.
5. If an entity is ambiguous, set confidence < 0.7.
</rules>

<output_format>
{{
  "entities": [
    {{
      "type": "Technology",
      "name": "PostgreSQL",
      "properties": {{ "category": "database", "version": "16" }},
      "confidence": 0.95,
      "source_span": "We use PostgreSQL 16 for..."
    }}
  ]
}}
</output_format>"""


RELATIONSHIP_EXTRACTION_PROMPT = """\
<system>
You are a knowledge graph relationship extractor. Given a document chunk and
pre-extracted entities, identify relationships between them.
Return ONLY valid JSON. Do not include explanations.
</system>

<context>
Document Title: {document_title}
</context>

<chunk>
{chunk_text}
</chunk>

<entities>
{extracted_entities_json}
</entities>

<relationship_types>
- DEPENDS_ON: X requires Y to function (criticality: critical|high|medium|low)
- COMPLIES_WITH: X must adhere to regulation Y (compliance_status: compliant|partial|non_compliant)
- AFFECTS: Change in X impacts Y (impact_level: high|medium|low)
- MANAGED_BY: X is owned/managed by Y (role: owner|contributor|reviewer)
- USES: Process X uses Technology Y (purpose, criticality)
- SUPPLIED_BY: Component X is provided by Organization Y
- HAS_COMPONENT: Product X contains Component Y (criticality)
- RELATED_TO: Semantic relationship (describe subtype)
- MENTIONS: Document mentions entity
- AUTHORED_BY: Document authored by person
- CITES: Document cites another document
</relationship_types>

<rules>
1. Only extract relationships explicitly stated or strongly implied in the chunk.
2. Both "from" and "to" must be entities in the provided entity list.
3. Include confidence score (0.0-1.0).
4. Include a brief evidence quote from the chunk.
5. Do NOT create relationships between entities that don't interact in this chunk.
</rules>

<output_format>
{{
  "relationships": [
    {{
      "type": "DEPENDS_ON",
      "from": {{ "type": "Product", "name": "Knowledge Foundry" }},
      "to": {{ "type": "Technology", "name": "PostgreSQL" }},
      "properties": {{ "criticality": "high" }},
      "confidence": 0.90,
      "evidence": "Knowledge Foundry requires PostgreSQL 16 for persistent storage"
    }}
  ]
}}
</output_format>"""


# =============================================================
# ENTITY RESOLUTION
# =============================================================


class EntityResolutionConfig:
    """Configuration for entity resolution / deduplication."""

    FUZZY_THRESHOLD: float = 0.85  # Levenshtein ratio
    SAME_TYPE_REQUIRED: bool = True
    MERGE_STRATEGY: str = "highest_confidence"


def resolve_entity(
    new_entity: ExtractedEntity,
    existing_entities: list[ExtractedEntity],
    config: EntityResolutionConfig | None = None,
) -> ExtractedEntity | None:
    """Check if new_entity matches an existing entity.

    Returns the matched existing entity, or None if no match.
    """
    config = config or EntityResolutionConfig()

    for existing in existing_entities:
        # Same-type constraint
        if config.SAME_TYPE_REQUIRED and new_entity.type != existing.type:
            continue

        # Exact match (case-insensitive)
        if new_entity.name.lower().strip() == existing.name.lower().strip():
            return existing

        # Fuzzy match
        ratio = fuzz.ratio(new_entity.name.lower(), existing.name.lower()) / 100.0
        if ratio >= config.FUZZY_THRESHOLD:
            return existing

    return None


def deduplicate_entities(
    entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    """Deduplicate a list of extracted entities."""
    unique: list[ExtractedEntity] = []

    for entity in entities:
        match = resolve_entity(entity, unique)
        if match is None:
            unique.append(entity)
        else:
            # Keep the one with higher confidence
            if entity.confidence > match.confidence:
                idx = unique.index(match)
                unique[idx] = entity

    return unique


# =============================================================
# EXTRACTION ENGINE
# =============================================================


class EntityRelationshipExtractor:
    """Extracts entities and relationships from document chunks using LLM.

    Uses a two-pass approach:
    1. Extract entities from chunk text
    2. Extract relationships given the entities
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    async def extract_from_chunk(
        self,
        chunk_text: str,
        document_title: str = "",
        source_system: str = "manual",
        content_type: str = "documentation",
        document_id: str | None = None,
        chunk_index: int | None = None,
    ) -> ExtractionResult:
        """Extract entities and relationships from a single chunk."""
        # --- Pass 1: Entity extraction ---
        entity_prompt = ENTITY_EXTRACTION_PROMPT.format(
            document_title=document_title,
            source_system=source_system,
            content_type=content_type,
            chunk_text=chunk_text,
        )

        entity_response = await self._llm.generate(
            prompt=entity_prompt,
            config=LLMConfig(
                model="sonnet",
                tier=ModelTier.SONNET,
                temperature=0.1,
                max_tokens=4096,
            ),
        )

        raw_entities = self._parse_entities(entity_response.text)
        entities = deduplicate_entities(raw_entities)

        # --- Pass 2: Relationship extraction ---
        entities_json = json.dumps(
            [{"type": e.type, "name": e.name, "properties": e.properties} for e in entities],
            indent=2,
        )

        rel_prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(
            document_title=document_title,
            chunk_text=chunk_text,
            extracted_entities_json=entities_json,
        )

        rel_response = await self._llm.generate(
            prompt=rel_prompt,
            config=LLMConfig(
                model="sonnet",
                tier=ModelTier.SONNET,
                temperature=0.1,
                max_tokens=4096,
            ),
        )

        relationships = self._parse_relationships(rel_response.text)

        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            document_id=document_id,
            chunk_index=chunk_index,
        )

    async def extract_from_document(
        self,
        chunks: list[str],
        document_title: str = "",
        source_system: str = "manual",
        content_type: str = "documentation",
        document_id: str | None = None,
    ) -> ExtractionResult:
        """Extract from all chunks and merge results."""
        all_entities: list[ExtractedEntity] = []
        all_relationships: list[ExtractedRelationship] = []

        for idx, chunk_text in enumerate(chunks):
            result = await self.extract_from_chunk(
                chunk_text=chunk_text,
                document_title=document_title,
                source_system=source_system,
                content_type=content_type,
                document_id=document_id,
                chunk_index=idx,
            )
            all_entities.extend(result.entities)
            all_relationships.extend(result.relationships)

        # Deduplicate across all chunks
        unique_entities = deduplicate_entities(all_entities)

        return ExtractionResult(
            entities=unique_entities,
            relationships=all_relationships,
            document_id=document_id,
        )

    def to_graph_models(
        self,
        result: ExtractionResult,
        tenant_id: str,
    ) -> tuple[list[Entity], list[Relationship]]:
        """Convert extraction result to graph interface models."""
        from uuid import uuid4

        entity_id_map: dict[str, str] = {}  # (type:name) -> entity_id
        entities: list[Entity] = []

        for e in result.entities:
            key = f"{e.type}:{e.name.lower()}"
            eid = str(uuid4())
            entity_id_map[key] = eid
            entities.append(
                Entity(
                    entity_id=eid,
                    entity_type=e.type,
                    name=e.name,
                    properties={**e.properties, "confidence": e.confidence},
                    tenant_id=tenant_id,
                )
            )

        relationships: list[Relationship] = []
        for r in result.relationships:
            from_key = f"{r.from_type}:{r.from_entity.lower()}"
            to_key = f"{r.to_type}:{r.to_entity.lower()}"
            from_id = entity_id_map.get(from_key)
            to_id = entity_id_map.get(to_key)
            if from_id and to_id:
                relationships.append(
                    Relationship(
                        source_id=from_id,
                        target_id=to_id,
                        relationship_type=r.type,
                        properties={
                            **r.properties,
                            "confidence": r.confidence,
                            "evidence": r.evidence or "",
                        },
                    )
                )

        return entities, relationships

    # ------------------------------------------------------------------
    # JSON Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_entities(text: str) -> list[ExtractedEntity]:
        """Parse LLM entity extraction response into ExtractedEntity list."""
        try:
            data = _extract_json(text)
            raw_entities = data.get("entities", [])
            result: list[ExtractedEntity] = []
            for raw in raw_entities:
                # Validate entity type
                etype = raw.get("type", "")
                valid_types = {t.value for t in EntityType}
                if etype not in valid_types:
                    continue
                result.append(
                    ExtractedEntity(
                        type=etype,
                        name=raw.get("name", ""),
                        properties=raw.get("properties", {}),
                        confidence=float(raw.get("confidence", 0.5)),
                        source_span=raw.get("source_span"),
                    )
                )
            return result
        except Exception as exc:
            logger.warning("extraction.parse_entities.error", error=str(exc))
            return []

    @staticmethod
    def _parse_relationships(text: str) -> list[ExtractedRelationship]:
        """Parse LLM relationship extraction response."""
        try:
            data = _extract_json(text)
            raw_rels = data.get("relationships", [])
            result: list[ExtractedRelationship] = []
            for raw in raw_rels:
                rtype = raw.get("type", "")
                valid_types = {t.value for t in RelationshipType}
                if rtype not in valid_types:
                    rtype = "RELATED_TO"
                from_info = raw.get("from", {})
                to_info = raw.get("to", {})
                result.append(
                    ExtractedRelationship(
                        type=rtype,
                        from_entity=from_info.get("name", ""),
                        from_type=from_info.get("type", ""),
                        to_entity=to_info.get("name", ""),
                        to_type=to_info.get("type", ""),
                        properties=raw.get("properties", {}),
                        confidence=float(raw.get("confidence", 0.5)),
                        evidence=raw.get("evidence"),
                    )
                )
            return result
        except Exception as exc:
            logger.warning("extraction.parse_relationships.error", error=str(exc))
            return []


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON object from LLM response text (handles markdown fences)."""
    # Try to find JSON in code fences
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))

    # Try direct JSON parse
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)

    # Try to find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    return {}
