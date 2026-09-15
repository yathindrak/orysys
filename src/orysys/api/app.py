from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from orysys import __version__
from orysys.bootstrap import build_container
from orysys.config import Settings, get_settings


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    version: str
    adapter_profile: str | None = None


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(title="Orysys API", version=__version__)
    app.state.container = build_container(resolved)

    @app.get("/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/health/ready", response_model=HealthResponse)
    async def ready() -> HealthResponse:
        profile = "fake" if resolved.use_fake_adapters else "live"
        return HealthResponse(status="ready", version=__version__, adapter_profile=profile)

    return app
