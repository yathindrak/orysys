import os
from collections.abc import Iterator
from typing import Any

import streamlit as st

from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.evidence import Evidence
from orysys.domain.validation import ValidationResult
from orysys.ui.api_client import OrysysApiClient
from orysys.ui.design import render_activity_item, render_evidence, render_validation
from orysys.ui.design.icons import Icon
from orysys.ui.view_models import (
    ActivityItem,
    EvidenceCard,
    ValidationItem,
    activity_item,
    evidence_card,
    validation_item,
)

st.set_page_config(page_title="Orysys", page_icon=Icon.ASSISTANT, layout="wide")
st.title(f"{Icon.ASSISTANT} Orysys")
st.caption("Access-scoped enterprise knowledge assistant")


def _client() -> OrysysApiClient:
    existing = st.session_state.get("api_client")
    if isinstance(existing, OrysysApiClient):
        return existing
    client = OrysysApiClient(os.getenv("ORYSYS_API_URL", "http://localhost:8000"))
    st.session_state.api_client = client
    return client


def _conversation_id(client: OrysysApiClient) -> str:
    existing = st.session_state.get("conversation_id")
    if isinstance(existing, str):
        return existing
    conversation = client.create_conversation()
    st.session_state.conversation_id = conversation.conversation_id
    return conversation.conversation_id


def _messages() -> list[dict[str, str]]:
    existing = st.session_state.get("messages")
    if isinstance(existing, list):
        return existing
    messages: list[dict[str, str]] = []
    st.session_state.messages = messages
    return messages


def _response_stream(
    events: Iterator[ActivityEvent],
    status: Any,
    evidence: list[EvidenceCard],
    validations: list[ValidationItem],
) -> Iterator[str]:
    for event in events:
        activity: ActivityItem | None = activity_item(event)
        if activity is not None:
            render_activity_item(status, activity)
        if event.type is EventType.ANSWER_DELTA:
            text = event.public_payload.get("text")
            if isinstance(text, str):
                yield text
        elif event.type is EventType.ANSWER_COMPLETED:
            raw_evidence = event.public_payload.get("evidence", [])
            if isinstance(raw_evidence, list):
                evidence.extend(
                    evidence_card(Evidence.model_validate(item)) for item in raw_evidence
                )
        elif event.type is EventType.VALIDATION_COMPLETED:
            raw_results = event.public_payload.get("results", [])
            if isinstance(raw_results, list):
                validations.extend(
                    validation_item(ValidationResult.model_validate(item)) for item in raw_results
                )


api = _client()
conversation_id = _conversation_id(api)
messages = _messages()

with st.sidebar:
    st.subheader("Session")
    st.caption(f"Conversation: {conversation_id}")
    if st.button("New conversation", width="stretch"):
        conversation = api.create_conversation()
        st.session_state.conversation_id = conversation.conversation_id
        st.session_state.messages = []
        st.rerun()

for message in messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if prompt := st.chat_input("Ask about authorized policies, systems, or incidents"):
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        activity = st.status("Working", expanded=True)
        evidence_items: list[EvidenceCard] = []
        validation_items: list[ValidationItem] = []
        try:
            answer = st.write_stream(
                _response_stream(
                    api.stream_message(conversation_id, prompt),
                    activity,
                    evidence_items,
                    validation_items,
                ),
                cursor="▌",
            )
            answer_text = answer if isinstance(answer, str) else ""
            activity.update(label="Completed", state="complete", expanded=False)
        except Exception:
            answer_text = "The assistant is currently unavailable. Please try again."
            st.error(answer_text)
            activity.update(label="Failed", state="error", expanded=True)
        render_validation(validation_items)
        render_evidence(evidence_items)
    messages.append({"role": "assistant", "content": answer_text})
