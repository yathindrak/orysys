from pytest import MonkeyPatch

from orysys.config import Settings


def test_provider_secrets_use_documented_environment_names(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "secret-token")

    settings = Settings()

    assert settings.cloudflare_api_token is not None
    assert settings.cloudflare_api_token.get_secret_value() == "secret-token"
    assert "secret-token" not in repr(settings)
