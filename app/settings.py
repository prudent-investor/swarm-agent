from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agent Workflow"
    app_version: str = "0.1.0"
    app_port: int = 8000
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    rag_enabled: bool = True
    rag_top_k: int = 5
    rag_max_context_chars: int = 8000
    rag_min_score: float = 0.5
    rag_rerank_title_boost: float = 0.1
    rag_rerank_exact_term_boost: float = 0.2
    rag_rerank_length_penalty: float = 0.1
    rag_cache_ttl_seconds: int = 300
    rag_admin_enabled: bool = False
    rag_diagnostics_enabled: bool = False

    rag_max_pages: int = 5
    rag_max_depth: int = 1
    rag_request_timeout: float = 10.0
    rag_request_interval: float = 1.0
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 200

    web_search_enabled: bool = False
    web_search_provider: Optional[str] = None
    web_search_api_key: Optional[str] = None

    support_faq_enabled: bool = True
    support_faq_score_threshold: float = 0.65
    support_tickets_persist_to_file: bool = False
    support_tickets_file_path: str = "data/support/tickets.json"
    support_escalation_auto: bool = False
    support_pii_masking_enabled: bool = True
    support_max_response_chars: int = 1200
    support_category_terms_overrides: Optional[str] = None
    support_severity_terms_overrides: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
