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
