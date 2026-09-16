import asyncio
import json

import httpx2
import pytest

from orysys.adapters.cloudflare.chat import CloudflareChatModel
from orysys.domain.errors import ProviderUnavailable
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


@pytest.mark.asyncio
async def test_chat_retries_429_but_not_403() -> None:
    attempts = 0

    async def transient(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx2.Response(429, headers={"retry-after": "0"}, request=request)
        return httpx2.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            request=request,
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(transient))
    model = CloudflareChatModel(
        account_id="account",
        api_token="token",
        model="chat-model",
        max_tokens=64,
        retry_attempts=3,
        client=client,
    )
    request = ModelRequest(messages=(ModelMessage(role=MessageRole.USER, content="hello"),))

    assert (await model.complete(request)).text == "ok"
    assert attempts == 2
    await client.aclose()

    attempts = 0

    async def forbidden(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return httpx2.Response(403, request=request)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(forbidden))
    model = CloudflareChatModel(
        account_id="account",
        api_token="token",
        model="chat-model",
        max_tokens=64,
        retry_attempts=3,
        client=client,
    )
    with pytest.raises(ProviderUnavailable):
        await model.complete(request)
    assert attempts == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_chat_concurrency_is_capped() -> None:
    active = 0
    peak = 0

    async def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx2.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            request=request,
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    model = CloudflareChatModel(
        account_id="account",
        api_token="token",
        model="chat-model",
        max_tokens=64,
        max_concurrency=2,
        client=client,
    )
    request = ModelRequest(messages=(ModelMessage(role=MessageRole.USER, content="hello"),))

    await asyncio.gather(*(model.complete(request) for _ in range(8)))

    assert peak == 2
    await client.aclose()
