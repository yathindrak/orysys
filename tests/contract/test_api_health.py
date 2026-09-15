from fastapi.testclient import TestClient

from orysys.api.app import create_app
from orysys.config import Settings


def test_health_contracts() -> None:
    client = TestClient(create_app(Settings(environment="test", use_fake_adapters=True)))

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok", "version": "0.1.0", "adapter_profile": None}
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "version": "0.1.0",
        "adapter_profile": "fake",
    }
