from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import asdict
from typing import Iterable, List, Optional

from app.agents.base import Agent, AgentControlledError, AgentRequest, AgentResponse
from app.services.llm_provider import LLMProvider, LLMProviderError
from app.services.rag import (
    Citation,
    HeuristicReranker,
    QueryCache,
    RAGRetriever,
    RetrievedChunk,
    build_citations,
    build_context,
    filter_chunks,
)
from app.services.web_search import NoopWebSearchClient, WebSearchClient, WebSearchResult
from app.guardrails import get_guardrails_service
from app.settings import settings

logger = logging.getLogger(__name__)
_guardrails_service = get_guardrails_service()

FALLBACK_URLS = ["https://www.infinitepay.io"]


class KnowledgeAgent(Agent):
    name = "knowledge"

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        retriever: Optional[RAGRetriever] = None,
        reranker: Optional[HeuristicReranker] = None,
        cache: Optional[QueryCache] = None,
        web_search: Optional[WebSearchClient] = None,
    ) -> None:
        self._provider = provider or LLMProvider()
        self._retriever = retriever or RAGRetriever()
        self._reranker = reranker or HeuristicReranker()
        self._cache = cache or QueryCache(ttl_seconds=settings.rag_cache_ttl_seconds)
        self._web_search = web_search or NoopWebSearchClient()

    def run(self, payload: AgentRequest) -> AgentResponse:
        start_time = time.perf_counter()
        query = payload.message.strip()
        normalised = query.lower()
        user_id = payload.user_id
        history_key = f"user_history::{user_id}" if user_id else None
        previous_message = None
        remembered_name = None
        stored_history = None
        if history_key:
            stored_history = self._cache.get(history_key)
            if isinstance(stored_history, dict):
                previous_message = stored_history.get("last_message")
                name_value = stored_history.get("name")
                if isinstance(name_value, str) and name_value.strip():
                    remembered_name = name_value.strip()

        remembered_previous = bool(previous_message)
        language = _detect_language(query)
        extracted_name = _extract_name(query)
        active_name = extracted_name or remembered_name

        if _is_name_recall_question(query):
            response = _name_recall_response(active_name, language)
            response.meta.update(
                {
                    "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
                    "remembered_name": bool(active_name),
                    "response_language": language,
                    "previous_message_remembered": remembered_previous,
                }
            )
            self._record_user_message(history_key, query, name=active_name)
            return response

        if not settings.rag_enabled:
            response = self._fallback_response(
                query,
                cache_hit=False,
                rag_used=False,
                web_search_used=False,
                remembered_previous=remembered_previous,
                remembered_name=active_name,
                language=language,
            )
            response.meta.update(
                {
                    "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
                    "remembered_name": bool(active_name),
                    "response_language": language,
                }
            )
            self._record_user_message(history_key, query, name=active_name)
            return response

        cache_key = normalised
        cached = self._cache.get(cache_key)
        cache_hit = cached is not None
        if cached:
            context_text, selected_chunks = cached["context"], _deserialize_chunks(cached["chunks"])
            reranked_chunks = selected_chunks
        else:
            retrieved = self._retriever.retrieve(query, top_k=settings.rag_top_k)
            reranked = self._reranker.rerank(query, retrieved)
            filtered = filter_chunks(reranked)
            filtered = _guardrails_service.filter_context(filtered)
            context_text, selected_chunks = build_context(filtered, max_chars=settings.rag_max_context_chars)
            reranked_chunks = selected_chunks
            serialisable = {
                "context": context_text,
                "chunks": [_serialise_chunk(chunk) for chunk in selected_chunks],
            }
            self._cache.set(cache_key, serialisable)

        rag_used = bool(context_text)
        fallback_used = not rag_used
        web_search_used = False
        external_citations: List[WebSearchResult] = []

        if not rag_used and settings.web_search_enabled:
            external_citations = self._web_search.search(query, top_k=3)
            web_search_used = bool(external_citations)

        if not rag_used and not external_citations:
            response = self._fallback_response(
                query,
                cache_hit=cache_hit,
                rag_used=False,
                web_search_used=False,
                remembered_previous=remembered_previous,
                remembered_name=active_name,
                language=language,
            )
            response.meta.update(
                {
                    "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
                    "remembered_name": bool(active_name),
                    "response_language": language,
                }
            )
            self._record_user_message(history_key, query, name=active_name)
            return response

        try:
            context_snippets = []
            if context_text:
                context_snippets.append(context_text)
            if external_citations:
                for result in external_citations:
                    snippet = f"External source: {result.url}\nExcerpt: {result.snippet}"
                    context_snippets.append(snippet)

            composed_context = "\n\n".join(context_snippets)
            language_label = "Portuguese" if language == "pt" else "English"
            system_prompt = (
                "You are InfinitePay's KnowledgeAgent v2. Use only the provided context to answer. "
                f"Respond in {language_label} using 2 to 5 sentences and always cite the relevant sources. "
                "If the context does not cover the request, be explicit about that. "
                "When the user's preferred name is provided, acknowledge them naturally in that language."
            )
            conversation_lines = [f"Latest user message: {query}"]
            if previous_message:
                conversation_lines.insert(0, f"Previous user message: {previous_message}")
            if active_name:
                conversation_lines.insert(0, f"User prefers to be called: {active_name}")
            conversation_snapshot = "\n".join(conversation_lines)
            user_prompt = (
                f"Conversation snapshot:\n{conversation_snapshot}\n\n"
                f"Support context:\n{composed_context}\n\n"
                f"Instruction: deliver a concise answer in {language_label}, cite the supporting sources by name, "
                "and keep the tone helpful."
            )
            ai_response = self._provider.generate_response(
                system_prompt=system_prompt,
                user_message=user_prompt,
                metadata={"rag_used": rag_used, "web_search_used": web_search_used},
                temperature=0.2,
            )
        except LLMProviderError as exc:
            logger.error("rag.knowledge.llm_failure", extra={"error": str(exc)})
            raise AgentControlledError(
                error="knowledge_agent_unavailable",
                status_code=503,
                details="The language model could not be reached.",
                agent=self.name,
            ) from exc

        citations = build_citations(
            reranked_chunks if rag_used else [],
            fallback_urls=FALLBACK_URLS,
            external_sources=[
                _external_citation(result) for result in external_citations
            ] if external_citations else None,
        )

        meta = {
            "rag_used": rag_used,
            "top_k_selected": len(reranked_chunks),
            "avg_score": _average_score(reranked_chunks),
            "cache_hit": cache_hit,
            "fallback_used": fallback_used,
            "web_search_used": web_search_used,
            "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
            "previous_message_remembered": remembered_previous,
            "remembered_name": bool(active_name),
            "response_language": language,
        }

        response = AgentResponse(
            agent=self.name,
            content=_normalise_text(ai_response),
            citations=citations,
            meta=meta,
        )
        self._record_user_message(history_key, query, name=active_name)
        return response

    def _fallback_response(
        self,
        query: str,
        *,
        cache_hit: bool,
        rag_used: bool,
        web_search_used: bool,
        remembered_previous: bool,
        remembered_name: Optional[str],
        language: str,
    ) -> AgentResponse:
        if language == "pt":
            greeting = "Olá!"
            if remembered_name:
                greeting = f"Olá, {remembered_name}!"
            if _is_simple_greeting(query):
                content = (
                    f"{greeting} Como posso ajudar você desta vez?"
                    if remembered_previous
                    else f"{greeting} Como posso ajudar você hoje?"
                )
            else:
                prefix = f"{remembered_name}, " if remembered_name else ""
                if remembered_previous:
                    content = (
                        f"{prefix}ainda não encontrei informações suficientes na base de conhecimento, "
                        "mas continuo acompanhando sua solicitação. Pode me contar um pouco mais "
                        "sobre o que você precisa para que eu possa ajudar melhor?"
                    )
                else:
                    content = (
                        f"{prefix}ainda não encontrei informações suficientes na base de conhecimento. "
                        "Pode compartilhar mais detalhes? Estou aqui para ajudar!"
                    )
        else:
            greeting = "Hello!"
            if remembered_name:
                greeting = f"Hello, {remembered_name}!"
            if _is_simple_greeting(query):
                content = (
                    f"{greeting} How can I help you this time?"
                    if remembered_previous
                    else f"{greeting} How can I help you today?"
                )
            else:
                prefix = f"{remembered_name}, " if remembered_name else ""
                if remembered_previous:
                    content = (
                        f"{prefix}I still haven't found enough details in the knowledge base, but I'm "
                        "following your request. Could you share a bit more so I can support you better?"
                    )
                else:
                    content = (
                        f"{prefix}I couldn't find enough information in the knowledge base yet. "
                        "Could you share more details? I'm here to help!"
                    )
        citations = build_citations([], fallback_urls=FALLBACK_URLS)
        meta = {
            "rag_used": rag_used,
            "top_k_selected": 0,
            "avg_score": 0.0,
            "cache_hit": cache_hit,
            "fallback_used": True,
            "web_search_used": web_search_used,
            "duration_ms": 0.0,
            "previous_message_remembered": remembered_previous,
            "remembered_name": bool(remembered_name),
            "response_language": language,
        }
        return AgentResponse(agent=self.name, content=content, citations=citations, meta=meta)

    def _record_user_message(self, history_key: Optional[str], message: str, *, name: Optional[str]) -> None:
        if not history_key:
            return
        try:
            existing = self._cache.get(history_key)
            payload = dict(existing) if isinstance(existing, dict) else {}
            payload["last_message"] = message
            if name:
                payload["name"] = name
            self._cache.set(history_key, payload)
        except Exception:
            logger.debug("rag.knowledge.history_store_failed", extra={"history_key": history_key})


