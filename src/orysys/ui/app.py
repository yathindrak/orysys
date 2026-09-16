import os
from collections.abc import Iterator
from typing import Any

import streamlit as st

from orysys.config import Settings
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

settings = Settings()


def _access_token() -> str | None:
    if not settings.auth_enabled:
        return None
    if not st.user.is_logged_in:
        if st.button("Log in with Skycloak", type="primary"):
            st.login("skycloak")
        st.stop()
    try:
        token = st.user.tokens["access"]
    except (KeyError, AttributeError):
        st.error("Skycloak did not return an access token.")
        st.stop()
    return str(token)


access_token = _access_token()


def _client() -> OrysysApiClient:
    existing = st.session_state.get("api_client")
    if isinstance(existing, OrysysApiClient):
        return existing
    client = OrysysApiClient(
        os.getenv("ORYSYS_API_URL", "http://localhost:8000"),
        access_token=access_token,
    )
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
        st.session_state.active_run_id = event.run_id
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
    if settings.auth_enabled and st.button("Log out", width="stretch"):
        st.logout()
    if st.button("New conversation", width="stretch"):
        conversation = api.create_conversation()
        st.session_state.conversation_id = conversation.conversation_id
        st.session_state.messages = []
        st.rerun()
    with st.expander("Admin action"):
        action_target = st.text_input("Service", value="search-api")
        action_reason = st.text_input("Reason", value="Assessment demonstration")
        if st.button("Request restart approval", width="stretch"):
            try:
                st.session_state.approval_ticket = api.propose_action(
                    target=action_target,
                    reason=action_reason,
                )
            except Exception:
                st.error("The approval request was rejected.")
        ticket = st.session_state.get("approval_ticket")
        if ticket is not None:
            st.warning("This simulated restart requires your explicit decision.")
            approve_column, deny_column = st.columns(2)
            if approve_column.button("Approve", type="primary", width="stretch"):
                try:
                    api.decide_action(
                        ticket.proposal.proposal_id,
                        approval_token=ticket.approval_token,
                        confirm=True,
                    )
                    st.success("Approved and simulated.")
                    del st.session_state.approval_ticket
                except Exception:
                    st.error("Approval failed or expired.")
            if deny_column.button("Deny", width="stretch"):
                try:
                    api.decide_action(
                        ticket.proposal.proposal_id,
                        approval_token=ticket.approval_token,
                        confirm=False,
                    )
                    st.info("Denied. No action was taken.")
                    del st.session_state.approval_ticket
                except Exception:
                    st.error("Denial failed or expired.")

for message in messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        run_id = message.get("run_id")
        if message["role"] == "assistant" and run_id:
            selection = st.feedback("thumbs", key=f"feedback-{run_id}")
            feedback_key = f"feedback-sent-{run_id}"
            if selection is not None and not st.session_state.get(feedback_key):
                try:
                    api.submit_feedback(run_id, 1 if selection == 1 else -1)
                    st.session_state[feedback_key] = True
                except Exception:
                    st.error("Feedback could not be saved.")

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
    messages.append(
        {
            "role": "assistant",
            "content": answer_text,
            "run_id": str(st.session_state.get("active_run_id", "")),
        }
    )
    st.rerun()
