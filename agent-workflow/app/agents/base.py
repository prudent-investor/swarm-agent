from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Route(str, Enum):
    knowledge = "knowledge"
    support = "support"
    custom = "custom"
    slack = "slack"


class RoutingDecision(BaseModel):
    route: Route
    hint: Optional[str] = Field(default=None, description="Optional hint to refine downstream handling.")


class RoutingRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to classify.")


class AgentRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    agent: str = Field(..., description="Identifier of the agent that produced the answer.")
    content: str = Field(..., description="Agent response already normalised and truncated as needed.")
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Optional[Dict[str, Any]] = None


class AgentControlledError(Exception):
    """Raised by agents when a predictable failure occurs (e.g. validation issues)."""

    def __init__(self, *, error: str, status_code: int = 400, details: Optional[str] = None, agent: Optional[str] = None) -> None:
        super().__init__(error)
        self.error = error
        self.details = details
        self.status_code = status_code
        self.agent = agent


@runtime_checkable
class Agent(Protocol):
    name: str

    def run(self, payload: AgentRequest) -> AgentResponse:
        ...
