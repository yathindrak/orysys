import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from orysys import __version__
from orysys.adapters.fakes import InMemoryKnowledgeIndex, ScriptedChatModel
from orysys.adapters.oidc import OidcIdentityVerifier
from orysys.api.schemas import (
    CreateConversationResponse,
    ErrorResponse,
    SendMessageRequest,
)
from orysys.api.sse import encode_sse
from orysys.application.assistant import AssistantRequest, AssistantRuntime
from orysys.application.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStore,
    InMemoryConversationStore,
)
from orysys.bootstrap import live_assistant_runtime
from orysys.config import Settings, get_settings
from orysys.domain.errors import (
    AuthenticationFailed,
    AuthorizationDenied,
    OrysysError,
    ResourceNotFound,
)
from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.identity import Principal, Role
from orysys.graph.runtime import DirectAssistantRuntime
from orysys.observability import configure_logging, get_logger, redact
from orysys.ports.models import MessageRole, ModelMessage
from orysys.ports.services import IdentityVerifier


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    version: str
    adapter_profile: str | None = None


def create_app(
    settings: Settings | None = None,
    *,
    runtime: AssistantRuntime | None = None,
    conversations: ConversationStore | None = None,
    principal: Principal | None = None,
    identity_verifier: IdentityVerifier | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    store = conversations or InMemoryConversationStore()
    active_principal = principal or _demo_principal(resolved)
    if resolved.environment == "production" and not resolved.auth_enabled:
        raise ValueError("Authentication must be enabled in production")
    resolved.require_auth_configuration()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.conversations = store
        verifier = identity_verifier
        owned_verifier: OidcIdentityVerifier | None = None
        if resolved.auth_enabled and verifier is None:
            assert resolved.keycloak_issuer is not None
            owned_verifier = OidcIdentityVerifier(
                issuer=resolved.keycloak_issuer,
                audience=resolved.keycloak_audience,
                client_id=resolved.keycloak_client_id,
                jwks_ttl_seconds=resolved.oidc_jwks_ttl_seconds,
            )
            verifier = owned_verifier
        app.state.identity_verifier = verifier
        if runtime is not None:
            app.state.runtime = runtime
        elif resolved.use_fake_adapters:
            app.state.runtime = DirectAssistantRuntime(
                chat_model=ScriptedChatModel("unused-with-empty-evidence"),
                knowledge_index=InMemoryKnowledgeIndex(),
            )
        try:
            if runtime is not None or resolved.use_fake_adapters:
                yield
            else:
                async with live_assistant_runtime(resolved) as live_runtime:
                    app.state.runtime = live_runtime
                    yield
        finally:
            if owned_verifier is not None:
                await owned_verifier.close()

    async def current_principal(request: Request) -> Principal:
        if not resolved.auth_enabled:
            return active_principal
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not token:
            raise AuthenticationFailed
        verifier: IdentityVerifier | None = request.app.state.identity_verifier
        if verifier is None:
            raise AuthenticationFailed
        return await verifier.verify(token)

    app = FastAPI(title="Orysys API", version=__version__, lifespan=lifespan)

    @app.get("/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/health/ready", response_model=HealthResponse)
    async def ready() -> HealthResponse:
        profile = "fake" if resolved.use_fake_adapters else "live"
        return HealthResponse(status="ready", version=__version__, adapter_profile=profile)

    @app.post(
        "/v1/conversations",
        response_model=CreateConversationResponse,
        status_code=201,
    )
    async def create_conversation(
        request_principal: Annotated[Principal, Depends(current_principal)],
    ) -> CreateConversationResponse:
        conversation = await store.create(request_principal)
        return CreateConversationResponse(conversation=conversation)

    @app.get("/v1/conversations/{conversation_id}", response_model=Conversation)
    async def get_conversation(
        conversation_id: str,
        request_principal: Annotated[Principal, Depends(current_principal)],
    ) -> Conversation:
        return await store.get(conversation_id, request_principal)

    @app.post("/v1/conversations/{conversation_id}/messages")
    async def send_message(
        conversation_id: str,
        body: SendMessageRequest,
        request: Request,
        request_principal: Annotated[Principal, Depends(current_principal)],
    ) -> StreamingResponse:
        conversation = await store.get(conversation_id, request_principal)
        await store.append(
            conversation_id,
            request_principal,
            ConversationMessage(role=MessageRole.USER, content=body.message),
        )
        assistant_request = AssistantRequest(
            request_id=body.request_id,
            thread_id=conversation_id,
            message=body.message,
            history=tuple(
                ModelMessage(role=item.role, content=item.content)
                for item in conversation.messages[-12:]
            ),
        )
        return StreamingResponse(
            _stream_run(
                request=request,
                assistant_request=assistant_request,
                runtime=app.state.runtime,
                store=store,
                principal=request_principal,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.exception_handler(OrysysError)
    async def handle_orysys_error(request: Request, error: OrysysError) -> JSONResponse:
        del request
        status_code = 400
        if isinstance(error, ResourceNotFound):
            status_code = 404
        elif isinstance(error, AuthenticationFailed):
            status_code = 401
        elif isinstance(error, AuthorizationDenied):
            status_code = 403
        elif error.retryable:
            status_code = 503
        payload = ErrorResponse(
            code=error.code,
            message=error.public_message,
            retryable=error.retryable,
        )
        headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
        return JSONResponse(
            status_code=status_code,
            content=payload.model_dump(mode="json"),
            headers=headers,
        )

    return app


async def _stream_run(
    *,
    request: Request,
    assistant_request: AssistantRequest,
    runtime: AssistantRuntime,
    store: ConversationStore,
    principal: Principal,
) -> AsyncIterator[bytes]:
    answer_parts: list[str] = []
    sequence = 0
    run_id = str(uuid4())
    logger = get_logger()
    event_stream = runtime.stream(assistant_request, principal)
    try:
        async for event in event_stream:
            if await request.is_disconnected():
                logger.info(
                    "sse_disconnected",
                    **redact(
                        {
                            "request_id": assistant_request.request_id,
                            "thread_id": assistant_request.thread_id,
                        }
                    ),
                )
                return
            sequence = event.sequence + 1
            run_id = event.run_id
            if event.type is EventType.ANSWER_DELTA:
                text = event.public_payload.get("text")
                if isinstance(text, str):
                    answer_parts.append(text)
            yield encode_sse(event)
        answer = "".join(answer_parts).strip()
        if answer:
            await store.append(
                assistant_request.thread_id,
                principal,
                ConversationMessage(role=MessageRole.ASSISTANT, content=answer),
            )
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.exception(
            "assistant_stream_failed",
            **redact(
                {
                    "request_id": assistant_request.request_id,
                    "thread_id": assistant_request.thread_id,
                    "error_type": type(error).__name__,
                }
            ),
        )
        event = ActivityEvent(
            sequence=sequence,
            request_id=assistant_request.request_id,
            run_id=run_id,
            thread_id=assistant_request.thread_id,
            type=EventType.RUN_FAILED,
            public_payload={"message": "The assistant run could not be completed."},
        )
        yield encode_sse(event)
    finally:
        if isinstance(event_stream, AsyncGenerator):
            await event_stream.aclose()


def _demo_principal(settings: Settings) -> Principal:
    departments = frozenset(
        item.strip() for item in settings.demo_departments.split(",") if item.strip()
    )
    return Principal(
        subject=settings.demo_subject,
        tenant_id=settings.demo_tenant_id,
        roles=frozenset({Role(settings.demo_role)}),
        departments=departments,
        clearance=settings.demo_clearance,
    )
