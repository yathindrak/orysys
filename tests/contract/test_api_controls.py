import pytest
from fastapi.testclient import TestClient

from orysys.api.app import create_app
from orysys.config import Settings
from orysys.domain.errors import AuthenticationFailed, RateLimitUnavailable
from orysys.domain.identity import Principal, Role
from orysys.domain.security import RateLimitDecision


class SameTenantVerifier:
    async def verify(self, token: str) -> Principal:
        roles = {
            "viewer": frozenset({Role.VIEWER}),
            "admin": frozenset({Role.ADMINISTRATOR}),
            "other-admin": frozenset({Role.ADMINISTRATOR}),
        }
        if token not in roles:
            raise AuthenticationFailed
        return Principal(subject=token, tenant_id="tenant-1", roles=roles[token])


def _client(**kwargs: object) -> TestClient:
    settings = Settings(
        environment="test",
        use_fake_adapters=True,
        auth_enabled=True,
        keycloak_issuer="https://identity.example.test/realms/orysys",
    )
    return TestClient(create_app(settings, identity_verifier=SameTenantVerifier(), **kwargs))


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_approval_api_rejects_viewer_wrong_identity_and_replay() -> None:
    with _client() as client:
        denied = client.post(
            "/v1/actions/proposals",
            headers=_auth("viewer"),
            json={
                "action": "simulate_service_restart",
                "target": "search-api",
                "reason": "deploy",
            },
        )
        created = client.post(
            "/v1/actions/proposals",
            headers=_auth("admin"),
            json={
                "action": "simulate_service_restart",
                "target": "search-api",
                "reason": "deploy",
            },
        )
        ticket = created.json()["ticket"]
        proposal_id = ticket["proposal"]["proposal_id"]
        body = {"approval_token": ticket["approval_token"], "confirm": True}
        wrong_identity = client.post(
            f"/v1/actions/{proposal_id}/decision",
            headers=_auth("other-admin"),
            json=body,
        )
        approved = client.post(
            f"/v1/actions/{proposal_id}/decision",
            headers=_auth("admin"),
            json=body,
        )
        replay = client.post(
            f"/v1/actions/{proposal_id}/decision",
            headers=_auth("admin"),
            json=body,
        )

    assert denied.status_code == 403
    assert created.status_code == 201
    assert wrong_identity.status_code == 404
    assert approved.json()["proposal"]["status"] == "approved"
    assert replay.status_code == 400
    assert replay.json()["code"] == "approval_replayed"


def test_feedback_api_is_idempotent_and_admin_reviewed() -> None:
    body = {
        "run_id": "run-1",
        "trace_id": "trace-1",
        "rating": 1,
        "note": "useful",
        "route": "direct",
    }
    with _client() as client:
        first = client.post("/v1/feedback", headers=_auth("viewer"), json=body)
        duplicate = client.post("/v1/feedback", headers=_auth("viewer"), json=body)
        feedback_id = first.json()["feedback"]["feedback_id"]
        viewer_review = client.post(f"/v1/feedback/{feedback_id}/review", headers=_auth("viewer"))
        reviewed = client.post(f"/v1/feedback/{feedback_id}/review", headers=_auth("admin"))

    assert first.status_code == 201
    assert duplicate.json()["feedback"]["feedback_id"] == feedback_id
    assert viewer_review.status_code == 403
    assert reviewed.json()["feedback"]["status"] == "reviewed"


class DenyingLimiter:
    async def consume(self, subject: str, cost: int = 1) -> RateLimitDecision:
        del subject, cost
        return RateLimitDecision(allowed=False, retry_after_seconds=7, remaining=0)


class UnavailableLimiter:
    async def consume(self, subject: str, cost: int = 1) -> RateLimitDecision:
        del subject, cost
        raise RateLimitUnavailable


def test_api_returns_429_and_retry_after_when_rate_limited() -> None:
    with _client(rate_limiter=DenyingLimiter()) as client:
        response = client.post("/v1/conversations", headers=_auth("viewer"))

    assert response.status_code == 429
    assert response.headers["retry-after"] == "7"
    assert response.json()["code"] == "rate_limit_exceeded"


def test_api_fails_closed_when_shared_limiter_is_unavailable() -> None:
    with _client(rate_limiter=UnavailableLimiter()) as client:
        response = client.post("/v1/conversations", headers=_auth("viewer"))

    assert response.status_code == 503
    assert response.json()["code"] == "rate_limit_unavailable"


def test_production_rejects_fake_adapters() -> None:
    settings = Settings(
        environment="production",
        use_fake_adapters=True,
        auth_enabled=True,
        keycloak_issuer="https://identity.example.test/realms/orysys",
        upstash_redis_rest_url="https://redis.example.test",
        upstash_redis_rest_token="test-token",
        langsmith_api_key=None,
        langsmith_tracing=False,
    )

    try:
        create_app(settings)
    except ValueError as error:
        assert str(error) == "Fake adapters are not permitted in production"
    else:
        raise AssertionError("production accepted fake adapters")


def test_production_requires_langsmith_tracing() -> None:
    settings = Settings(
        environment="production",
        use_fake_adapters=False,
        auth_enabled=True,
        keycloak_issuer="https://identity.example.test/realms/orysys",
        upstash_redis_rest_url="https://redis.example.test",
        upstash_redis_rest_token="test-token",
        langsmith_api_key=None,
        langsmith_tracing=False,
    )

    with pytest.raises(ValueError, match="LangSmith tracing must be configured in production"):
        create_app(settings)
