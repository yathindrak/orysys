import asyncio
import time
from typing import Any

import httpx2
import jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from orysys.domain.errors import AuthenticationFailed, AuthenticationUnavailable
from orysys.domain.identity import Principal, Role


class _Discovery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    issuer: str
    jwks_uri: str


class _Jwks(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keys: list[dict[str, Any]]


class _RealmAccess(BaseModel):
    model_config = ConfigDict(extra="ignore")

    roles: list[str] = Field(default_factory=list)


class _ClientAccess(BaseModel):
    model_config = ConfigDict(extra="ignore")

    roles: list[str] = Field(default_factory=list)


class _Claims(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    departments: list[str] = Field(default_factory=list)
    clearance: int = Field(default=0, ge=0, le=10)
    realm_access: _RealmAccess = Field(default_factory=_RealmAccess)
    resource_access: dict[str, _ClientAccess] = Field(default_factory=dict)


class OidcIdentityVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        client_id: str,
        jwks_ttl_seconds: int = 300,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._client_id = client_id
        self._ttl = jwks_ttl_seconds
        self._client = client or httpx2.AsyncClient(timeout=httpx2.Timeout(10.0, connect=5.0))
        self._owns_client = client is None
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise AuthenticationFailed
            kid = header["kid"]
            key = await self._key(kid)
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
            claims = _Claims.model_validate(payload)
            client_roles = claims.resource_access.get(self._client_id, _ClientAccess()).roles
            known_roles = {role.value for role in Role}
            roles = frozenset(Role(item) for item in client_roles if item in known_roles)
            if not roles:
                raise AuthenticationFailed
            return Principal(
                subject=claims.sub,
                tenant_id=claims.tenant_id,
                roles=roles,
                departments=frozenset(claims.departments),
                clearance=claims.clearance,
            )
        except AuthenticationUnavailable:
            raise
        except (jwt.PyJWTError, ValidationError, ValueError, KeyError) as error:
            raise AuthenticationFailed from error

    async def _key(self, kid: str) -> Any:
        if time.monotonic() >= self._expires_at or kid not in self._keys:
            await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            await self._refresh(force=True)
            key = self._keys.get(kid)
        if key is None:
            raise AuthenticationFailed
        return key

    async def _refresh(self, *, force: bool = False) -> None:
        async with self._lock:
            if not force and time.monotonic() < self._expires_at and self._keys:
                return
            try:
                discovery_response = await self._client.get(
                    f"{self._issuer}/.well-known/openid-configuration"
                )
                discovery_response.raise_for_status()
                discovery = _Discovery.model_validate(discovery_response.json())
                if discovery.issuer.rstrip("/") != self._issuer:
                    raise AuthenticationUnavailable
                jwks_response = await self._client.get(discovery.jwks_uri)
                jwks_response.raise_for_status()
                jwks = _Jwks.model_validate(jwks_response.json())
                self._keys = {
                    item["kid"]: jwt.PyJWK.from_dict(item).key
                    for item in jwks.keys
                    if isinstance(item.get("kid"), str) and item.get("alg", "RS256") == "RS256"
                }
                self._expires_at = time.monotonic() + self._ttl
            except AuthenticationUnavailable:
                raise
            except (httpx2.HTTPError, ValidationError, ValueError, KeyError) as error:
                raise AuthenticationUnavailable from error

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
