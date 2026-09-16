# Orysys threat model

## Scope and trust boundaries

The browser and all request payloads are untrusted. FastAPI is the policy boundary: it
derives identity from a verified token, assigns tenant/user scope, rate-limits the
identity, and validates input before calling the graph. Model output and retrieved
content are also untrusted. PostgreSQL, Redis, Pinecone, Cloudflare, Keycloak, MCP, and
LangSmith are separate network trust boundaries. Secrets may enter only through runtime
configuration and must never enter prompts, graph state, activity events, logs, or
dataset exports.

## Assets

- tenant documents, evidence excerpts, conversations, memory, and feedback;
- access tokens, provider credentials, approval tokens, and database credentials;
- server-owned authorization scope and action permissions;
- audit integrity, checkpoint integrity, and evaluation provenance.

## Threats and controls

| Threat | Preventive controls | Verification | Residual risk |
|---|---|---|---|
| Identity or tenant spoofing | OIDC verification; server-derived principal and namespace; owner-scoped repositories | API authorization and cross-tenant tests | A compromised issuer remains authoritative |
| Prompt injection or secret exfiltration | Control-character and explicit exfiltration rejection; retrieved memory treated as untrusted context; no secrets in graph state | Adversarial input suite and redaction tests | Novel semantic attacks require continued evaluation |
| Unauthorized network access | MCP operation allow-list; outbound HTTPS/host allow-list; no model-directed generic HTTP, shell, filesystem, or Python | URL policy and tool gateway tests | An allow-listed provider can itself be compromised |
| Tool abuse | Role-filtered registry, schema validation, duplicate authorization in handlers, deadlines, output caps, and idempotency | Tool policy and contract tests | Authorized users can still request harmful but syntactically valid work, so impactful actions require approval |
| Impactful action replay or substitution | Administrator role; canonical action hash; random single-use token stored only as a hash; requester/tenant binding; expiry; atomic state transition; audit record | approval, denial, expiry, identity mismatch, and replay tests | Database administrators can alter persisted state |
| Denial of service | Atomic Redis token bucket keyed by tenant and subject; bounded graph/model/tool budgets; request timeouts | per-user exhaustion and HTTP 429 tests | Distributed traffic across many valid identities needs upstream limits too |
| Data leakage in answers | Access filters before retrieval; evidence ledger; citation validation; safe insufficient-evidence fallback; shared log redaction | retrieval leakage and citation validation suites | Incorrect source metadata can misclassify a document |
| Feedback poisoning | Feedback is owner/run-id idempotent and remains untrusted until an administrator reviews it; only reviewed rows can be exported | feedback ownership, review, idempotency, and export projection tests | Human reviewers can approve poor examples |

## Failure policy

Production and test environments fail closed when the shared rate limiter is
unavailable. Development may fail open so local work is possible. Provider failures
must produce a redacted public error or an explicit degraded result; they must not widen
authorization, skip approval, or invent citations.

## Operational notes

- Rotate any credential that appears outside an ignored local `.env`.
- Keep Redis and PostgreSQL private; local Compose binds them to loopback only.
- Review approval and feedback audit records, rate-limit denials, and provider failures.
- Re-run `python -m orysys.evals.controls` after changing request, tool, or network policy.