def _external_citation(result: WebSearchResult) -> Citation:
    return Citation(title=result.title or _title_from_external(result.url), url=result.url, source_type="external")


def _title_from_external(url: str) -> str:
    if not url:
        return "External Source"
    parts = url.split("//", 1)[-1]
    return parts.split("/", 1)[0]


def _average_score(chunks: Iterable[RetrievedChunk]) -> float:
    scores = [chunk.rank_score or chunk.raw_score for chunk in chunks if chunk.rank_score or chunk.raw_score]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 3)


def _normalise_text(text: str) -> str:
    return " ".join(text.strip().split())


_GREETING_WORDS = {
    "oi",
    "ola",
    "hello",
    "hi",
    "hey",
    "eai",
    "eae",
}

_GREETING_PHRASES = {
    "bom dia",
    "boa tarde",
    "boa noite",
    "ola bom dia",
    "ola boa tarde",
    "ola boa noite",
}


_PORTUGUESE_WORDS = {
    "oi",
    "ola",
    "olá",
    "voce",
    "você",
    "meu",
    "minha",
    "problema",
    "ajuda",
    "ajudar",
    "preciso",
    "precisa",
    "suporte",
    "ainda",
    "lembrar",
    "lembra",
    "nome",
    "poderia",
    "cpf",
    "cnpj",
}

