from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from app.settings import settings


class ValidationError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": "invalid_input", "detail": detail})


def validate_payload(message: Optional[str], user_id: Optional[str], metadata: Optional[Dict[str, Any]]) -> None:
    if not isinstance(message, str) or not message.strip():
        raise ValidationError("Campo 'message' deve ser uma string nao vazia.")

    if len(message) > settings.guardrails_max_input_chars:
        raise ValidationError("Campo 'message' excede o limite permitido.")

    if user_id is not None and not isinstance(user_id, str):
        raise ValidationError("Campo 'user_id' deve ser string ou nulo.")

    if metadata is not None and not isinstance(metadata, dict):
        raise ValidationError("Campo 'metadata' deve ser um objeto JSON.")
