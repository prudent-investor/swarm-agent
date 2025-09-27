from __future__ import annotations

import re

from app.agents.base import Agent, AgentControlledError, AgentRequest, AgentResponse
from app.services.llm_provider import LLMProvider, LLMProviderError

_MAX_RESPONSE_LENGTH = 1500

_SYSTEM_PROMPT = (
    "You are CustomAgent v1. Handle generic or out-of-scope messages with a professional"
    " and succinct tone. Explain that the message nao se enquadra nas categorias atuais"
    " (knowledge/support) e convide o usuario a reformular. Responda em PT-BR."
)


def _normalise(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) > _MAX_RESPONSE_LENGTH:
        cleaned = cleaned[:_MAX_RESPONSE_LENGTH].rstrip()
    return cleaned


class CustomAgent(Agent):
    name = "custom_agent_v1"

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def run(self, payload: AgentRequest) -> AgentResponse:
        try:
            raw_answer = self._provider.generate_response(
                system_prompt=_SYSTEM_PROMPT,
                user_message=payload.message,
                metadata=payload.metadata,
                temperature=0.2,
            )
        except LLMProviderError as exc:
            raise AgentControlledError(
                error="custom_agent_unavailable",
                status_code=503,
                details="Assistente generico indisponivel.",
                agent=self.name,
            ) from exc

        content = _normalise(raw_answer)
        if not content:
            content = _normalise(
                "Ainda nao entendi como posso ajudar. Reformule a pergunta escolhendo"
                " se deseja informacoes sobre o produto (knowledge) ou suporte tecnico."
            )

        return AgentResponse(agent=self.name, content=content, meta={"notes": "custom_v1"})
