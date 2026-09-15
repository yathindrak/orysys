import asyncio
import math
from collections.abc import Sequence

import httpx2
from pydantic import BaseModel, ConfigDict

from orysys.domain.errors import ProviderUnavailable


class _EmbeddingItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index: int
    embedding: list[float]


class _EmbeddingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[_EmbeddingItem]


class CloudflareEmbeddingModel:
    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        model: str,
        expected_dimensions: int,
        gateway_id: str | None = None,
        batch_size: int = 32,
        max_concurrency: int = 3,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._expected_dimensions = expected_dimensions
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._owns_client = client is None
        headers = {"Authorization": f"Bearer {api_token}"}
        if gateway_id:
            headers["cf-aig-gateway-id"] = gateway_id
        self._headers = headers
        self._client = client or httpx2.AsyncClient(
            base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
            timeout=httpx2.Timeout(30.0, connect=10.0),
        )

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        batches = [
            texts[start : start + self._batch_size]
            for start in range(0, len(texts), self._batch_size)
        ]
        results = await asyncio.gather(*(self._embed_batch(batch) for batch in batches))
        return [vector for batch in results for vector in batch]

    async def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        async with self._semaphore:
            try:
                response = await self._client.post(
                    "/embeddings",
                    headers=self._headers,
                    json={"model": self._model, "input": list(texts)},
                )
                response.raise_for_status()
            except httpx2.HTTPError as error:
                raise ProviderUnavailable("Cloudflare embeddings") from error
        payload = _EmbeddingResponse.model_validate(response.json())
        ordered = sorted(payload.data, key=lambda item: item.index)
        vectors = [self._normalize(item.embedding) for item in ordered]
        if len(vectors) != len(texts):
            raise ValueError("Cloudflare returned an unexpected embedding count")
        return vectors

    def _normalize(self, vector: list[float]) -> list[float]:
        if len(vector) != self._expected_dimensions:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected {self._expected_dimensions}, got {len(vector)}"
            )
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            raise ValueError("Embedding vector has zero magnitude")
        return [value / magnitude for value in vector]

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
