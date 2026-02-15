"""Knowledge Foundry — Graph Schema Models.

Pydantic models for all 13 entity types and 16 relationship types
defined in Phase 1.3 spec §2.1–2.2.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================
# ENTITY TYPE ENUM
# =============================================================


class EntityType(str, Enum):
    """Supported knowledge graph entity types."""

    DOCUMENT = "Document"
    CONCEPT = "Concept"
    PERSON = "Person"
    ORGANIZATION = "Organization"
    PRODUCT = "Product"
    PROCESS = "Process"
    REGULATION = "Regulation"
    TECHNOLOGY = "Technology"
    TEAM = "Team"
    COMPONENT = "Component"
    TICKET = "Ticket"
    DECISION = "Decision"
    RISK = "Risk"


# =============================================================
# RELATIONSHIP TYPE ENUM
# =============================================================


class RelationshipType(str, Enum):
    """Supported knowledge graph relationship types."""

    MENTIONS = "MENTIONS"
    AUTHORED_BY = "AUTHORED_BY"
    DEPENDS_ON = "DEPENDS_ON"
    COMPLIES_WITH = "COMPLIES_WITH"
    AFFECTS = "AFFECTS"
    HAS_COMPONENT = "HAS_COMPONENT"
    SUPPLIED_BY = "SUPPLIED_BY"
    MANAGED_BY = "MANAGED_BY"
    MEMBER_OF = "MEMBER_OF"
    RELATED_TO = "RELATED_TO"
    MITIGATES = "MITIGATES"
    SUPERSEDES = "SUPERSEDES"
    CITES = "CITES"
    USES = "USES"
    REPORTS_TO = "REPORTS_TO"
    IMPACTS = "IMPACTS"


# =============================================================
# ENTITY NODE SCHEMAS — used for validation during extraction
# =============================================================


class DocumentNode(BaseModel):
    """Represents a source document in the knowledge graph."""

    id: UUID
    tenant_id: UUID
    title: str
    source_system: str  # confluence, sharepoint, github, etc.
    source_url: str | None = None
    content_type: str  # policy, architecture, code, ticket
    content_hash: str  # SHA-256 for change detection
    created_date: datetime | None = None
    updated_date: datetime | None = None
    author_id: str | None = None
    is_skeleton: bool = False  # In KET-RAG skeleton set
    pagerank_score: float = 0.0  # Centrality score
    labels: list[str] = Field(default_factory=lambda: ["Document"])


class ConceptNode(BaseModel):
    """Abstract concept extracted from documents."""

    id: UUID
    tenant_id: UUID
    name: str  # Canonical name
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    category: str  # technology, business, process, domain


class PersonNode(BaseModel):
    """Person entity (PII-aware)."""

    id: UUID
    tenant_id: UUID
    name_hash: str  # Hashed for GDPR
    display_name: str  # Can be pseudonymized
    role: str | None = None
    team_id: str | None = None
    expertise_areas: list[str] = Field(default_factory=list)
    document_count: int = 0


class OrganizationNode(BaseModel):
    """External organization (customer, supplier, partner)."""

    id: UUID
    tenant_id: UUID
    name: str
    org_type: Literal["customer", "supplier", "partner", "regulator"]
    industry: str | None = None
    tier: Literal["platinum", "gold", "silver", "bronze"] | None = None
    active: bool = True


class ProductNode(BaseModel):
    """Product, service, or software component."""

    id: UUID
    tenant_id: UUID
    name: str
    version: str | None = None
    status: Literal["active", "deprecated", "planning", "eol"]
    owner_team_id: str | None = None
    criticality: Literal["critical", "high", "medium", "low"]


class ProcessNode(BaseModel):
    """Business process or workflow."""

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None = None
    owner_id: str | None = None
    data_category: str | None = None  # PII, financial, public
    automation_level: str | None = None  # manual, semi-auto, auto


class RegulationNode(BaseModel):
    """Regulation, policy, or compliance standard."""

    id: UUID
    tenant_id: UUID
    name: str
    short_name: str | None = None  # e.g., "GDPR", "SOX"
    jurisdiction: str  # EU, US, Global
    effective_date: datetime | None = None
    review_date: datetime | None = None
    status: Literal["active", "draft", "superseded"]


class TechnologyNode(BaseModel):
    """Technology, tool, or platform."""

    id: UUID
    tenant_id: UUID
    name: str
    category: str  # database, language, framework, cloud
    version: str | None = None
    eol_date: datetime | None = None
    status: Literal["supported", "deprecated", "eol", "evaluating"]


class TeamNode(BaseModel):
    """Organizational team."""

    id: UUID
    tenant_id: UUID
    name: str
    department: str | None = None
    member_count: int = 0
    lead_id: str | None = None


class ComponentNode(BaseModel):
    """Sub-component of a product."""

    id: UUID
    tenant_id: UUID
    name: str
    component_type: str  # library, service, module
    parent_product_id: str | None = None


class RiskNode(BaseModel):
    """Identified risk."""

    id: UUID
    tenant_id: UUID
    title: str
    severity: Literal["critical", "high", "medium", "low"]
    likelihood: Literal["almost_certain", "likely", "possible", "unlikely", "rare"]
    mitigation_status: Literal["open", "mitigated", "accepted", "closed"]


# =============================================================
# EXTRACTION MODELS — used by the LLM extraction pipeline
# =============================================================


class ExtractedEntity(BaseModel):
    """An entity extracted from a document chunk by the LLM."""

    type: str  # EntityType value
    name: str
    properties: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source_span: str | None = None  # Original text span


class ExtractedRelationship(BaseModel):
    """A relationship extracted from a document chunk by the LLM."""

    type: str  # RelationshipType value
    from_entity: str  # Entity name
    from_type: str  # Entity type
    to_entity: str  # Entity name
    to_type: str  # Entity type
    properties: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = None  # Supporting text


class ExtractionResult(BaseModel):
    """Combined result from entity/relationship extraction."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    document_id: str | None = None
    chunk_index: int | None = None


