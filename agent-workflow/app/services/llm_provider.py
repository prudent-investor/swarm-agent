from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.settings import settings


class LLMProviderError(RuntimeError):
    """Raised when the language model provider cannot produce a response."""


class LLMProvider:
    def __init__(self, *, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if not self.api_key:
            raise LLMProviderError("OpenAI API key is not configured.")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def generate_response(
        self,
        *,
        system_prompt: str,
        user_message: str,
        metadata: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
    ) -> str:
        if not user_message.strip():
            raise LLMProviderError("Message to model cannot be empty.")

        client = self._get_client()

        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": system_prompt},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_message},
                ],
            },
        ]

        if metadata:
            meta_snippet = "\n".join(f"{key}: {value}" for key, value in metadata.items())
            messages.append(
                {
                    "role": "system",
                    "content": [
                        {"type": "input_text", "text": f"Context metadata:\n{meta_snippet}"},
                    ],
                }
            )

        try:
            response = client.responses.create(
                model=self.model,
                temperature=temperature,
                input=messages,
            )
        except Exception as exc:  # pragma: no cover
            raise LLMProviderError("Failed to query OpenAI API.") from exc

        text = self._extract_text(response)
        if not text:
            raise LLMProviderError("Language model returned no content.")

        return text.strip()

    @staticmethod
    def _extract_text(response: Any) -> Optional[str]:
        if response is None:
            return None

        text = getattr(response, "output_text", None)
        if text:
            return text

        output = getattr(response, "output", None) or []
        for item in output:
            item_type = getattr(item, "type", None)
            if item_type == "output_text":
                possible = getattr(item, "text", None)
                if possible:
                    return possible
            if item_type == "message":
                contents = getattr(item, "content", [])
                for content in contents:
                    if getattr(content, "type", None) == "output_text":
                        possible = getattr(content, "text", None)
                        if possible:
                            return possible
        return None
