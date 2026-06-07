"""
src/config.py
─────────────────────────────────────────────────────────────────
Central configuration for the FlowDesk Agentic Support system.

All environment variables are read ONCE here at startup.
Every other module imports from this file — nothing is hardcoded
anywhere else in the codebase.

Usage:
    from src.config import settings
    print(settings.db_path)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    """
    Reads configuration from environment variables and .env file.
    Pydantic-settings handles type coercion and validation automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── OpenAI ───────────────────────────────────────────────────
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field("gpt-4o-mini", description="OpenAI model for orchestrator")
    openai_max_tokens: int = Field(1500, description="Max tokens for LLM responses")
    openai_temperature: float = Field(0.0, description="LLM temperature")

    # ── Mock REST API ─────────────────────────────────────────────
    api_host: str = Field("0.0.0.0", description="FastAPI host")
    api_port: int = Field(8001, description="FastAPI port")

    # ── Database ──────────────────────────────────────────────────
    db_path: str = Field("mock-services/flowdesk.db", description="SQLite DB path")

    # ── RAG Pipeline ──────────────────────────────────────────────
    docs_dir: str = Field("docs", description="Product docs directory")
    chroma_persist_dir: str = Field(".chroma_store", description="ChromaDB persist dir")
    chroma_collection_name: str = Field("flowdesk_docs", description="ChromaDB collection name")
    embedding_model: str = Field("all-MiniLM-L6-v2", description="Sentence-transformers model")
    rag_top_k_dense: int = Field(5, description="Dense retrieval top-k")
    rag_top_k_sparse: int = Field(5, description="BM25 sparse retrieval top-k")
    rag_top_k_final: int = Field(3, description="Final top-k after reranking")
    rag_min_relevance_score: float = Field(0.3, description="Minimum relevance threshold")

    # ── Retry / Resilience ────────────────────────────────────────
    tool_max_retries: int = Field(3, description="Max retries for tool calls")
    tool_retry_base_delay: float = Field(1.0, description="Base delay seconds for backoff")
    tool_retry_max_delay: float = Field(10.0, description="Max delay seconds for backoff")
    tool_timeout_seconds: float = Field(10.0, description="Per-tool timeout in seconds")

    # ── Orchestrator ──────────────────────────────────────────────
    agent_min_confidence: float = Field(0.6, description="Min confidence to auto-resolve")
    agent_max_tool_calls: int = Field(10, description="Max tool calls per query")

    # ── Security ──────────────────────────────────────────────────
    blocked_doc_sources: str = Field(
        "system-override.md",
        description="Comma-separated blocked document sources",
    )

    # ── Logging ───────────────────────────────────────────────────
    log_level: str = Field("INFO", description="Logging level")

    # ── Derived Properties ────────────────────────────────────────
    @property
    def db_path_resolved(self) -> Path:
        """Returns the DB path as an absolute Path object."""
        return Path(self.db_path).resolve()

    @property
    def docs_dir_resolved(self) -> Path:
        """Returns the docs directory as an absolute Path object."""
        return Path(self.docs_dir).resolve()

    @property
    def blocked_sources_list(self) -> list[str]:
        """Returns blocked doc sources as a list."""
        return [s.strip() for s in self.blocked_doc_sources.split(",") if s.strip()]


# ── Singleton ─────────────────────────────────────────────────────
# Instantiated once at import time. All modules share this instance.
settings = Settings()