import json

import httpx2
import pytest

from orysys.adapters.cloudflare.chat import CloudflareChatModel
from orysys.ports.models import MessageRole, ModelMessage, ModelRequest


@pytest.mark.asyncio
async def test_cloudflare_chat_maps_messages_and_json_schema() -> None:
    async def handler(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer token"
        assert request.headers["cf-aig-gateway-id"] == "default"
        assert payload["messages"] == [{"role": "user", "content": "Question"}]
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["max_tokens"] == 256
        return httpx2.Response(
            200,
            json={
                "model": "chat-model",
                "choices": [{"message": {"content": '{"answer":"ok"}'}}],
            },
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    model = CloudflareChatModel(
        account_id="account",
        api_token="token",
        model="chat-model",
        max_tokens=256,
        gateway_id="default",
        client=client,
    )
    request = ModelRequest(
        messages=(ModelMessage(role=MessageRole.USER, content="Question"),),
        response_schema={"type": "object"},
    )

    result = await model.complete(request)

    assert result.text == '{"answer":"ok"}'
    assert result.model == "chat-model"
    await client.aclose()
