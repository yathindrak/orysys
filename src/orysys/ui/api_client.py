import json
from collections.abc import Iterator

import httpx

from orysys.application.conversations import Conversation
from orysys.domain.events import ActivityEvent


class OrysysApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        access_token: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        self._headers = headers
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(90.0, connect=10.0),
        )

    def create_conversation(self) -> Conversation:
        response = self._client.post("/v1/conversations", headers=self._headers)
        response.raise_for_status()
        return Conversation.model_validate(response.json()["conversation"])

    def get_conversation(self, conversation_id: str) -> Conversation:
        response = self._client.get(f"/v1/conversations/{conversation_id}", headers=self._headers)
        response.raise_for_status()
        return Conversation.model_validate(response.json())

    def stream_message(self, conversation_id: str, message: str) -> Iterator[ActivityEvent]:
        with self._client.stream(
            "POST",
            f"/v1/conversations/{conversation_id}/messages",
            headers=self._headers,
            json={"message": message},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    yield ActivityEvent.model_validate(json.loads(line[6:]))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
