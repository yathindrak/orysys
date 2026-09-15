import argparse
import asyncio
import json
from pathlib import Path

from pinecone import AsyncPinecone

from orysys.adapters.cloudflare.embeddings import CloudflareEmbeddingModel
from orysys.adapters.pinecone.reranker import PineconeHostedReranker
from orysys.adapters.pinecone.retrieval import PineconeKnowledgeIndex
from orysys.config import Settings
from orysys.domain.identity import Principal, Role
from orysys.domain.policy import derive_access_scope
from orysys.ingestion.sparse import PineconeBM25Encoder
from orysys.ports.retrieval import SearchOptions


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one live scoped hybrid search")
    parser.add_argument("query")
    parser.add_argument("--tenant", default="commercial-bank")
    parser.add_argument("--department", action="append", default=["payments"])
    parser.add_argument("--role", choices=[role.value for role in Role], default="analyst")
    parser.add_argument("--clearance", type=int, default=2)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--candidate-count", type=int, default=28)
    parser.add_argument("--alpha", type=float, default=0.5)
    return parser


async def _run(args: argparse.Namespace) -> None:
    settings = Settings()
    settings.require_ingestion_credentials()
    assert settings.cloudflare_account_id is not None
    assert settings.cloudflare_api_token is not None
    assert settings.pinecone_api_key is not None
    assert settings.pinecone_index is not None
    embedding = CloudflareEmbeddingModel(
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_api_token.get_secret_value(),
        model=settings.cloudflare_embedding_model,
        expected_dimensions=settings.cloudflare_embedding_dimensions,
        gateway_id=settings.cloudflare_ai_gateway_id,
    )
    rerank_client = AsyncPinecone(api_key=settings.pinecone_api_key.get_secret_value())
    retriever = await PineconeKnowledgeIndex.connect(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index,
        expected_dimensions=settings.cloudflare_embedding_dimensions,
        embedding_model=embedding,
        sparse_encoder=PineconeBM25Encoder.load(Path("data/index/bm25.json")),
        reranker=PineconeHostedReranker(rerank_client),
    )
    try:
        principal = Principal(
            subject="retrieval-cli",
            tenant_id=args.tenant,
            roles=frozenset({Role(args.role)}),
            departments=frozenset(args.department),
            clearance=args.clearance,
        )
        result = await retriever.search(
            args.query,
            derive_access_scope(principal),
            SearchOptions(
                limit=args.limit,
                candidate_count=args.candidate_count,
                alpha=args.alpha,
            ),
        )
        payload = {
            "degraded": result.degraded,
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "document_id": item.document_id,
                    "title": item.title,
                    "section": item.section,
                    "source_uri": str(item.source_uri),
                    "hybrid_score": item.hybrid_score,
                    "rerank_score": item.rerank_score,
                }
                for item in result.evidence
            ],
        }
        print(json.dumps(payload, indent=2))
    finally:
        await retriever.close()
        await rerank_client.close()
        await embedding.close()


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
