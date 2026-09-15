from collections.abc import AsyncIterator
from typing import Any

import httpx2
from pydantic import BaseModel, ConfigDict

from orysys.domain.errors import ProviderUnavailable
from orysys.ports.models import ModelRequest, ModelResult


class _ResponseMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str


class _Choice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: _ResponseMessage


class _ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    choices: list[_Choice]
    model: str | None = None


class CloudflareChatModel:
    """Cloudflare Workers AI through its OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        model: str,
        max_tokens: int,
        gateway_id: str | None = None,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._owns_client = client is None
        headers = {"Authorization": f"Bearer {api_token}"}
        if gateway_id:
            headers["cf-aig-gateway-id"] = gateway_id
        self._headers = headers
        self._client = client or httpx2.AsyncClient(
            base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
            timeout=httpx2.Timeout(45.0, connect=10.0),
        )

    async def complete(self, request: ModelRequest) -> ModelResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "max_tokens": request.max_tokens or self._max_tokens,
        }
        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": request.response_schema,
            }
        try:
            response = await self._client.post(
                "/chat/completions", headers=self._headers, json=payload
            )
            response.raise_for_status()
            parsed = _ChatResponse.model_validate(response.json())
            choice = parsed.choices[0]
        except (httpx2.HTTPError, ValueError, IndexError) as error:
            raise ProviderUnavailable("Cloudflare chat") from error
        return ModelResult(text=choice.message.content, model=parsed.model or self._model)

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        result = await self.complete(request)
        yield result.text

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
