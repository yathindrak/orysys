from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import langsmith as ls

from orysys.domain.events import ActivityEvent
from orysys.observability import get_logger, redact


class NoopTelemetry:
    @asynccontextmanager
    async def span(
        self, name: str, attributes: dict[str, object] | None = None
    ) -> AsyncIterator[None]:
        del name, attributes
        yield

    async def event(self, event: ActivityEvent) -> None:
        del event


class LangSmithTelemetry:
    """Manual, redacted spans so graph state and document text never enter traces."""

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
        with ls.trace(
            name,
            inputs=safe_attributes,
            metadata=safe_attributes,
            project_name=self._project,
            client=self._client,
        ) as run:
            try:
                yield
            except Exception as error:
                run.end(error=type(error).__name__)
                raise
            else:
                run.end(outputs={"status": "completed"})

    async def event(self, event: ActivityEvent) -> None:
        self._logger.info(
            "activity_event",
            **_redact_dict(event.model_dump(mode="json")),
        )


def _redact_dict(value: dict[str, Any]) -> dict[str, Any]:
    result = redact(value)
    assert isinstance(result, dict)
    return result
