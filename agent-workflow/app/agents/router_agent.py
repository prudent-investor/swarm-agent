import json
import re
import unicodedata
from typing import Optional

from openai import OpenAI

from app.settings import settings
from .base import Route, RoutingDecision

_DIRECT_REQUEST_PATTERNS = [
    "falar com humano",
    "quero humano",
    "quero um humano",
    "atendimento humano",
    "suporte humano",
    "pessoa de verdade",
    "falar com atendente",
    "preciso de humano",
]


def _extract_text_from_response(response) -> Optional[str]:
    try:
        for item in response.output:
            if getattr(item, "type", None) == "message":
                for content in getattr(item, "content", []):
                    if getattr(content, "type", None) == "output_text":
                        return getattr(content, "text", None)
            if getattr(item, "type", None) == "output_text":
                return getattr(item, "text", None)
    except AttributeError:
        pass
    return getattr(response, "output_text", None)


def _normalize(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "")
    cleaned = cleaned.strip().lower()
    if not cleaned:
        return ""
    decomposed = unicodedata.normalize("NFD", cleaned)
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", without_accents)


class RouterAgent:
    """Routes incoming messages to the appropriate downstream agent."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if not self.api_key:
            raise RuntimeError("OpenAI API key is not configured.")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def _fallback_route(self, message: str) -> RoutingDecision:
        text = _normalize(message)
        if not text:
            return RoutingDecision(route=Route.custom, hint="fallback_empty", confidence=None)

        support_keywords = {"pagamento", "pagamentos", "fraude", "cobranca", "chargeback", "suporte"}
        if any(keyword in text for keyword in support_keywords):
            return RoutingDecision(route=Route.support, hint="fallback_support", confidence=0.4)

        knowledge_keywords = {"politica", "privacidade", "privacy", "documentacao"}
        if any(keyword in text for keyword in knowledge_keywords):
            return RoutingDecision(route=Route.knowledge, hint="fallback_knowledge", confidence=0.4)

        return RoutingDecision(route=Route.custom, hint="fallback_custom", confidence=0.3)

    def _match_direct_handoff(self, message: str) -> bool:
        text = _normalize(message)
        if not text:
            return False
        for pattern in _DIRECT_REQUEST_PATTERNS:
            if pattern in text:
                return True
        if any(word in {"humano", "atendente"} for word in text.split()):
            if "quero" in text or "preciso" in text or "falar" in text:
                return True
        return False

    def route_message(self, message: str) -> RoutingDecision:
        if not message.strip():
            return RoutingDecision(route=Route.custom, hint="Empty message", confidence=None)

        if self._match_direct_handoff(message):
            return RoutingDecision(route=Route.slack, hint="user_requested_human", confidence=1.0)

        if not self.api_key:
            return self._fallback_route(message)

        client = self._get_client()

        system_message = (
            "You classify user intents for a multi-agent system."
            " Return a JSON object with keys 'route' (knowledge, support, custom, slack),"
            " optional 'hint', and optional 'confidence' (0-1)."
            " Use 'slack' when the user explicitly requests human assistance or escalation."
            " Respond with strict JSON."
        )

        try:
            response = client.responses.create(
                model=self.model,
                temperature=0,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {"type": "input_text", "text": system_message},
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": message},
                        ],
                    },
                ],
            )
        except Exception as exc:  # pragma: no cover - network errors handled at runtime
            raise RuntimeError("Failed to contact OpenAI API.") from exc

        content = _extract_text_from_response(response)
        if not content:
            return RoutingDecision(route=Route.custom, hint="LLM returned no content", confidence=None)

        route_value: Optional[str] = None
        hint_value: Optional[str] = None
        confidence_value: Optional[float] = None

        try:
            payload = json.loads(content)
            route_value = payload.get("route")
            hint_value = payload.get("hint")
            confidence_value = payload.get("confidence")
        except json.JSONDecodeError:
            normalized = content.lower()
            for candidate in Route:
                if candidate.value in normalized:
                    route_value = candidate.value
                    break

        try:
            route = Route(route_value) if route_value else Route.custom
        except ValueError:
            route = Route.custom
            hint_value = hint_value or "Model returned an unsupported route"

        try:
            if confidence_value is not None:
                confidence_value = float(confidence_value)
        except (TypeError, ValueError):
            confidence_value = None

        if confidence_value is not None and not (0.0 <= confidence_value <= 1.0):
            confidence_value = None

        return RoutingDecision(route=route, hint=hint_value, confidence=confidence_value)

router_agent = RouterAgent()


