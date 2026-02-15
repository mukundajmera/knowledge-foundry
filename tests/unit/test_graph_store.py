"""Unit tests for Neo4j Graph Store."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.core.interfaces import (
    Entity,
    GraphEntity,
    GraphRelationship,
    Relationship,
    TraversalResult,
)


# =============================================================
# Fixtures
# =============================================================


@pytest.fixture
def mock_neo4j_settings():
    """Return a mock Neo4jSettings."""
    settings = MagicMock()
    settings.bolt_uri = "bolt://localhost:7687"
    settings.user = "neo4j"
    settings.password = "test"
    settings.database = "neo4j"
    return settings


@pytest.fixture
def mock_driver():
    """Return a mock AsyncDriver."""
    driver = AsyncMock()
    session = AsyncMock()
    result = AsyncMock()
    result.data = AsyncMock(return_value=[])

    session.run = AsyncMock(return_value=result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    driver.session = MagicMock(return_value=session)
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def graph_store(mock_driver, mock_neo4j_settings):
    """Return a Neo4jGraphStore instance with mocked driver."""
    from src.graph.graph_store import Neo4jGraphStore

    store = Neo4jGraphStore(driver=mock_driver, settings=mock_neo4j_settings)
    return store


# =============================================================
# Tests: query
# =============================================================


class TestNeo4jQuery:
    async def test_query_basic(self, graph_store, mock_driver):
        """Test basic Cypher query execution."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[{"count": 42}])
        session.run = AsyncMock(return_value=result_mock)

        records = await graph_store.query("RETURN 42 AS count")

        assert len(records) == 1
        assert records[0]["count"] == 42
        session.run.assert_called_once()

    async def test_query_with_params(self, graph_store, mock_driver):
        """Test Cypher query with parameters."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[{"name": "test"}])
        session.run = AsyncMock(return_value=result_mock)

        await graph_store.query(
            "MATCH (n) WHERE n.name = $name RETURN n",
            {"name": "test"},
        )

        session.run.assert_called_once_with(
            "MATCH (n) WHERE n.name = $name RETURN n",
            {"name": "test"},
        )


# =============================================================
# Tests: add_entities
# =============================================================


class TestAddEntities:
    async def test_add_single_entity(self, graph_store, mock_driver):
        """Test adding a single entity."""
        session = mock_driver.session.return_value

        entities = [
            Entity(
                entity_id="e1",
                entity_type="Technology",
                name="PostgreSQL",
                properties={"version": "16"},
                tenant_id="tenant1",
            )
        ]

        await graph_store.add_entities(entities, [])

        assert session.run.call_count >= 1

    async def test_add_entity_with_relationship(self, graph_store, mock_driver):
        """Test adding entities with relationships."""
        session = mock_driver.session.return_value

        entities = [
            Entity(entity_id="e1", entity_type="Product", name="KF", tenant_id="t1"),
            Entity(entity_id="e2", entity_type="Technology", name="Neo4j", tenant_id="t1"),
        ]
        relationships = [
            Relationship(
                source_id="e1",
                target_id="e2",
                relationship_type="DEPENDS_ON",
                properties={"criticality": "high"},
            )
        ]

        await graph_store.add_entities(entities, relationships)

        # 2 entity merges + 1 relationship merge
        assert session.run.call_count >= 3


# =============================================================
# Tests: search_entities
# =============================================================


class TestSearchEntities:
    async def test_search_basic(self, graph_store, mock_driver):
        """Test basic entity search."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(
            return_value=[
                {
                    "id": "e1",
                    "type": "Technology",
                    "name": "PostgreSQL",
                    "props": {"version": "16"},
                    "tenant_id": "t1",
                    "centrality": 0.5,
                }
            ]
        )
        session.run = AsyncMock(return_value=result_mock)

        results = await graph_store.search_entities("Postgres", "t1")

        assert len(results) == 1
        assert results[0].name == "PostgreSQL"
        assert results[0].type == "Technology"

    async def test_search_with_entity_types(self, graph_store, mock_driver):
        """Test search filtered by entity types."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[])
        session.run = AsyncMock(return_value=result_mock)

        await graph_store.search_entities(
            "test",
            "t1",
            entity_types=["Product", "Technology"],
        )

        session.run.assert_called_once()
        call_args = session.run.call_args
        # UNION ALL query should be produced
        assert "UNION ALL" in call_args[0][0]

    async def test_search_empty(self, graph_store, mock_driver):
        """Test search with no results."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[])
        session.run = AsyncMock(return_value=result_mock)

        results = await graph_store.search_entities("nonexistent", "t1")

        assert len(results) == 0