_ENGLISH_INDICATORS = {
    "hello",
    "hi",
    "please",
    "problem",
    "help",
    "remember",
    "name",
    "could",
    "thank",
}


def _strip_accents(value: str) -> str:
    normalised = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalised if unicodedata.category(char) != "Mn")


def _is_simple_greeting(text: str) -> bool:
    cleaned = _strip_accents(text or "").lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return False
    if cleaned in _GREETING_PHRASES or cleaned in _GREETING_WORDS:
        return True
    words = cleaned.split()
    if len(words) <= 3 and words:
        if words[0] in _GREETING_WORDS:
            return True
        joined = " ".join(words[:2])
        if joined in _GREETING_PHRASES:
            return True
    return False


_NAME_PATTERNS = [
    re.compile(r"\bmeu nome (?:é|e)\s+([^.,;!?\n\d]{2,})", re.IGNORECASE),
    re.compile(r"\bme chamo\s+([^.,;!?\n\d]{2,})", re.IGNORECASE),
    re.compile(r"\bchamo-me\s+([^.,;!?\n\d]{2,})", re.IGNORECASE),
    re.compile(r"\bmy name is\s+([^.,;!?\n\d]{2,})", re.IGNORECASE),
]

_NAME_RECALL_PATTERNS = [
    "lembra do meu nome",
    "voce lembra do meu nome",
    "voce lembra meu nome",
    "sabe meu nome",
    "qual e meu nome",
    "qual é meu nome",
    "remember my name",
    "do you remember my name",
    "what is my name again",
]


