import json
from datetime import UTC, datetime, timedelta

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from orysys.adapters.oidc import OidcIdentityVerifier
from orysys.domain.errors import AuthenticationFailed, AuthenticationUnavailable
from orysys.domain.identity import Role


@pytest.mark.asyncio
async def test_oidc_verifies_fixed_algorithm_audience_and_client_roles() -> None:
    issuer = "https://identity.example.test/realms/orysys"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "key-1", "alg": "RS256", "use": "sig"})

    async def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx2.Response(
                200,
                json={"issuer": issuer, "jwks_uri": f"{issuer}/protocol/openid-connect/certs"},
            )
        return httpx2.Response(200, json={"keys": [jwk]})

    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": issuer,
            "aud": "orysys-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "tenant_id": "commercial-bank",
            "departments": ["payments"],
            "clearance": 3,
            "resource_access": {"orysys-api": {"roles": ["analyst"]}},
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    verifier = OidcIdentityVerifier(
        issuer=issuer,
        audience="orysys-api",
        client_id="orysys-api",
        client=client,
    )

    principal = await verifier.verify(token)

    assert principal.subject == "user-1"
    assert principal.tenant_id == "commercial-bank"
    assert principal.roles == frozenset({Role.ANALYST})
    assert principal.departments == frozenset({"payments"})

    forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        jwt.decode(token, options={"verify_signature": False}),
        forged_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    with pytest.raises(AuthenticationFailed):
        await verifier.verify(forged)
    await client.aclose()


@pytest.mark.asyncio
async def test_oidc_rejects_tokens_without_application_client_role() -> None:
    issuer = "https://identity.example.test/realms/orysys"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "key-1", "alg": "RS256"})

    async def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx2.Response(
                200,
                json={"issuer": issuer, "jwks_uri": f"{issuer}/certs"},
            )
        return httpx2.Response(200, json={"keys": [jwk]})

    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": issuer,
            "aud": "orysys-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "tenant_id": "commercial-bank",
            "resource_access": {"other-client": {"roles": ["administrator"]}},
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    verifier = OidcIdentityVerifier(
        issuer=issuer,
        audience="orysys-api",
        client_id="orysys-api",
        client=client,
    )

    with pytest.raises(AuthenticationFailed):
        await verifier.verify(token)
    await client.aclose()


@pytest.mark.asyncio
async def test_oidc_provider_failure_is_authentication_unavailable() -> None:
    issuer = "https://identity.example.test/realms/orysys"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": issuer,
            "aud": "orysys-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )

    async def unavailable(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503, request=request)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(unavailable))
    verifier = OidcIdentityVerifier(
        issuer=issuer,
        audience="orysys-api",
        client_id="orysys-api",
        client=client,
    )

    with pytest.raises(AuthenticationUnavailable):
        await verifier.verify(token)
    await client.aclose()