# =============================================================
# Tests: traverse
# =============================================================


class TestTraverse:
    async def test_traverse_basic(self, graph_store, mock_driver):
        """Test basic graph traversal."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(
            return_value=[
                {
                    "end_id": "e2",
                    "end_type": "Technology",
                    "end_name": "Neo4j",
                    "end_props": {},
                    "rel_type": "DEPENDS_ON",
                    "rel_from": "e1",
                    "rel_to": "e2",
                    "rel_props": {"criticality": "high"},
                    "confidence": 0.9,
                    "depth": 1,
                },
            ]
        )
        session.run = AsyncMock(return_value=result_mock)

        result = await graph_store.traverse(["e1"], "t1", max_hops=2)

        assert isinstance(result, TraversalResult)
        assert len(result.entities) == 1
        assert result.entities[0].name == "Neo4j"
        assert len(result.relationships) == 1
        assert result.relationships[0].type == "DEPENDS_ON"
        assert result.traversal_depth_reached == 1

    async def test_traverse_with_rel_filter(self, graph_store, mock_driver):
        """Test traversal with relationship type filter."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[])
        session.run = AsyncMock(return_value=result_mock)

        await graph_store.traverse(
            ["e1"],
            "t1",
            relationship_types=["DEPENDS_ON", "AFFECTS"],
        )

        call_args = session.run.call_args
        cypher = call_args[0][0]
        assert "DEPENDS_ON|AFFECTS" in cypher

    async def test_traverse_empty(self, graph_store, mock_driver):
        """Test traversal with no results."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[])
        session.run = AsyncMock(return_value=result_mock)

        result = await graph_store.traverse(["e1"], "t1")

        assert len(result.entities) == 0
        assert len(result.relationships) == 0
        assert result.traversal_depth_reached == 0

    async def test_traverse_collects_document_ids(self, graph_store, mock_driver):
        """Test that traversal collects connected document IDs."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(
            return_value=[
                {
                    "end_id": "doc1",
                    "end_type": "Document",
                    "end_name": "Architecture Spec",
                    "end_props": {},
                    "rel_type": "MENTIONS",
                    "rel_from": "e1",
                    "rel_to": "doc1",
                    "rel_props": {},
                    "confidence": 0.8,
                    "depth": 1,
                },
            ]
        )
        session.run = AsyncMock(return_value=result_mock)

        result = await graph_store.traverse(["e1"], "t1")

        assert "doc1" in result.connected_document_ids


# =============================================================
# Tests: ensure_indices
# =============================================================


class TestEnsureIndices:
    async def test_ensure_indices(self, graph_store, mock_driver):
        """Test that all schema statements are executed."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[])
        session.run = AsyncMock(return_value=result_mock)

        from src.graph.schemas import NEO4J_SCHEMA_CYPHER

        await graph_store.ensure_indices()

        assert session.run.call_count == len(NEO4J_SCHEMA_CYPHER)

    async def test_ensure_indices_tolerates_errors(self, graph_store, mock_driver):
        """Test that individual statement failures don't crash."""
        session = mock_driver.session.return_value
        session.run = AsyncMock(side_effect=Exception("Already exists"))

        # Should not raise
        await graph_store.ensure_indices()


# =============================================================
# Tests: close and health_check
# =============================================================


class TestLifecycle:
    async def test_close(self, graph_store, mock_driver):
        """Test driver close."""
        await graph_store.close()
        mock_driver.close.assert_called_once()

    async def test_health_check_ok(self, graph_store, mock_driver):
        """Test health check success."""
        session = mock_driver.session.return_value
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[{"ok": 1}])
        session.run = AsyncMock(return_value=result_mock)

        assert await graph_store.health_check() is True

    async def test_health_check_fail(self, graph_store, mock_driver):
        """Test health check failure."""
        session = mock_driver.session.return_value
        session.run = AsyncMock(side_effect=Exception("Connection refused"))

        assert await graph_store.health_check() is False
