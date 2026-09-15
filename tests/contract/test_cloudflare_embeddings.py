import math

import httpx2
import pytest

from orysys.adapters.cloudflare.embeddings import CloudflareEmbeddingModel


@pytest.mark.asyncio
async def test_cloudflare_embedding_mapping_and_normalization() -> None:
    async def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["cf-aig-gateway-id"] == "default"
        return httpx2.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 4.0, 0.0]},
                    {"index": 0, "embedding": [3.0, 0.0, 0.0]},
                ]
            },
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    model = CloudflareEmbeddingModel(
        account_id="account",
        api_token="token",
        model="embedding-model",
        expected_dimensions=3,
        gateway_id="default",
        client=client,
    )

    vectors = await model.embed(["first", "second"])

    assert vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert all(math.isclose(sum(value * value for value in vector), 1.0) for vector in vectors)
    await client.aclose()


@pytest.mark.asyncio
async def test_cloudflare_rejects_wrong_embedding_dimension() -> None:
    async def handler(request: httpx2.Request) -> httpx2.Response:
        del request
        return httpx2.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    model = CloudflareEmbeddingModel(
        account_id="account",
        api_token="token",
        model="embedding-model",
        expected_dimensions=3,
        client=client,
    )

    with pytest.raises(ValueError, match="dimension mismatch"):
        await model.embed(["first"])
    await client.aclose()
