import argparse
import asyncio
import json
from pathlib import Path

from orysys.adapters.cloudflare.embeddings import CloudflareEmbeddingModel
from orysys.adapters.fakes import DeterministicEmbeddingModel, InMemoryVectorWriter
from orysys.adapters.pinecone.writer import PineconeVectorWriter
from orysys.config import get_settings
from orysys.ingestion.service import DocumentIngestion
from orysys.ingestion.sparse import PineconeBM25Encoder
from orysys.ports.ingestion import VectorIndexWriter
from orysys.ports.models import EmbeddingModel


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest an Orysys corpus manifest")
    parser.add_argument("--manifest", type=Path, default=Path("data/sample/manifest.json"))
    parser.add_argument("--bm25-output", type=Path, default=Path("data/index/bm25.json"))
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use configured Cloudflare and Pinecone services instead of deterministic fakes",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    cloudflare: CloudflareEmbeddingModel | None = None
    pinecone: PineconeVectorWriter | None = None
    embedding_model: EmbeddingModel
    index_writer: VectorIndexWriter
    if args.live:
        settings.require_ingestion_credentials()
        assert settings.cloudflare_account_id is not None
        assert settings.cloudflare_api_token is not None
        assert settings.pinecone_api_key is not None
        assert settings.pinecone_index is not None
        cloudflare = CloudflareEmbeddingModel(
            account_id=settings.cloudflare_account_id,
            api_token=settings.cloudflare_api_token.get_secret_value(),
            model=settings.cloudflare_embedding_model,
            expected_dimensions=settings.cloudflare_embedding_dimensions,
            gateway_id=settings.cloudflare_ai_gateway_id,
        )
        pinecone = await PineconeVectorWriter.connect(
            api_key=settings.pinecone_api_key.get_secret_value(),
            index_name=settings.pinecone_index,
            expected_dimensions=settings.cloudflare_embedding_dimensions,
        )
        embedding_model = cloudflare
        index_writer = pinecone
    else:
        embedding_model = DeterministicEmbeddingModel(
            dimension=settings.cloudflare_embedding_dimensions
        )
        index_writer = InMemoryVectorWriter()

    try:
        service = DocumentIngestion(
            embedding_model=embedding_model,
            sparse_encoder=PineconeBM25Encoder(),
            index_writer=index_writer,
        )
        report = await service.ingest(args.manifest, args.bm25_output)
        print(json.dumps(report.model_dump(mode="json"), indent=2))
    finally:
        if cloudflare:
            await cloudflare.close()
        if pinecone:
            await pinecone.close()


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
