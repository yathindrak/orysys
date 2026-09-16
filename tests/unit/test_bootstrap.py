import pytest

from orysys.bootstrap import build_container
from orysys.config import Settings
from orysys.domain.errors import OrysysError


def test_development_container_composes_with_fake_adapters() -> None:
    container = build_container(Settings(environment="test", use_fake_adapters=True))
    assert container.settings.environment == "test"


def test_development_container_directs_live_profile_to_async_runtime() -> None:
    with pytest.raises(OrysysError) as caught:
        build_container(Settings(environment="test", use_fake_adapters=False))

    assert caught.value.code == "async_live_runtime_required"
