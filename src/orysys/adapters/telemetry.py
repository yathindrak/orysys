import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, Literal

import langsmith as ls
from langsmith.run_trees import RunTree

from orysys.domain.events import ActivityEvent
from orysys.observability import get_logger, redact

_current_run_id: ContextVar[str | None] = ContextVar("orysys_langsmith_run_id", default=None)
_current_tree: ContextVar[Any] = ContextVar("orysys_langsmith_tree", default=None)


class NoopTelemetry:
    @asynccontextmanager
    async def span(
        self, name: str, attributes: dict[str, object] | None = None
    ) -> AsyncIterator[None]:
        del name, attributes
        yield

    async def event(self, event: ActivityEvent) -> None:
        del event

    def flush(self) -> None:
        """No buffered runs; present so runtimes can flush uniformly."""


class LangSmithTelemetry:
    """Manual, redacted spans so graph state and document text never enter traces.

    The orysys.* spans created here are the entire trace surface: conversation,
    per-node agent transitions, retrieval status, tool calls, validation, and
    the final response. LangGraph/LangChain automatic instrumentation is
    deliberately disabled in ensure_langsmith_env() because it serializes the
    full graph state (evidence excerpts, principal subjects) into run inputs.
    """

    def __init__(self, *, api_key: str, project: str, enabled: bool) -> None:
        self._enabled = enabled
        self._project = project
        self._client = ls.Client(
            api_key=api_key,
            hide_inputs=_redact_dict,
            hide_outputs=_redact_dict,
            hide_metadata=_redact_dict,
        )
        self._logger = get_logger()

    @asynccontextmanager
    async def span(
        self, name: str, attributes: dict[str, object] | None = None
    ) -> AsyncIterator[None]:
        safe_attributes = _redact_dict(attributes or {})
        if not self._enabled:
            yield
            return
        # Post RunTrees directly instead of ls.trace(): the trace() helper
        # obeys the global tracing-enabled flag, while direct posts always
        # deliver. Auto-instrumentation stays disabled (see
        # ensure_langsmith_env) so raw graph state never enters LangSmith;
        # these redacted orysys.* spans are the complete trace surface.
        parent: RunTree | None = _current_tree.get()
        if parent is None:
            tree = RunTree(
                name=name,
                run_type=_run_type(name),
                inputs={"name": name},
                tags=["orysys", _short_tag(name)],
                extra={"metadata": safe_attributes},
                ls_client=self._client,
            )
            tree.session_name = self._project
        else:
            tree = parent.create_child(
                name=name,
                run_type=_run_type(name),
                inputs={"name": name},
                tags=["orysys", _short_tag(name)],
                extra={"metadata": safe_attributes},
            )
        await asyncio.to_thread(tree.post)
        run_token = _current_run_id.set(str(tree.id))
        tree_token = _current_tree.set(tree)
        try:
            yield
            tree.end(outputs={"status": "completed"})
        except Exception as error:
            tree.end(error=type(error).__name__)
            raise
        finally:
            _current_tree.reset(tree_token)
            _current_run_id.reset(run_token)
            await asyncio.to_thread(tree.patch)

    async def event(self, event: ActivityEvent) -> None:
        payload = _redact_dict(event.model_dump(mode="json"))
        trace_id = _current_run_id.get()
        if trace_id is not None:
            payload["langsmith_run_id"] = trace_id
        self._logger.info("activity_event", **payload)

    @property
    def project(self) -> str:
        return self._project

    @property
    def enabled(self) -> bool:
        return self._enabled

    def flush(self) -> None:
        """Block until buffered runs are delivered.

        Short-lived processes (CLIs, eval scripts) exit before the SDK's
        background batcher fires; without this their traces silently vanish.
        The long-lived API flushes continuously and rarely needs it.
        """

        if self._enabled:
            self._client.flush()


def current_run_id() -> str | None:
    """LangSmith run id of the innermost active span, if any."""
    return _current_run_id.get()


def ensure_langsmith_env(settings: Any) -> None:
    """Prepare os.environ for redacted manual tracing.

    Pydantic-settings reads .env itself, but the LangSmith SDK only looks at
    os.environ, so export the project/key for explicit manual spans. Automatic
    LangChain/LangGraph instrumentation is force-disabled: it serializes the
    full graph state (evidence excerpts, principal subjects, message history)
    into run inputs, which violates the metadata-only trace policy. The
    manual orysys.* spans (explicit client, redacted) push regardless of
    these flags and remain the complete evaluator-visible trace.
    """

    project = str(getattr(settings, "langsmith_project", "orysys-development"))
    key = getattr(settings, "langsmith_api_key", None)
    key_value = key.get_secret_value() if key is not None else None
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_TRACING"] = "false"
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    if key_value:
        os.environ.setdefault("LANGSMITH_API_KEY", key_value)


def _run_type(name: str) -> Literal["tool", "chain", "llm", "retriever"]:
    normalized = name.casefold()
    if ".tool." in normalized or normalized.endswith(".tool") or "mcp" in normalized:
        return "tool"
    if "retriev" in normalized or "rerank" in normalized or "embed" in normalized:
        return "retriever"
    if "chat" in normalized or "llm" in normalized or "model" in normalized:
        return "llm"
    return "chain"


def _short_tag(name: str) -> str:
    parts = name.split(".")
    return parts[-1][:32] if parts else "orysys"


def _redact_dict(value: dict[str, Any]) -> dict[str, Any]:
    result = redact(value)
    assert isinstance(result, dict)
    return result
