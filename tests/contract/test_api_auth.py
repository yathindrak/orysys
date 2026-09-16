import pytest
from fastapi.testclient import TestClient

from orysys.api.app import create_app
from orysys.config import Settings
from orysys.domain.errors import AuthenticationFailed
from orysys.domain.identity import Principal, Role


class TokenVerifier:
    async def verify(self, token: str) -> Principal:
        if token == "user-one":
            return Principal(
                subject="user-1",
                tenant_id="tenant-1",
                roles=frozenset({Role.VIEWER}),
            )
        if token == "user-two":
            return Principal(
                subject="user-2",
                tenant_id="tenant-2",
                roles=frozenset({Role.ADMINISTRATOR}),
            )
        raise AuthenticationFailed


@pytest.fixture
def authenticated_app() -> TestClient:
    settings = Settings(
        environment="test",
        use_fake_adapters=True,
        auth_enabled=True,
        keycloak_issuer="https://identity.example.test/realms/orysys",
    )
    return TestClient(create_app(settings, identity_verifier=TokenVerifier()))


def test_api_requires_bearer_token(authenticated_app: TestClient) -> None:
    with authenticated_app as client:
        response = client.post("/v1/conversations")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["code"] == "authentication_failed"


def test_conversation_owner_and_tenant_come_only_from_verified_token(
    authenticated_app: TestClient,
) -> None:
    with authenticated_app as client:
        created = client.post("/v1/conversations", headers={"Authorization": "Bearer user-one"})
        conversation_id = created.json()["conversation"]["conversation_id"]
        denied = client.get(
            f"/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer user-two"},
        )
        spoof = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            headers={"Authorization": "Bearer user-one"},
            json={"message": "hello", "role": "administrator", "tenant_id": "tenant-2"},
        )

    assert created.status_code == 201
    assert denied.status_code == 404
    assert spoof.status_code == 422
