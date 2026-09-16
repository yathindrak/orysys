import os
from typing import Any

import streamlit as st

from orysys.config import Settings
from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.evidence import Evidence
from orysys.domain.policy import ADMIN_ACTION
from orysys.domain.validation import ValidationResult
from orysys.ui.api_client import OrysysApiClient
from orysys.ui.design import (
    render_activity_item,
    render_evidence,
    render_login_screen,
    render_suggested_prompts,
    render_validation,
)
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

settings = Settings()


def _access_token() -> str | None:
    if not settings.auth_enabled:
        return None
    if not st.user.is_logged_in:
        if render_login_screen(provider_label="Skycloak"):
            st.login("skycloak")
        st.stop()
    try:
        token = st.user.tokens["access"]
    except (KeyError, AttributeError):
        st.error("Skycloak did not return an access token.")
        st.stop()
    return str(token)


access_token = _access_token()

st.title(f"{Icon.ASSISTANT} Orysys")
st.caption("Access-scoped enterprise knowledge assistant")


def _client() -> OrysysApiClient:
    existing = st.session_state.get("api_client")
    cached_token = st.session_state.get("api_client_token")
    if isinstance(existing, OrysysApiClient) and cached_token == access_token:
        return existing
    # The access token rotates on refresh and changes across logins. Never reuse
    # a client bound to a previous token: the API rejects it with 401 and the
    # app would show a raw traceback instead of working.
    client = OrysysApiClient(
        os.getenv("ORYSYS_API_URL", "http://localhost:8000"),
        access_token=access_token,
    )
    st.session_state.api_client = client
    st.session_state.api_client_token = access_token
    # A new identity must not inherit the previous identity's conversation.
    if cached_token != access_token:
        st.session_state.pop("conversation_id", None)
    return client


def _conversation_id(client: OrysysApiClient) -> str:
    existing = st.session_state.get("conversation_id")
    if isinstance(existing, str):
        return existing
    try:
        conversation = client.create_conversation()
    except Exception as error:
        _handle_conversation_error(error)
        st.stop()
    st.session_state.conversation_id = conversation.conversation_id
    return conversation.conversation_id


def _handle_conversation_error(error: Exception) -> None:
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status == 401:
        st.session_state.pop("api_client", None)
        st.session_state.pop("api_client_token", None)
        st.session_state.pop("conversation_id", None)
        st.error(
            "Your session expired or is not recognized by the API. Please log out and log back in."
        )
        if settings.auth_enabled and st.button("Log out", key="relogin"):
            _logout()
        return
    if status == 403:
        st.error("Your account is not authorized to start conversations.")
        return
    st.error("The assistant is currently unavailable. Please try again.")


def _messages() -> list[dict[str, str]]:
    existing = st.session_state.get("messages")
    if isinstance(existing, list):
        return existing
    messages: list[dict[str, str]] = []
    st.session_state.messages = messages
    return messages


def _logout() -> None:
    for key in (
        "api_client",
        "api_client_token",
        "allowed_tools",
        "allowed_tools_token",
        "conversation_id",
        "messages",
        "active_run_id",
    ):
        st.session_state.pop(key, None)
    st.logout()


def _allowed_tools(client: OrysysApiClient) -> tuple[str, ...]:
    """Ask the server which tools this identity may use. Fail closed on error."""
    token = st.session_state.get("api_client_token")
    cached = st.session_state.get("allowed_tools")
    cached_token = st.session_state.get("allowed_tools_token")
    if isinstance(cached, tuple) and cached_token == token:
        return cached
    try:
        tools = client.list_tools()
    except Exception:
        tools = ()
    st.session_state.allowed_tools = tools
    st.session_state.allowed_tools_token = token
    return tools


def _start_new_conversation(client: OrysysApiClient) -> None:
    try:
        conversation = client.create_conversation()
    except Exception:
        # Callbacks cannot render widgets, so drop the failed state and let the
        # main flow retry via _conversation_id, which displays the error.
        st.session_state.pop("api_client", None)
        st.session_state.pop("api_client_token", None)
        st.session_state.pop("conversation_id", None)
        return
    st.session_state.conversation_id = conversation.conversation_id
    existing_messages = st.session_state.get("messages")
    if isinstance(existing_messages, list):
        existing_messages.clear()
    else:
        st.session_state.messages = []
    st.session_state.pop("active_run_id", None)


def _apply_event(
    event: ActivityEvent,
    *,
    status: Any,
    answer_parts: list[str],
    evidence: list[EvidenceCard],
    validations: list[ValidationItem],
) -> None:
    st.session_state.active_run_id = event.run_id
    activity: ActivityItem | None = activity_item(event)
    if activity is not None:
        render_activity_item(status, activity)
    if event.type is EventType.ANSWER_DELTA:
        text = event.public_payload.get("text")
        if isinstance(text, str):
            answer_parts.append(text)
    elif event.type is EventType.ANSWER_COMPLETED:
        raw_evidence = event.public_payload.get("evidence", [])
        if isinstance(raw_evidence, list):
            evidence.extend(evidence_card(Evidence.model_validate(item)) for item in raw_evidence)
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
    st.markdown(f"### {Icon.ASSISTANT} Orysys")
    st.caption("Enterprise knowledge workspace")
    st.divider()

    st.caption("CURRENT CONVERSATION")
    st.markdown(f"**Thread {conversation_id.split('-', maxsplit=1)[0]}**")
    message_count = len(messages)
    st.caption(
        f"{message_count} message{'s' if message_count != 1 else ''}"
        if message_count
        else "Ready for your first question"
    )

    if settings.auth_enabled:
        st.button("Log out", width="stretch", on_click=_logout)
    st.button(
        "New conversation",
        type="primary",
        width="stretch",
        disabled=not messages,
        help=("Start a fresh conversation" if messages else "This conversation is already empty"),
        on_click=_start_new_conversation,
        args=(api,),
    )

    st.divider()
    st.caption("TOOLS")
    if ADMIN_ACTION in _allowed_tools(api):
        with st.expander("Administrator controls"):
            st.caption("Approval-gated simulated operations for assessment and testing.")
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

suggested_prompt: str | None = None
if not messages:
    suggested_prompt = render_suggested_prompts()

typed_prompt = st.chat_input("Ask about authorized policies, systems, or incidents")
prompt = suggested_prompt or typed_prompt
if prompt:
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        activity = st.status("Working", expanded=True)
        evidence_items: list[EvidenceCard] = []
        validation_items: list[ValidationItem] = []
        answer_parts: list[str] = []
        answer_text = ""
        try:
            placeholder = st.empty()
            for event in api.stream_message(conversation_id, prompt):
                _apply_event(
                    event,
                    status=activity,
                    answer_parts=answer_parts,
                    evidence=evidence_items,
                    validations=validation_items,
                )
                if answer_parts:
                    placeholder.markdown("".join(answer_parts) + "▌")
            answer_text = "".join(answer_parts)
            placeholder.markdown(answer_text)
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
