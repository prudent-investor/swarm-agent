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

    slack_enabled: bool = False
    slack_mode: str = "mock"
    slack_webhook_url: Optional[str] = None
    slack_bot_token: Optional[str] = None
    slack_default_channel: str = "#support-escalations"
    slack_timeout_seconds: float = 10.0
    slack_max_retries: int = 2

    redirect_enabled: bool = True
    redirect_confidence_threshold: float = 0.3
    guardrails_redirect_always: bool = False
    slack_agent_enabled: bool = True
    slack_channel_default: str = support-humans

    handoff_confirm_ttl_seconds: int = 300
    handoff_summary_max_chars: int = 280
    handoff_details_max_chars: int = 1200
    pii_masking_enabled: bool = True
    pii_mask_email: bool = True
    pii_mask_phone: bool = True
    pii_mask_docs: bool = False

    guardrails_enabled: bool = True
    guardrails_mode: str = "balanced"
    guardrails_max_input_chars: int = 4000
    guardrails_max_output_chars: int = 3000
    guardrails_normalize_remove_accents: bool = True
    guardrails_normalize_strip_symbols: str = "~,^,\u00b4,\u00b8,`,\\"
    guardrails_anti_injection_enabled: bool = True
    guardrails_anti_injection_patterns: Optional[str] = None
    guardrails_moderation_enabled: bool = True
    guardrails_moderation_blocklist_terms: Optional[str] = None
    guardrails_diagnostics_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
