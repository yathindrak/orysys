import pytest

from orysys.bootstrap import build_container
from orysys.config import Settings
from orysys.domain.errors import OrysysError


def test_baseline_composes_with_fake_adapters() -> None:
    container = build_container(Settings(environment="test", use_fake_adapters=True))
    assert container.settings.environment == "test"


def test_live_profile_fails_until_live_adapters_exist() -> None:
    with pytest.raises(OrysysError) as caught:
        build_container(Settings(environment="test", use_fake_adapters=False))

    assert caught.value.code == "live_adapters_not_configured"
