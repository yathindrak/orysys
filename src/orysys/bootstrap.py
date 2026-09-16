from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pinecone import AsyncPinecone

from orysys.adapters.cloudflare.chat import CloudflareChatModel
from orysys.adapters.cloudflare.embeddings import CloudflareEmbeddingModel
from orysys.adapters.fakes import (
    DeterministicEmbeddingModel,
    InMemoryKnowledgeIndex,
    ScriptedChatModel,
)
from orysys.adapters.mcp_client import McpDirectoryClient
from orysys.adapters.model_research import ModelResearchPlanner, ModelResearchWorker
from orysys.adapters.pinecone.reranker import PineconeHostedReranker
from orysys.adapters.pinecone.retrieval import PineconeKnowledgeIndex
from orysys.adapters.telemetry import LangSmithTelemetry, NoopTelemetry
from orysys.config import Settings
from orysys.domain.errors import OrysysError
from orysys.graph.runtime import DirectAssistantRuntime
from orysys.ingestion.sparse import PineconeBM25Encoder
from orysys.ports.models import ChatModel, EmbeddingModel
from orysys.ports.retrieval import KnowledgeIndex, SearchOptions
from orysys.ports.services import Telemetry
from orysys.research.runtime import ResearchAssistantRuntime, RoutingAssistantRuntime
from orysys.tools.gateway import AuthorizedToolGateway
from orysys.tools.handlers import IncidentAnalyticsTool, KnowledgeSearchTool, McpReadTool


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    settings: Settings
    chat_model: ChatModel
    embedding_model: EmbeddingModel
    knowledge_index: KnowledgeIndex


def build_container(settings: Settings) -> ApplicationContainer:
    """Construct process-scoped dependencies in one reviewable location."""

    if not settings.use_fake_adapters:
        raise OrysysError(
            "live_adapters_not_configured",
            "Live adapters have not been implemented for this baseline.",
        )
    return ApplicationContainer(
        settings=settings,
        chat_model=ScriptedChatModel("No product workflow has been configured yet."),
        embedding_model=DeterministicEmbeddingModel(),
        knowledge_index=InMemoryKnowledgeIndex(),
    )


@asynccontextmanager
async def live_assistant_runtime(settings: Settings) -> AsyncIterator[RoutingAssistantRuntime]:
    """Compose and close the provider-backed direct-answer runtime."""

    settings.require_ingestion_credentials()
    settings.require_chat_credentials()
    assert settings.cloudflare_account_id is not None
    assert settings.cloudflare_api_token is not None
    assert settings.pinecone_api_key is not None
    assert settings.pinecone_index is not None

    cloudflare_token = settings.cloudflare_api_token.get_secret_value()
    embedding = CloudflareEmbeddingModel(
        account_id=settings.cloudflare_account_id,
        api_token=cloudflare_token,
        model=settings.cloudflare_embedding_model,
        expected_dimensions=settings.cloudflare_embedding_dimensions,
        gateway_id=settings.cloudflare_ai_gateway_id,
    )
    chat = CloudflareChatModel(
        account_id=settings.cloudflare_account_id,
        api_token=cloudflare_token,
        model=settings.cloudflare_chat_model,
        max_tokens=settings.cloudflare_chat_max_tokens,
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
    telemetry: Telemetry = NoopTelemetry()
    if settings.langsmith_api_key is not None:
        telemetry = LangSmithTelemetry(
            api_key=settings.langsmith_api_key.get_secret_value(),
            project=settings.langsmith_project,
            enabled=settings.langsmith_tracing,
        )
    try:
        async with AsyncExitStack() as stack:
            checkpointer = None
            if settings.database_url is not None:
                checkpointer = await stack.enter_async_context(
                    AsyncPostgresSaver.from_conn_string(
                        settings.database_url.get_secret_value(),
                        serde=_checkpoint_serializer(),
                    )
                )
                await checkpointer.setup()
            direct = DirectAssistantRuntime(
                chat_model=chat,
                knowledge_index=retriever,
                search_options=SearchOptions(limit=12, candidate_count=28, alpha=0.5),
                telemetry=telemetry,
                checkpointer=checkpointer,
            )
            research = ResearchAssistantRuntime(
                planner=ModelResearchPlanner(chat),
                worker=ModelResearchWorker(chat),
                knowledge_index=retriever,
                telemetry=telemetry,
                checkpointer=checkpointer,
            )
            tools = AuthorizedToolGateway(
                [
                    KnowledgeSearchTool(retriever),
                    IncidentAnalyticsTool(),
                    McpReadTool(McpDirectoryClient(settings.mcp_server_url)),
                ],
                telemetry=telemetry,
            )
            yield RoutingAssistantRuntime(direct=direct, research=research, tools=tools)
    finally:
        await retriever.close()
        await rerank_client.close()
        await chat.close()
        await embedding.close()


def _checkpoint_serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(
        pickle_fallback=False,
        allowed_msgpack_modules={
            ("orysys.application.assistant", "AssistantRequest"),
            ("orysys.domain.events", "ActivityEvent"),
            ("orysys.domain.events", "EventType"),
            ("orysys.domain.evidence", "Claim"),
            ("orysys.domain.evidence", "Evidence"),
            ("orysys.domain.evidence", "GroundedAnswer"),
            ("orysys.domain.identity", "AccessScope"),
            ("orysys.domain.identity", "Principal"),
            ("orysys.domain.identity", "Role"),
            ("orysys.domain.plans", "ResearchPlan"),
            ("orysys.domain.plans", "RunBudget"),
            ("orysys.domain.research", "Finding"),
            ("orysys.domain.research", "ResearchBatch"),
            ("orysys.domain.research", "WorkerOutcome"),
            ("orysys.domain.research", "WorkerStatus"),
            ("orysys.domain.validation", "ValidationResult"),
            ("orysys.ports.models", "ModelMessage"),
            ("orysys.ports.models", "MessageRole"),
        },
    )
