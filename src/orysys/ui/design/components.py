from typing import Any

import streamlit as st

from orysys.ui.design.icons import Icon
from orysys.ui.view_models import ActivityItem, EvidenceCard, ValidationItem


def render_activity_item(container: Any, item: ActivityItem) -> None:
    container.write(item.label)


def render_evidence(evidence: list[EvidenceCard]) -> None:
    if not evidence:
        return
    st.subheader(f"{Icon.EVIDENCE} Evidence")
    for item in evidence:
        with st.expander(f"{item.title} — {item.location}"):
            st.write(item.excerpt)
            st.caption(f"Evidence ID: {item.evidence_id}")
            st.caption(f"Source: {item.source}")


def render_validation(results: list[ValidationItem]) -> None:
    if not results:
        return
    st.subheader("Validation")
    for result in results:
        icon = Icon.VALIDATION if result.passed else Icon.WARNING
        st.write(f"{icon} {result.message}")


def render_login_screen(*, provider_label: str = "Skycloak") -> bool:
    """Render a centered, branded locked screen. Returns True when login was requested."""
    st.markdown(
        """
        <style>
        .orysys-login-wrap { max-width: 560px; margin: 8vh auto 0; }
        .orysys-login-eyebrow {
            font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase;
            opacity: 0.72; margin-bottom: 0.5rem;
        }
        .orysys-login-title { font-size: 2.6rem; line-height: 1.05; margin: 0 0 0.5rem; }
        .orysys-login-sub { font-size: 1.02rem; opacity: 0.82; margin-bottom: 1.25rem; }
        .orysys-login-points {
            display: grid; gap: 0.6rem;
            margin: 1.1rem 0 0; padding: 0.25rem 0 0.65rem;
        }
        .orysys-login-point {
            display: flex; gap: 0.6rem; align-items: flex-start;
            font-size: 0.92rem; opacity: 0.9;
        }
        .orysys-login-point span:first-child { flex-shrink: 0; }
        [data-testid="stButton"] > button {
            transition: transform 160ms cubic-bezier(0.23, 1, 0.32, 1),
                        filter 160ms cubic-bezier(0.23, 1, 0.32, 1);
        }
        [data-testid="stButton"] > button:active { transform: scale(0.97); }
        @media (hover: hover) and (pointer: fine) {
            [data-testid="stButton"] > button:hover { filter: brightness(1.06); }
        }
        @media (prefers-reduced-motion: reduce) {
            [data-testid="stButton"] > button { transition: none; }
            [data-testid="stButton"] > button:active { transform: none; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, center, _ = st.columns([1, 2.2, 1])
    requested = False
    with center:
        st.markdown(
            f"""
            <div class="orysys-login-wrap">
              <div class="orysys-login-eyebrow">Enterprise knowledge workspace</div>
              <div class="orysys-login-title">{Icon.ASSISTANT} Orysys</div>
              <div class="orysys-login-sub">Access-scoped answers, grounded in authorized
              policies, systems, and incidents — with cited evidence and validation.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.markdown("**Sign in to continue**")
            st.caption(
                "Your permissions decide what Orysys can retrieve. "
                "Nothing outside your access scope is shown."
            )
            if st.button(
                f"Continue with {provider_label}",
                type="primary",
                width="stretch",
                icon=":material/login:",
                help=f"Sign in with {provider_label} to open your workspace",
            ):
                requested = True
            st.markdown(
                f"""
                <div class="orysys-login-points">
                  <div class="orysys-login-point"><span>🔒</span>
                  <span>Access-scoped retrieval, enforced by tenant and clearance.</span></div>
                  <div class="orysys-login-point"><span>{Icon.EVIDENCE}</span>
                  <span>Every claim carries cited evidence you can inspect.</span></div>
                  <div class="orysys-login-point"><span>{Icon.VALIDATION}</span>
                  <span>Validated answers, with a safe refusal when unsupported.</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.caption("Secured with Skycloak OIDC. Sessions stay in your browser.")
    return requested


SUGGESTED_PROMPTS: tuple[str, ...] = (
    "What caused incident PAY-2025-0214 (error PAY-DB-042)?",
    "How do I mitigate payment database saturation?",
    "What does the Remote Access Policy require?",
    "What caused the PAY-2025-0603 settlement delay?",
)


def render_suggested_prompts(
    prompts: tuple[str, ...] = SUGGESTED_PROMPTS,
) -> str | None:
    """Render clickable starter prompts. Returns the prompt that was clicked."""
    st.caption("Try asking")
    selected: str | None = None
    for index in range(0, len(prompts), 2):
        row = prompts[index : index + 2]
        columns = st.columns(len(row))
        for column, prompt in zip(columns, row, strict=True):
            with column:
                if st.button(
                    prompt,
                    key=f"suggested-prompt-{index}-{prompt[:16]}",
                    width="stretch",
                    help="Send this question to the assistant",
                ):
                    selected = prompt
    return selected
