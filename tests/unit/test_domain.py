"""Tests for src.core.domain — Knowledge Foundry domain entities."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.core.domain import (
    ChunkingStrategy,
    ClientApp,
    Connector,
    ConnectorType,
    Index,
    IndexType,
    IngestionEvent,
    IngestionJob,
    IngestionJobStatus,
    KnowledgeBase,
    Policy,
    PolicyType,
    Source,
    SourceStatus,
)


class TestConnector:
    """Tests for the Connector entity."""

    def test_create_connector(self) -> None:
        c = Connector(name="git-connector", connector_type=ConnectorType.GIT_REPO)
        assert c.name == "git-connector"
        assert c.connector_type == ConnectorType.GIT_REPO
        assert c.enabled is True
        assert isinstance(c.connector_id, UUID)

    def test_connector_with_config(self) -> None:
        c = Connector(
            name="s3-conn",
            connector_type=ConnectorType.S3_BUCKET,
            config={"bucket": "my-bucket", "region": "us-east-1"},
        )
        assert c.config["bucket"] == "my-bucket"
        assert c.credentials_ref is None

    def test_all_connector_types(self) -> None:
        for ct in ConnectorType:
            c = Connector(name=f"test-{ct.value}", connector_type=ct)
            assert c.connector_type == ct


class TestSource:
    """Tests for the Source entity."""

    def test_create_source(self) -> None:
        kb_id = uuid4()
        conn_id = uuid4()
        s = Source(
            knowledge_base_id=kb_id,
            connector_id=conn_id,
            name="my-source",
            location="/data/docs",
        )
        assert s.knowledge_base_id == kb_id
        assert s.status == SourceStatus.PENDING
        assert s.document_count == 0

    def test_source_with_file_patterns(self) -> None:
        s = Source(
            knowledge_base_id=uuid4(),
            connector_id=uuid4(),
            name="md-source",
            location="/repo",
            file_patterns=["*.md", "*.txt"],
        )
        assert len(s.file_patterns) == 2


class TestIngestionJob:
    """Tests for the IngestionJob entity."""

    def test_create_job(self) -> None:
        job = IngestionJob(
            source_id=uuid4(),
            knowledge_base_id=uuid4(),
        )
        assert job.status == IngestionJobStatus.QUEUED
        assert job.documents_processed == 0
        assert job.chunks_created == 0

    def test_job_statuses(self) -> None:
        for status in IngestionJobStatus:
            job = IngestionJob(
                source_id=uuid4(),
                knowledge_base_id=uuid4(),
                status=status,
            )
            assert job.status == status


class TestIndex:
    """Tests for the Index entity."""

    def test_create_vector_index(self) -> None:
        idx = Index(
            knowledge_base_id=uuid4(),
            name="vec-idx",
            index_type=IndexType.VECTOR,
        )
        assert idx.index_type == IndexType.VECTOR
        assert idx.dimensions == 3072
        assert idx.distance_metric == "cosine"

    def test_create_hybrid_index(self) -> None:
        idx = Index(
            knowledge_base_id=uuid4(),
            name="hybrid-idx",
            index_type=IndexType.HYBRID,
            chunk_size=256,
            chunk_overlap=32,
        )
        assert idx.index_type == IndexType.HYBRID
        assert idx.chunk_size == 256
        assert idx.chunk_overlap == 32


class TestPolicy:
    """Tests for the Policy entity."""

    def test_create_policy(self) -> None:
        p = Policy(
            knowledge_base_id=uuid4(),
            name="data-retention",
            policy_type=PolicyType.DATA_RETENTION,
            rules={"retention_days": 365},
        )
        assert p.policy_type == PolicyType.DATA_RETENTION
        assert p.rules["retention_days"] == 365
        assert p.enabled is True


class TestClientApp:
    """Tests for the ClientApp entity."""

    def test_create_client(self) -> None:
        client = ClientApp(name="my-agent")
        assert client.name == "my-agent"
        assert client.rate_limit_rpm == 60
        assert client.enabled is True
        assert client.allowed_knowledge_base_ids == []

    def test_client_with_kb_restriction(self) -> None:
        kb_id = uuid4()
        client = ClientApp(
            name="restricted-agent",
            allowed_knowledge_base_ids=[kb_id],
            rate_limit_rpm=30,
        )
        assert len(client.allowed_knowledge_base_ids) == 1
        assert client.rate_limit_rpm == 30


class TestKnowledgeBase:
    """Tests for the KnowledgeBase entity."""

    def test_create_knowledge_base(self) -> None:
        kb = KnowledgeBase(
            tenant_id=uuid4(),
            name="Engineering Docs",
            description="Internal engineering documentation",
        )
        assert kb.name == "Engineering Docs"
        assert kb.chunking_strategy == ChunkingStrategy.SEMANTIC
        assert kb.sources == []
        assert kb.indices == []
        assert kb.policies == []

    def test_kb_with_sources_and_indices(self) -> None:
        kb_id = uuid4()
        kb = KnowledgeBase(
            kb_id=kb_id,
            tenant_id=uuid4(),
            name="Full KB",
            tags=["engineering", "docs"],
        )
        source = Source(
            knowledge_base_id=kb_id,
            connector_id=uuid4(),
            name="src1",
            location="/data",
        )
        index = Index(
            knowledge_base_id=kb_id,
            name="idx1",
            index_type=IndexType.HYBRID,
        )
        kb.sources.append(source)
        kb.indices.append(index)

        assert len(kb.sources) == 1
        assert len(kb.indices) == 1
        assert kb.tags == ["engineering", "docs"]

    def test_kb_serialization(self) -> None:
        kb = KnowledgeBase(
            tenant_id=uuid4(),
            name="Test KB",
        )
        data = kb.model_dump(mode="json")
        assert "kb_id" in data
        assert data["name"] == "Test KB"
        assert data["chunking_strategy"] == "semantic"


class TestIngestionEvent:
    """Tests for the IngestionEvent entity."""

    def test_create_event(self) -> None:
        event = IngestionEvent(
            job_id=uuid4(),
            event_type="document_discovered",
            data={"path": "/docs/readme.md"},
        )
        assert event.event_type == "document_discovered"
        assert event.data["path"] == "/docs/readme.md"
        assert event.error is None
