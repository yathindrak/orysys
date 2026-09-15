import argparse
import asyncio
import json
from pathlib import Path

from pinecone import AsyncPinecone
from pydantic import BaseModel, ConfigDict, TypeAdapter

from orysys.adapters.cloudflare.embeddings import CloudflareEmbeddingModel
from orysys.adapters.fakes import IdentityReranker
from orysys.adapters.pinecone.reranker import PineconeHostedReranker
from orysys.adapters.pinecone.retrieval import PineconeKnowledgeIndex
from orysys.config import Settings
from orysys.domain.identity import Principal, Role
from orysys.domain.policy import derive_access_scope
from orysys.ingestion.sparse import PineconeBM25Encoder
from orysys.ports.retrieval import Reranker, SearchOptions


class EvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    query: str
    relevant_documents: frozenset[str]
    minimum_access_level: int | None = None


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_version: str
    cases: tuple[EvaluationCase, ...]


class CaseResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    retrieved_documents: tuple[str, ...]
    recall_at_k: float | None
    reciprocal_rank: float | None
    leakage_detected: bool
    degraded: bool


class ConfigurationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    alpha: float
    reranker: str
    mean_recall_at_k: float
    mean_reciprocal_rank: float
    leakage_count: int
    cases: tuple[CaseResult, ...]


class RetrievalEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_version: str
    namespace: str
    limit: int
    candidate_count: int
    configurations: tuple[ConfigurationResult, ...]


def _load_dataset(path: Path) -> EvaluationDataset:
    return TypeAdapter(EvaluationDataset).validate_json(path.read_text(encoding="utf-8"))


async def _evaluate_configuration(
    *,
    name: str,
    alpha: float,
    reranker_name: str,
    reranker: Reranker,
    settings: Settings,
    embedding: CloudflareEmbeddingModel,
    dataset: EvaluationDataset,
    principal: Principal,
    limit: int,
    candidate_count: int,
) -> ConfigurationResult:
    assert settings.pinecone_api_key is not None
    assert settings.pinecone_index is not None
    retriever = await PineconeKnowledgeIndex.connect(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index,
        expected_dimensions=settings.cloudflare_embedding_dimensions,
        embedding_model=embedding,
        sparse_encoder=PineconeBM25Encoder.load(Path("data/index/bm25.json")),
        reranker=reranker,
    )
    scope = derive_access_scope(principal)
    case_results: list[CaseResult] = []
    try:
        for case in dataset.cases:
            result = await retriever.search(
                case.query,
                scope,
                SearchOptions(limit=limit, candidate_count=candidate_count, alpha=alpha),
            )
            documents = tuple(dict.fromkeys(item.document_id for item in result.evidence))
            restricted = bool(
                case.minimum_access_level and case.minimum_access_level > principal.clearance
            )
            leakage = restricted and bool(set(documents) & case.relevant_documents)
            if restricted:
                recall = reciprocal_rank = None
            else:
                recall = len(set(documents) & case.relevant_documents) / len(
                    case.relevant_documents
                )
                reciprocal_rank = next(
                    (
                        1 / rank
                        for rank, document_id in enumerate(documents, start=1)
                        if document_id in case.relevant_documents
                    ),
                    0.0,
                )
            case_results.append(
                CaseResult(
                    case_id=case.id,
                    retrieved_documents=documents,
                    recall_at_k=recall,
                    reciprocal_rank=reciprocal_rank,
                    leakage_detected=leakage,
                    degraded=result.degraded,
                )
            )
    finally:
        await retriever.close()

    measured = [case for case in case_results if case.recall_at_k is not None]
    return ConfigurationResult(
        name=name,
        alpha=alpha,
        reranker=reranker_name,
        mean_recall_at_k=sum(case.recall_at_k or 0 for case in measured) / len(measured),
        mean_reciprocal_rank=sum(case.reciprocal_rank or 0 for case in measured) / len(measured),
        leakage_count=sum(case.leakage_detected for case in case_results),
        cases=tuple(case_results),
    )


async def run(output: Path, dataset_path: Path) -> RetrievalEvaluationReport:
    settings = Settings()
    settings.require_ingestion_credentials()
    assert settings.cloudflare_account_id is not None
    assert settings.cloudflare_api_token is not None
    assert settings.pinecone_api_key is not None
    embedding = CloudflareEmbeddingModel(
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_api_token.get_secret_value(),
        model=settings.cloudflare_embedding_model,
        expected_dimensions=settings.cloudflare_embedding_dimensions,
        gateway_id=settings.cloudflare_ai_gateway_id,
    )
    rerank_client = AsyncPinecone(api_key=settings.pinecone_api_key.get_secret_value())
    dataset = _load_dataset(dataset_path)
    principal = Principal(
        subject="retrieval-evaluator",
        tenant_id="commercial-bank",
        roles=frozenset({Role.ANALYST}),
        departments=frozenset({"payments"}),
        clearance=2,
    )
    limit = 8
    candidate_count = 28
    try:
        configurations = (
            await _evaluate_configuration(
                name="dense-only",
                alpha=1.0,
                reranker_name="none",
                reranker=IdentityReranker(),
                settings=settings,
                embedding=embedding,
                dataset=dataset,
                principal=principal,
                limit=limit,
                candidate_count=candidate_count,
            ),
            await _evaluate_configuration(
                name="hybrid",
                alpha=0.5,
                reranker_name="none",
                reranker=IdentityReranker(),
                settings=settings,
                embedding=embedding,
                dataset=dataset,
                principal=principal,
                limit=limit,
                candidate_count=candidate_count,
            ),
            await _evaluate_configuration(
                name="hybrid-reranked",
                alpha=0.5,
                reranker_name="bge-reranker-v2-m3",
                reranker=PineconeHostedReranker(rerank_client),
                settings=settings,
                embedding=embedding,
                dataset=dataset,
                principal=principal,
                limit=limit,
                candidate_count=candidate_count,
            ),
        )
    finally:
        await rerank_client.close()
        await embedding.close()
    report = RetrievalEvaluationReport(
        corpus_version=dataset.corpus_version,
        namespace=principal.tenant_id,
        limit=limit,
        candidate_count=candidate_count,
        configurations=configurations,
    )
    await asyncio.to_thread(_write_report, output, report)
    return report


def _write_report(path: Path, report: RetrievalEvaluationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate live Orysys retrieval")
    parser.add_argument("--dataset", type=Path, default=Path("data/sample/evaluation.json"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/results/retrieval-bank-demo-v1.json"),
    )
    args = parser.parse_args()
    report = asyncio.run(run(args.output, args.dataset))
    print(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
