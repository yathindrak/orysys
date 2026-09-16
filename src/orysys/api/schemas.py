from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from orysys.application.conversations import Conversation


class CreateConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: Conversation


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    message: str = Field(min_length=1, max_length=8_000)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool = False
