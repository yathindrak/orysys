# Orysys guided walkthrough

Target duration: 42–45 minutes. Record the exact demonstrated commit, configured model,
corpus version, prompt version, and LangSmith project before starting. Never show `.env`,
tokens, database URLs, raw restricted documents, or Streamlit client secrets.

## Preparation

1. Run `make verify` and save the CI URL for the demonstrated commit.
2. Run `make pilot` for the credential-free topology check, then use `make pilot-live`
   only if the authorized provider and identity configuration is ready.
3. Confirm the Pinecone index contains `bank-demo-v1` and the BM25 artifact matches it.
4. Select redacted LangSmith traces for direct, research, tool, degraded, and approval
   examples. Record their IDs privately in the presenter notes.
5. Use synthetic accounts and data only. Clear unrelated browser tabs and terminal
   history before recording.

## 0–5 min: problem and architecture

- State the product outcome: evidence-backed organizational answers with visible work
  and deterministic access enforcement.
- Show the system-context diagram and modular-monolith/provider-port decisions.
- Point out the trust boundaries: browser, API, model, Pinecone, MCP, PostgreSQL, Redis,
  Keycloak, and LangSmith.

Evidence: `docs/diagrams/system-context.mmd`, rendered `system-context.svg`, ADR index,
threat model.

## 5–10 min: identity and role policy

- Log in as viewer and show the server-derived role/tenant behavior.
- Attempt the analytics tool as viewer and show the denial.
- Log in as analyst and show knowledge, analytics, and MCP capabilities.
- Explain that request bodies and prompts cannot choose tenant, namespace, or role.

Evidence: OIDC trace, `/v1/tools` responses, redacted tool events.

## 10–15 min: direct grounded answer

- Ask an exact incident or policy question.
- Follow retrieval, generation, validation, and answer events in the activity panel.
- Expand evidence cards and match each claim to an authorized evidence ID.
- Ask a follow-up to demonstrate bounded conversation context.

Evidence: Streamlit activity/evidence views and matching LangSmith root run.

## 15–23 min: bounded research

- Ask the annual recurring payment-incident question.
- Show discovery queries, document grouping, bounded child batches, deterministic reduce,
  and the one allowed gap retry.
- Explain model-call, child, recursion, token, and deadline budgets.
- Use the recorded failure fixture to show one failed child while siblings still produce
  an explicitly incomplete cited result.

Evidence: research trace, ordered events, retrieval evaluation report.

## 23–30 min: retrieval quality and access

- Compare exact identifier/BM25, semantic/dense, and hybrid queries.
- Show server-owned namespace and metadata filters without exposing restricted content.
- Explain reranking and the deterministic fallback order.
- Present recall/MRR and zero-leakage results plus the known annual-case gap.

Evidence: `evals/results/retrieval-bank-demo-v1.json` and evaluation README.

## 30–34 min: tools and durable memory

- Invoke the synthetic MCP service catalog and constrained incident aggregation.
- Show strict arguments, timeout/output caps, idempotency, and redacted events.
- Propose and confirm a harmless memory, open another thread, recall it, then delete it.
- Explain checkpoint state versus consent-based long-term memory tables.

Evidence: tool events, memory audit rows with synthetic identifiers only.

## 34–38 min: administrator approval

- Request the simulated service restart as administrator.
- Show the pause and approve or deny controls without displaying the approval token.
- Demonstrate denial or replay rejection and explain requester binding, action hash,
  expiry, atomic transition, restart persistence, and audit.

Evidence: approval trace and redacted audit outcome.

## 38–42 min: controls, failure handling, and feedback

- Run a prompt-injection/exfiltration attempt and show the safe response.
- Show a hallucinated citation repair/failure and a controlled provider degradation.
- Demonstrate a rate-limit response with `Retry-After`.
- Submit thumbs feedback, review it as administrator, and show the identity-free dataset
  projection. Emphasize that unreviewed feedback cannot alter runtime behavior.

Evidence: control evaluation, reliability matrix, reviewed feedback export.

## 42–45 min: reproducibility and limitations

- Show the non-root image, Compose topology, health checks, migration cycle, and CI jobs.
- Summarize provider choices, bounded research, synthetic data, simulated action, and
  remaining production-readiness work.
- End on the exact commit and traceability matrix. Do not claim rows lacking recorded
  walkthrough or trace evidence as verified.
