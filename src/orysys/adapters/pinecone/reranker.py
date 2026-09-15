from pinecone import AsyncPinecone

from orysys.domain.evidence import Evidence


class PineconeHostedReranker:
    def __init__(
        self,
        client: AsyncPinecone,
        *,
        model: str = "bge-reranker-v2-m3",
    ) -> None:
        self._client = client
        self._model = model

    async def rerank(
        self, query: str, candidates: tuple[Evidence, ...], limit: int
    ) -> tuple[Evidence, ...]:
        if not candidates:
            return ()
        result = await self._client.inference.rerank(
            model=self._model,
            query=query,
            documents=[{"text": candidate.excerpt} for candidate in candidates],
            rank_fields=["text"],
            return_documents=False,
            top_n=min(limit, len(candidates)),
        )
        return tuple(
            candidates[item.index].model_copy(update={"rerank_score": item.score})
            for item in result.data
        )