# =============================================================
# SCHEMA REGISTRY — maps entity types to their node models
# =============================================================

ENTITY_TYPE_MAP: dict[str, type[BaseModel]] = {
    EntityType.DOCUMENT: DocumentNode,
    EntityType.CONCEPT: ConceptNode,
    EntityType.PERSON: PersonNode,
    EntityType.ORGANIZATION: OrganizationNode,
    EntityType.PRODUCT: ProductNode,
    EntityType.PROCESS: ProcessNode,
    EntityType.REGULATION: RegulationNode,
    EntityType.TECHNOLOGY: TechnologyNode,
    EntityType.TEAM: TeamNode,
    EntityType.COMPONENT: ComponentNode,
    EntityType.RISK: RiskNode,
}

# Neo4j constraints and indices — executed during ensure_indices()
NEO4J_SCHEMA_CYPHER: list[str] = [
    # Uniqueness constraints
    "CREATE CONSTRAINT doc_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT concept_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT person_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT org_unique IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT product_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT process_unique IF NOT EXISTS FOR (p:Process) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT reg_unique IF NOT EXISTS FOR (r:Regulation) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT tech_unique IF NOT EXISTS FOR (t:Technology) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT team_unique IF NOT EXISTS FOR (t:Team) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT component_unique IF NOT EXISTS FOR (c:Component) REQUIRE c.id IS UNIQUE",
    # Performance indices
    "CREATE INDEX doc_tenant IF NOT EXISTS FOR (d:Document) ON (d.tenant_id)",
    "CREATE INDEX doc_skeleton IF NOT EXISTS FOR (d:Document) ON (d.is_skeleton)",
    "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)",
    "CREATE INDEX concept_tenant IF NOT EXISTS FOR (c:Concept) ON (c.tenant_id)",
    "CREATE INDEX person_tenant IF NOT EXISTS FOR (p:Person) ON (p.tenant_id)",
    "CREATE INDEX product_tenant IF NOT EXISTS FOR (p:Product) ON (p.tenant_id)",
    "CREATE INDEX product_status IF NOT EXISTS FOR (p:Product) ON (p.status)",
    "CREATE INDEX tech_status IF NOT EXISTS FOR (t:Technology) ON (t.status)",
    "CREATE INDEX reg_jurisdiction IF NOT EXISTS FOR (r:Regulation) ON (r.jurisdiction)",
]
