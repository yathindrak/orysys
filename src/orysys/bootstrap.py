from dataclasses import dataclass

from orysys.adapters.fakes import (
    DeterministicEmbeddingModel,
    InMemoryKnowledgeIndex,
    ScriptedChatModel,
)
from orysys.config import Settings
from orysys.domain.errors import OrysysError
from orysys.ports.models import ChatModel, EmbeddingModel
from orysys.ports.retrieval import KnowledgeIndex


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
