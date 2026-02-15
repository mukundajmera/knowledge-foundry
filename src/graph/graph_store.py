"""Knowledge Foundry — Neo4j Graph Store Implementation.

Async Neo4j client implementing the GraphStore interface.
Provides tenant-isolated graph operations, entity CRUD, traversal,
and full-text search.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

import structlog
from neo4j import AsyncGraphDatabase, AsyncDriver

from src.core.config import Neo4jSettings, get_settings
from src.core.interfaces import (
    Entity,
    GraphEntity,
    GraphPath,
    GraphRelationship,
    GraphStore,
    Relationship,
    TraversalResult,
)
from src.graph.schemas import NEO4J_SCHEMA_CYPHER

logger = structlog.get_logger(__name__)


class Neo4jGraphStore(GraphStore):
    """Async Neo4j graph store with tenant isolation.

    All node operations are scoped by ``tenant_id`` property and Cypher
    ``WHERE`` clauses to enforce multi-tenant isolation.
    """

    def __init__(
        self,
        driver: AsyncDriver | None = None,
        settings: Neo4jSettings | None = None,
    ) -> None:
        self._settings = settings or get_settings().neo4j
        self._driver = driver or AsyncGraphDatabase.driver(
            self._settings.bolt_uri,
            auth=(self._settings.user, self._settings.password),
        )
        self._database = self._settings.database

    # ------------------------------------------------------------------
    # GraphStore interface: query
    # ------------------------------------------------------------------

    async def query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """Execute a Cypher query and return records as dicts."""
        params = params or {}
        async with self._driver.session(database=self._database) as session:
            result = await session.run(cypher, params)
            records = await result.data()
        return records

    # ------------------------------------------------------------------
    # GraphStore interface: add_entities
    # ------------------------------------------------------------------

    async def add_entities(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Add entities and relationships via MERGE (upsert)."""
        async with self._driver.session(database=self._database) as session:
            # Upsert entities
            for entity in entities:
                entity_id = entity.entity_id or str(uuid4())
                cypher = (
                    f"MERGE (n:{entity.entity_type} {{id: $id}}) "
                    f"SET n.name = $name, n.tenant_id = $tenant_id, "
                    f"n += $props"
                )
                await session.run(
                    cypher,
                    {
                        "id": entity_id,
                        "name": entity.name,
                        "tenant_id": entity.tenant_id or "",
                        "props": entity.properties,
                    },
                )

            # Upsert relationships
            for rel in relationships:
                cypher = (
                    "MATCH (a {id: $source_id}), (b {id: $target_id}) "
                    f"MERGE (a)-[r:{rel.relationship_type}]->(b) "
                    "SET r += $props"
                )
                await session.run(
                    cypher,
                    {
                        "source_id": rel.source_id,
                        "target_id": rel.target_id,
                        "props": rel.properties,
                    },
                )

        logger.info(
            "graph.add_entities",
            entities=len(entities),
            relationships=len(relationships),
        )

    # ------------------------------------------------------------------
    # GraphStore interface: search_entities
    # ------------------------------------------------------------------

    async def search_entities(
        self,
        query: str,
        tenant_id: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[GraphEntity]:
        """Search entities by name using CONTAINS (full-text fallback).

        If entity_types is provided, only nodes with those labels are returned.
        """
        if entity_types:
            # Build a UNION query across requested types
            parts: list[str] = []
            for etype in entity_types:
                parts.append(
                    f"MATCH (n:{etype}) WHERE n.tenant_id = $tenant_id "
                    f"AND toLower(n.name) CONTAINS toLower($query) "
                    f"RETURN n.id AS id, labels(n)[0] AS type, n.name AS name, "
                    f"properties(n) AS props, n.tenant_id AS tenant_id, "
                    f"n.pagerank_score AS centrality"
                )
            cypher = " UNION ALL ".join(parts) + f" LIMIT {limit}"
        else:
            cypher = (
                "MATCH (n) WHERE n.tenant_id = $tenant_id "
                "AND n.name IS NOT NULL "
                "AND toLower(n.name) CONTAINS toLower($query) "
                "RETURN n.id AS id, labels(n)[0] AS type, n.name AS name, "
                "properties(n) AS props, n.tenant_id AS tenant_id, "
                "n.pagerank_score AS centrality "
                f"LIMIT {limit}"
            )

        records = await self.query(cypher, {"tenant_id": tenant_id, "query": query})

        return [
            GraphEntity(
                id=str(r["id"]),
                type=r.get("type", "Unknown"),
                name=r.get("name", ""),
                properties=r.get("props", {}),
                tenant_id=r.get("tenant_id"),
                centrality_score=r.get("centrality"),
            )
            for r in records
        ]

    # ------------------------------------------------------------------
    # GraphStore interface: traverse
    # ------------------------------------------------------------------

    async def traverse(
        self,
        entry_entity_ids: list[str],
        tenant_id: str,
        max_hops: int = 2,
        relationship_types: list[str] | None = None,
        entity_types: list[str] | None = None,
        min_confidence: float = 0.5,
        max_results: int = 50,
    ) -> TraversalResult:
        """Traverse graph from entry entities up to max_hops depth."""
        start_time = time.perf_counter()

        # Build relationship filter
        rel_filter = ""
        if relationship_types:
            rel_names = "|".join(relationship_types)
            rel_filter = f":{rel_names}"

        # Build traversal Cypher — variable-length path
        cypher = (
            f"MATCH path = (start)-[r{rel_filter}*1..{max_hops}]-(end) "
            f"WHERE start.id IN $entry_ids AND start.tenant_id = $tenant_id "
            f"AND end.tenant_id = $tenant_id "
            f"UNWIND relationships(path) AS rel "
            f"WITH path, start, end, rel, "
            f"CASE WHEN rel.confidence IS NOT NULL THEN rel.confidence ELSE 1.0 END AS conf "
            f"WHERE conf >= $min_confidence "
            f"RETURN DISTINCT "
            f"end.id AS end_id, labels(end)[0] AS end_type, end.name AS end_name, "
            f"properties(end) AS end_props, "
            f"type(rel) AS rel_type, startNode(rel).id AS rel_from, endNode(rel).id AS rel_to, "
            f"properties(rel) AS rel_props, conf AS confidence, "
            f"length(path) AS depth "
            f"ORDER BY depth, conf DESC "
            f"LIMIT {max_results}"
        )

        records = await self.query(
            cypher,
            {
                "entry_ids": entry_entity_ids,
                "tenant_id": tenant_id,
                "min_confidence": min_confidence,
            },
        )

        # Parse results
        entities_map: dict[str, GraphEntity] = {}
        rels: list[GraphRelationship] = []
        connected_doc_ids: set[str] = set()
        max_depth = 0

        for r in records:
            entity_id = str(r["end_id"])
            entity_type = r.get("end_type", "Unknown")

            if entity_types and entity_type not in entity_types:
                continue

            if entity_id not in entities_map:
                entities_map[entity_id] = GraphEntity(
                    id=entity_id,
                    type=entity_type,
                    name=r.get("end_name", ""),
                    properties=r.get("end_props", {}),
                    tenant_id=tenant_id,
                )

            rels.append(
                GraphRelationship(
                    type=r.get("rel_type", "RELATED_TO"),
                    from_entity_id=str(r.get("rel_from", "")),
                    to_entity_id=str(r.get("rel_to", "")),
                    properties=r.get("rel_props", {}),
                    confidence=r.get("confidence", 1.0),
                )
            )

            # Collect connected document IDs
            if entity_type == "Document":
                connected_doc_ids.add(entity_id)

            depth = r.get("depth", 0)
            if depth > max_depth:
                max_depth = depth

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return TraversalResult(
            entities=list(entities_map.values()),
            relationships=rels,
            paths=[],  # Full path extraction is expensive; omitted for now
            connected_document_ids=list(connected_doc_ids),
            traversal_depth_reached=max_depth,
            nodes_explored=len(entities_map),
            latency_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------
    # GraphStore interface: ensure_indices
    # ------------------------------------------------------------------

    async def ensure_indices(self) -> None:
        """Create constraints and indices if they don't exist."""
        async with self._driver.session(database=self._database) as session:
            for statement in NEO4J_SCHEMA_CYPHER:
                try:
                    await session.run(statement)
                except Exception as exc:
                    logger.warning(
                        "graph.ensure_indices.skip",
                        statement=statement[:80],
                        error=str(exc),
                    )
        logger.info("graph.ensure_indices.done", count=len(NEO4J_SCHEMA_CYPHER))

    # ------------------------------------------------------------------
    # GraphStore interface: close
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the Neo4j driver connection."""
        await self._driver.close()
        logger.info("graph.close")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Verify Neo4j connectivity."""
        try:
            await self.query("RETURN 1 AS ok")
            return True
        except Exception:
            return False
