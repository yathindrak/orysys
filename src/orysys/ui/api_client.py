import json
from collections.abc import Iterator

import httpx

from orysys.application.conversations import Conversation, ConversationSummary
from orysys.domain.approval import ApprovalProposal, ApprovalTicket
from orysys.domain.events import ActivityEvent
from orysys.domain.feedback import FeedbackItem


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

    def list_conversations(
        self, *, limit: int = 20, offset: int = 0
    ) -> tuple[ConversationSummary, ...]:
        response = self._client.get(
            "/v1/conversations",
            headers=self._headers,
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        items = response.json().get("conversations", [])
        return tuple(ConversationSummary.model_validate(item) for item in items)

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

    def list_tools(self) -> tuple[str, ...]:
        response = self._client.get("/v1/tools", headers=self._headers)
        response.raise_for_status()
        tools = response.json().get("tools", [])
        return tuple(str(item) for item in tools) if isinstance(tools, list) else ()

    def propose_action(self, *, target: str, reason: str) -> ApprovalTicket:
        response = self._client.post(
            "/v1/actions/proposals",
            headers=self._headers,
            json={
                "action": "simulate_service_restart",
                "target": target,
                "reason": reason,
            },
        )
        response.raise_for_status()
        return ApprovalTicket.model_validate(response.json()["ticket"])

    def decide_action(
        self,
        proposal_id: str,
        *,
        approval_token: str,
        confirm: bool,
    ) -> ApprovalProposal:
        response = self._client.post(
            f"/v1/actions/{proposal_id}/decision",
            headers=self._headers,
            json={"approval_token": approval_token, "confirm": confirm},
        )
        response.raise_for_status()
        return ApprovalProposal.model_validate(response.json()["proposal"])

    def submit_feedback(self, run_id: str, rating: int) -> FeedbackItem:
        response = self._client.post(
            "/v1/feedback",
            headers=self._headers,
            json={"run_id": run_id, "rating": rating, "route": "chat"},
        )
        response.raise_for_status()
        return FeedbackItem.model_validate(response.json()["feedback"])

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
