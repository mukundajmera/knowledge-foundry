"""Knowledge Foundry — Application Configuration.

Uses pydantic-settings to load configuration from environment variables and .env files.
Grouped by service domain for clarity.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnthropicSettings(BaseSettings):
    """Anthropic LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_")

    api_key: str = Field(default="", description="Anthropic API key")
    model_opus: str = Field(
        default="claude-opus-4-20250514", description="Opus model identifier"
    )
    model_sonnet: str = Field(
        default="claude-sonnet-4-20250514", description="Sonnet model identifier"
    )
    model_haiku: str = Field(
        default="claude-3-5-haiku-20241022", description="Haiku model identifier"
    )
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retries on transient errors")
    timeout: int = Field(default=30, ge=5, le=120, description="Request timeout in seconds")


class OpenAISettings(BaseSettings):
    """OpenAI embedding provider configuration."""

    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    api_key: str = Field(default="", description="OpenAI API key")
    embedding_model: str = Field(
        default="text-embedding-3-large", description="Embedding model name"
    )
    embedding_dimensions: int = Field(
        default=3072, ge=256, le=3072, description="Embedding vector dimensions"
    )


class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    host: str = Field(default="localhost", description="Qdrant host")
    port: int = Field(default=6333, description="Qdrant HTTP port")
    grpc_port: int = Field(default=6334, description="Qdrant gRPC port")
    api_key: str = Field(default="", description="Qdrant API key (optional)")
    collection_prefix: str = Field(
        default="kf_tenant_", description="Collection name prefix"
    )
    # HNSW tuning — per phase-1.2 spec
    hnsw_m: int = Field(default=16, description="HNSW connections per node")
    hnsw_ef_construct: int = Field(default=200, description="HNSW build-time search quality")
    hnsw_ef_search: int = Field(default=128, description="HNSW query-time search quality")


class RedisSettings(BaseSettings):
    """Redis cache configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    password: str = Field(default="", description="Redis password")
    db: int = Field(default=0, ge=0, le=15, description="Redis database index")
    key_prefix: str = Field(default="kf:", description="Key namespace prefix")


class PostgresSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    db: str = Field(default="knowledge_foundry", description="Database name")
    user: str = Field(default="kf_user", description="Database user")
    password: str = Field(default="kf_dev_password", description="Database password")

    @property
    def dsn(self) -> str:
        """Build asyncpg-compatible DSN."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"



class Neo4jSettings(BaseSettings):
    """Neo4j graph database configuration."""

    model_config = SettingsConfigDict(env_prefix="NEO4J_")

    host: str = Field(default="localhost", description="Neo4j host")
    port: int = Field(default=7687, description="Neo4j Bolt port")
    user: str = Field(default="neo4j", description="Neo4j user")
    password: str = Field(default="kf_dev_password", description="Neo4j password")
    database: str = Field(default="neo4j", description="Neo4j database name")

    @property
    def bolt_uri(self) -> str:
        """Build Bolt URI for Neo4j driver."""
        return f"bolt://{self.host}:{self.port}"


class LLMSettings(BaseSettings):
    """LLM routing configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    allow_escalation: bool = Field(default=True, description="Allow tier escalation on low confidence")
    escalation_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence below which to escalate"
    )


class OracleCodeAssistSettings(BaseSettings):
    """Oracle Code Assist LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="ORACLE_")

    endpoint: str = Field(
        default="", description="Oracle Code Assist API endpoint URL"
    )
    api_key: str = Field(default="", description="Oracle API key")
    model: str = Field(
        default="oracle-code-assist-v1", description="Oracle model identifier"
    )
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retries")
    timeout: int = Field(default=30, ge=5, le=120, description="Request timeout in seconds")


class LMStudioSettings(BaseSettings):
    """LM Studio local LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LMSTUDIO_")

    host: str = Field(default="localhost", description="LM Studio server host")
    port: int = Field(default=1234, description="LM Studio server port")
    model: str = Field(
        default="", description="Model identifier loaded in LM Studio"
    )
    timeout: int = Field(default=60, ge=5, le=300, description="Request timeout in seconds")

    @property
    def base_url(self) -> str:
        """Build the base URL for LM Studio's OpenAI-compatible API."""
        return f"http://{self.host}:{self.port}/v1"


class OllamaSettings(BaseSettings):
    """Ollama local LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    host: str = Field(default="localhost", description="Ollama server host")
    port: int = Field(default=11434, description="Ollama server port")
    model: str = Field(
        default="llama3", description="Default Ollama model"
    )
    timeout: int = Field(default=120, ge=5, le=600, description="Request timeout in seconds")

    @property
    def base_url(self) -> str:
        """Build the base URL for the Ollama API."""
        return f"http://{self.host}:{self.port}"


class Settings(BaseSettings):
    """Root application settings — aggregates all sub-configs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="knowledge-foundry", description="Application name")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", description="Environment"
    )
    app_debug: bool = Field(default=True, description="Debug mode")
    app_host: str = Field(default="0.0.0.0", description="Server bind host")
    app_port: int = Field(default=8000, description="Server bind port")
    app_log_level: Literal["DEBUG", "INFO", "WARN", "ERROR"] = Field(
        default="INFO", description="Log level"
    )

    # Sub-configs
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    oracle: OracleCodeAssistSettings = Field(default_factory=OracleCodeAssistSettings)
    lmstudio: LMStudioSettings = Field(default_factory=LMStudioSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)

    # Security
    jwt_secret_key: str = Field(default="change-me-in-production", description="JWT signing key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=480, ge=15, le=1440, description="Token expiry"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()
