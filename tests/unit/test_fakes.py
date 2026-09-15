import pytest

from orysys.adapters.fakes import DeterministicEmbeddingModel, ScriptedChatModel
from orysys.ports.models import MessageRole, ModelMessage, ModelRequest


@pytest.mark.asyncio
async def test_scripted_model_is_deterministic() -> None:
    model = ScriptedChatModel("grounded response")
    request = ModelRequest(messages=(ModelMessage(role=MessageRole.USER, content="question"),))

    result = await model.complete(request)
    chunks = [chunk async for chunk in model.stream(request)]

    assert result.text == "grounded response"
    assert "".join(chunks) == "grounded response "


@pytest.mark.asyncio
async def test_embedding_fake_has_stable_dimension() -> None:
    model = DeterministicEmbeddingModel(dimension=4)
    first, second = await model.embed(["same", "same"])
    assert first == second
    assert len(first) == 4