def _detect_language(text: str) -> str:
    if not text:
        return "en"
    lowered = text.lower()
    if any(char in "áéíóúãõâêôç" for char in lowered):
        return "pt"
    cleaned = _strip_accents(text).lower()
    words = re.findall(r"[a-z]+", cleaned)
    if any(word in _PORTUGUESE_WORDS for word in words):
        return "pt"
    if any(phrase in cleaned for phrase in ("meu nome", "por favor", "pode me ajudar", "voce")):
        return "pt"
    if any(word in _ENGLISH_INDICATORS for word in words):
        return "en"
    return "en"


def _extract_name(text: str) -> Optional[str]:
    if not text:
        return None
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            normalised = _normalise_name(match.group(1))
            if normalised:
                return normalised
    return None


def _normalise_name(raw: str) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip().strip("\"' ")
    cleaned = re.split(r"[\n\r]", cleaned)[0]
    cleaned = re.split(r"\b(?:mas|porque|por que|por quê|and|but|please|poderia)\b", cleaned, maxsplit=1)[0]
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    parts = [part for part in cleaned.split(" ") if part]
    if not parts or len(parts) > 4:
        return None
    if parts[0].lower() in {"o", "a"} and len(parts) > 1:
        parts = parts[1:]
    if not parts:
        return None
    formatted_parts = []
    for part in parts:
        token = part.strip("-'")
        if not token or not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ'-]+", part):
            return None
        formatted_parts.append(part[:1].upper() + part[1:].lower())
    candidate = " ".join(formatted_parts)
    if len(candidate) < 2:
        return None
    return candidate


def _is_name_recall_question(text: str) -> bool:
    if not text:
        return False
    cleaned = re.sub(r"[^a-z\s]", " ", _strip_accents(text).lower())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return any(phrase in cleaned for phrase in _NAME_RECALL_PATTERNS)


def _name_recall_response(name: Optional[str], language: str) -> AgentResponse:
    if language == "pt":
        if name:
            content = f"Sim, você se chama {name}. Como posso ajudar você hoje?"
        else:
            content = "Ainda não registrei seu nome. Poderia me lembrar como devo chamá-lo?"
    else:
        if name:
            content = f"Yes, your name is {name}. How can I assist you today?"
        else:
            content = "I haven't saved your name yet. Could you remind me how I should address you?"
    citations = build_citations([], fallback_urls=FALLBACK_URLS)
    meta = {
        "rag_used": False,
        "top_k_selected": 0,
        "avg_score": 0.0,
        "cache_hit": False,
        "fallback_used": True,
        "web_search_used": False,
        "duration_ms": 0.0,
        "previous_message_remembered": False,
        "remembered_name": bool(name),
        "response_language": language,
    }
    return AgentResponse(agent="knowledge", content=content, citations=citations, meta=meta)


def _serialise_chunk(chunk: RetrievedChunk) -> dict:
    return {
        "id": chunk.id,
        "url": chunk.url,
        "title": chunk.title,
        "order": chunk.order,
        "text": chunk.text,
        "raw_score": chunk.raw_score,
        "content_hash": chunk.content_hash,
        "ingest_timestamp": chunk.ingest_timestamp,
        "rank_score": chunk.rank_score,
    }


def _deserialize_chunks(serialised: List[dict]) -> List[RetrievedChunk]:
    chunks: List[RetrievedChunk] = []
    for entry in serialised:
        chunks.append(
            RetrievedChunk(
                id=entry.get("id", ""),
                url=entry.get("url", ""),
                title=entry.get("title"),
                order=entry.get("order", 0),
                text=entry.get("text", ""),
                raw_score=entry.get("raw_score", 0.0),
                content_hash=entry.get("content_hash", ""),
                ingest_timestamp=entry.get("ingest_timestamp"),
                rank_score=entry.get("rank_score"),
            )
        )
    return chunks



