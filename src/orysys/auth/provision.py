import asyncio
import json
from pathlib import Path
from typing import Any

import httpx2

from orysys.config import Settings

REALM = "orysys"
API_CLIENT = "orysys-api"
UI_CLIENT = "orysys-ui"


async def provision(settings: Settings) -> dict[str, object]:
    required = {
        "SKYCLOAK_AUTOMATION_CLIENT_ID": settings.skycloak_automation_client_id,
        "SKYCLOAK_AUTOMATION_CLIENT_SECRET": settings.skycloak_automation_client_secret,
        "SKYCLOAK_AUTOMATION_TOKEN_URL": settings.skycloak_automation_token_url,
        "ORYSYS_OIDC_CLIENT_SECRET": settings.oidc_client_secret,
        "ORYSYS_BOOTSTRAP_USER_PASSWORD": settings.bootstrap_user_password,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(f"Missing provisioning settings: {', '.join(sorted(missing))}")
    assert settings.skycloak_automation_client_id is not None
    assert settings.skycloak_automation_client_secret is not None
    assert settings.skycloak_automation_token_url is not None
    assert settings.oidc_client_secret is not None
    assert settings.bootstrap_user_password is not None

    token_url = settings.skycloak_automation_token_url
    base_url = token_url.split("/realms/", 1)[0]
    async with httpx2.AsyncClient(base_url=base_url, timeout=30.0) as client:
        token_response = await client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.skycloak_automation_client_id,
                "client_secret": settings.skycloak_automation_client_secret.get_secret_value(),
            },
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        realm_response = await client.get(f"/admin/realms/{REALM}", headers=headers)
        created_realm = realm_response.status_code == 404
        if created_realm:
            representation = _hosted_realm(settings.oidc_client_secret.get_secret_value())
            create_response = await client.post(
                "/admin/realms", headers=headers, json=representation
            )
            create_response.raise_for_status()
        else:
            realm_response.raise_for_status()

        api_client_id = await _client_uuid(client, headers, API_CLIENT)
        created_users: list[str] = []
        for username, role, clearance, departments in (
            ("viewer", "viewer", 1, ["payments"]),
            ("analyst", "analyst", 3, ["payments"]),
            ("administrator", "administrator", 8, ["payments", "security"]),
        ):
            user_id, created = await _ensure_user(
                client,
                headers,
                username=username,
                password=settings.bootstrap_user_password.get_secret_value(),
                clearance=clearance,
                departments=departments,
            )
            role_response = await client.get(
                f"/admin/realms/{REALM}/clients/{api_client_id}/roles/{role}",
                headers=headers,
            )
            role_response.raise_for_status()
            mapping_response = await client.post(
                f"/admin/realms/{REALM}/users/{user_id}/role-mappings/clients/{api_client_id}",
                headers=headers,
                json=[role_response.json()],
            )
            mapping_response.raise_for_status()
            if created:
                created_users.append(username)

    return {
        "realm": REALM,
        "created_realm": created_realm,
        "created_users": created_users,
        "issuer": f"{base_url}/realms/{REALM}",
        "clients": [API_CLIENT, UI_CLIENT],
    }


def _hosted_realm(client_secret: str) -> dict[str, Any]:
    path = Path("infra/keycloak/orysys-realm.json")
    representation: dict[str, Any] = json.loads(path.read_text())
    representation["users"] = []
    for client in representation["clients"]:
        if client["clientId"] == UI_CLIENT:
            client["secret"] = client_secret
    return representation


async def _client_uuid(client: httpx2.AsyncClient, headers: dict[str, str], client_id: str) -> str:
    response = await client.get(
        f"/admin/realms/{REALM}/clients", headers=headers, params={"clientId": client_id}
    )
    response.raise_for_status()
    matches = response.json()
    if not matches:
        raise RuntimeError(f"Missing configured client: {client_id}")
    return str(matches[0]["id"])


async def _ensure_user(
    client: httpx2.AsyncClient,
    headers: dict[str, str],
    *,
    username: str,
    password: str,
    clearance: int,
    departments: list[str],
) -> tuple[str, bool]:
    search = await client.get(
        f"/admin/realms/{REALM}/users",
        headers=headers,
        params={"username": username, "exact": "true"},
    )
    search.raise_for_status()
    matches = search.json()
    if matches:
        return str(matches[0]["id"]), False
    response = await client.post(
        f"/admin/realms/{REALM}/users",
        headers=headers,
        json={
            "username": username,
            "enabled": True,
            "emailVerified": True,
            "attributes": {
                "tenant_id": ["commercial-bank"],
                "departments": departments,
                "clearance": [str(clearance)],
            },
            "credentials": [{"type": "password", "value": password, "temporary": True}],
        },
    )
    response.raise_for_status()
    location = response.headers.get("location", "")
    user_id = location.rstrip("/").rsplit("/", 1)[-1]
    if not user_id:
        raise RuntimeError(f"Keycloak did not return an ID for {username}")
    return user_id, True


def main() -> None:
    report = asyncio.run(provision(Settings()))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
