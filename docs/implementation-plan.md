# Orysys — Build Plan (v1 Pilot)

This file preserves the planned work-package sequence. For current implementation,
verification, limitations, and release evidence, see
[`release-audit.md`](release-audit.md).

## 1. Outcome

Ship a reproducible, supportable Orysys v1 that answers with evidence, shows its
work, and enforces access. A reviewer/operator must be able to follow a request from
authenticated input through graph routing, retrieval, tools, validation, persistence,
feedback, and final output in both the Streamlit activity panel and LangSmith.

The work is complete only when code, tests, traces, documentation, Docker Compose, and
the guided walkthrough tell the same architectural story.

## 2. Scope guardrails

### Build

- Streamlit chat with multi-turn history, token streaming, and a live activity panel.
- Async FastAPI application with one versioned SSE protocol.
- Explicit LangGraph supervisor, retrieval, research, tool, response, validation,
  memory, and approval flows.
- Pinecone dense plus BM25 sparse retrieval, metadata authorization, attribution, and
  reranking.
- A bounded recursive research flow that explores, partitions, fans out, aggregates,
  and optionally recurses once for an explicit information gap.
- Knowledge search, constrained Python analysis, and a separate dummy MCP server.
- Skycloak-hosted upstream Keycloak authentication and server-enforced RBAC.
- PostgreSQL checkpoints, consent-based long-term memory, feedback, and audit records.
- Redis token-bucket rate limiting.
- LangSmith tracing and offline/online evaluation.
- Prompt-injection, exfiltration, tool-abuse, citation, input, and output controls.
- Failure injection and graceful degradation for all named provider failures.
- Docker Compose, CI, architecture documentation, trace evidence, and walkthrough materials.

### Do not build

- Arbitrary Python, shell, filesystem, or network execution initiated by the model.
- Multiple production vector databases or multiple identity providers.
- A custom JavaScript frontend or a general-purpose Streamlit component library.
- Kubernetes, queues, service mesh, or microservices beyond the required MCP process.
- Automatic learning or prompt changes directly from unreviewed user feedback.
- Automatic durable storage of every conversation statement.
- Production document connectors, OCR at scale, or enterprise data migration.

## 3. Delivery topology

```text
Browser
  -> Streamlit UI
       -> FastAPI /v1 over HTTP + SSE
            -> request controls
            -> assistant runtime
                 -> LangGraph
                      -> model/embedding adapters -> Cloudflare Workers AI
                      -> retrieval module -> Pinecone
                      -> tool module -> MCP sidecar
                      -> analytics module
                      -> checkpoint adapter -> Postgres/Neon
                      -> long-term memory module -> Postgres/Neon
                 -> LangSmith + structured logs
            -> Redis rate limiter
       -> Skycloak-hosted Keycloak via OIDC

Local Docker Compose
  api, ui, mcp-server, postgres, redis
  optional profile: local upstream Keycloak
```

The API, graph, domain logic, and adapters deploy together as a modular monolith. The
MCP server is separate only because the protocol makes that process seam
useful. The Streamlit UI remains a separate process and never calls model, vector, or
tool providers directly.

## 4. Deep modules and interfaces

Each module below hides substantial behavior behind a small interface. Production and
test adapters justify the external seams. Tests exercise the same interface used by
callers and avoid reaching into implementation details.

| Module | Small interface | Behavior hidden behind it | Adapters/tests |
|---|---|---|---|
| `AssistantRuntime` | `stream(request, principal) -> AsyncIterator[ActivityEvent]` | Graph configuration, checkpoints, event ordering, cancellation, final-result mapping | Compiled LangGraph; scenario tests with fake ports |
| `IdentityVerifier` | `verify(token) -> Principal` | OIDC discovery, JWKS cache/rotation, JWT validation, role normalization | Keycloak OIDC adapter; deterministic signed-token adapter |
| `RateLimiter` | `consume(subject, cost) -> LimitDecision` | Atomic refill/consume, retry-after calculation, fail-closed behavior | Redis Lua adapter; deterministic in-memory adapter |
| `ChatModel` | `complete(request) -> ModelResult` and `stream(request) -> AsyncIterator[ModelDelta]` | Cloudflare Workers AI REST mapping via its OpenAI-compatible protocol (wire format only; no OpenAI key/billing), structured output/tool-call parsing, timeouts, provider-error classification | Cloudflare Workers AI adapter; generic OpenAI-protocol fallback (optional, off by default); scripted fake |
| `EmbeddingModel` | `embed(texts) -> list[DenseVector]` | batching, L2 normalization, dimension assertion, retry and corpus/model manifest checks | Cloudflare Qwen adapter; deterministic fake |
| `KnowledgeIndex` | `search(query, scope, options) -> SearchResult` | Embedding, sparse encoding, alpha weighting, mandatory filters, score normalization, evidence mapping | Pinecone adapter; in-memory corpus adapter |
| `Reranker` | `rerank(query, candidates, limit) -> candidates` | Provider request limits, excerpt shaping, stable fallback order | Cloudflare/Pinecone adapter selected by evaluation; identity/fake adapter |
| `ToolGateway` | `execute(request, principal, run_context) -> ToolResult` | Registry, double authorization, schema validation, timeout, retry policy, idempotency, redaction | Knowledge, analytics, MCP adapters; fake/denied adapters |
| `ConversationStore` | LangGraph checkpointer interface | Durable per-thread state, pause/resume, checkpoint versions | Postgres saver; in-memory saver for unit tests |
| `LongTermMemory` | `list`, `remember`, `forget`, `recall` | Consent, tenant/user scope, sensitivity policy, provenance, TTL, ranking, deletion | Psycopg repository; in-memory repository |
| `FeedbackRegistry` | `record`, `get`, `export_reviewed` | Idempotency, run/trace linkage, audit fields, dataset projection | Psycopg repository; in-memory repository |
| `Telemetry` | `span`, `event`, `metric` | LangSmith trace nesting, structured logging, redaction, correlation | LangSmith/structlog adapter; recording test adapter |
| `DocumentIngestion` | `ingest(source, scope) -> IngestionReport` | Parsing, structure-aware chunking, deterministic IDs, BM25 fitting, upsert/delete, provenance | File parsers plus Pinecone; fixture corpus adapter |

No port is created merely to rename an SDK method. Provider-specific configuration and
errors remain local to each adapter. Domain and application modules depend on the
interfaces above, never concrete SDK clients.

## 5. Repository shape

```text
.
├── pyproject.toml
├── uv.lock
├── compose.yaml
├── Dockerfile
├── .env.example
├── .gitignore
├── README.md
├── src/orysys/
│   ├── api/
│   │   ├── app.py
│   │   ├── dependencies.py
│   │   ├── errors.py
│   │   ├── routes/
│   │   └── sse.py
│   ├── application/
│   │   ├── assistant.py
│   │   ├── conversations.py
│   │   ├── feedback.py
│   │   └── memories.py
│   ├── domain/
│   │   ├── identity.py
│   │   ├── evidence.py
│   │   ├── policy.py
│   │   ├── events.py
│   │   ├── feedback.py
│   │   ├── memory.py
│   │   └── errors.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── builder.py
│   │   ├── reducers.py
│   │   ├── routes.py
│   │   ├── nodes/
│   │   └── subgraphs/
│   ├── retrieval/
│   │   ├── module.py
│   │   ├── query.py
│   │   ├── sparse.py
│   │   ├── ranking.py
│   │   └── attribution.py
│   ├── tools/
│   │   ├── gateway.py
│   │   ├── registry.py
│   │   ├── knowledge.py
│   │   ├── analytics.py
│   │   └── mcp.py
│   ├── memory/
│   ├── feedback/
│   ├── ingestion/
│   ├── ports/
│   ├── adapters/
│   │   ├── cloudflare/
│   │   ├── openai_protocol_fallback/ # generic OpenAI-protocol endpoint only; not the default vendor
│   │   ├── pinecone/
│   │   ├── postgres/
│   │   ├── redis/
│   │   ├── keycloak/
│   │   ├── mcp/
│   │   └── langsmith/
│   ├── prompts/
│   ├── config.py
│   └── bootstrap.py
├── ui/
│   ├── app.py
│   ├── api_client.py
│   ├── view_models.py
│   └── design_system/
│       ├── tokens.py
│       ├── theme.py
│       ├── icons.py
│       └── components/
├── mcp_server/
├── migrations/
├── data/sample/
├── evals/
├── tests/
│   ├── unit/
│   ├── graph/
│   ├── contract/
│   ├── integration/
│   ├── security/
│   ├── eval/
│   └── smoke/
├── docs/
│   ├── adrs/
│   ├── diagrams/
│   ├── research/
│   ├── architecture-plan.md
│   ├── implementation-plan.md
│   ├── requirements-traceability.md
│   ├── threat-model.md
│   └── demo-script.md
└── .github/workflows/
```

## 6. Runtime contracts

### Principal and access scope

`Principal` is constructed only by `IdentityVerifier` and contains subject, tenant,
roles, departments, clearance, token ID, and authentication time. A pure policy
function converts it into `AccessScope(namespace, metadata_filter, allowed_tools)`.
Neither the UI payload nor graph/model output may supply or widen these fields.

### Graph state

`AssistantState` contains:

- request, run, thread, checkpoint, and trace identifiers;
- immutable principal/access scope references;
- bounded conversation context and rolling summary;
- route, structured plan, and remaining budgets;
- retrieval queries and append-only evidence ledger;
- child task IDs, findings, and partial failures;
- tool requests/results and approval state;
- validation results, proposed memory candidates, and final answer;
- typed errors and public activity sequence number.

Reducers append and deduplicate evidence/findings/errors by stable IDs. Nodes return
state deltas. Raw documents, access tokens, secrets, hidden prompts, and streamed token
deltas are never persisted in graph state.

### Activity events

Every event has schema version, sequence, request/run/thread IDs, timestamp, event type,
node/agent, status, and a redacted public payload. Planned event types:

```text
run.started                    run.completed                  run.failed
agent.started                  agent.completed                agent.failed
node.started                   node.completed                 node.failed
plan.created                   route.selected
retrieval.started              retrieval.completed            retrieval.degraded
research.batch.started         research.batch.completed       research.batch.failed
tool.requested                 tool.approval_required         tool.approved
tool.denied                    tool.completed                 tool.failed
memory.recalled                memory.proposed                memory.saved
memory.deleted                 validation.completed
answer.delta                   answer.completed
```

The server assigns monotonically increasing sequence numbers. The UI treats duplicate
events idempotently and can reconnect with the last seen sequence where practical.

### Evidence and claims

An `Evidence` record contains stable document/chunk IDs, title, page/section, safe
excerpt, source URI, content hash, authorization scope marker, hybrid score, rerank
score, and corpus version. The response model emits `Claim(text, evidence_ids)`.
Validation rejects missing, unknown, unauthorized, or mismatched evidence IDs.

## 7. API and UI contract

Planned endpoints:

| Endpoint | Purpose | Main controls |
|---|---|---|
| `GET /health/live` | Process liveness | No provider calls |
| `GET /health/ready` | Required dependency readiness | Safe provider status only |
| `POST /v1/conversations` | Create server-owned thread ID | Authenticated, rate limited |
| `GET /v1/conversations/{id}` | Load visible conversation summary | Owner/tenant check |
| `POST /v1/conversations/{id}/messages` | Run graph and stream SSE | Auth, rate limit, schema/input policy |
| `POST /v1/runs/{id}/resume` | Resume a pending approval | Administrator plus approval token |
| `POST /v1/runs/{id}/feedback` | Record thumbs/note | Run ownership, idempotency |
| `GET /v1/memories` | List durable memories | User-scoped |
| `POST /v1/memories/{id}/confirm` | Confirm proposed memory | User-scoped, expiry required |
| `DELETE /v1/memories/{id}` | Forget durable memory | User-scoped, audited |

Streamlit owns login initiation, chat layout, session navigation, activity rendering,
evidence expansion, approval controls, feedback controls, and memory management. It
receives typed view models from its API client. Only native Streamlit primitives plus
the small project-owned design system are used.

## 8. Agent graph plan

### Top-level supervisor

1. Validate input and policy.
2. Recall authorized conversation and long-term memory context.
3. Produce a typed intent and bounded plan.
4. Route deterministically to direct retrieval, recursive research, or authorized tool
   work based on plan fields.
5. Compose only from evidence and structured tool results.
6. Validate authorization, citations, response schema, safety, and brand rules.
7. Permit one repair attempt.
8. Propose optional durable memory, checkpoint the turn, and finish safely.

### Specialized agents

- **Supervisor agent:** intent, plan, budgets, and route. It cannot retrieve or execute
  tools directly.
- **Retrieval agent:** query variants, hybrid search, reranking, evidence ledger. It
  cannot change access scope.
- **Research agent:** collection exploration, document batching, bounded child workers,
  gap analysis, and structured reduction.
- **Tool agent:** chooses among already-authorized tool descriptions; all calls still
  pass through `ToolGateway`.
- **Response agent:** converts claims/evidence/findings into a branded response and
  cannot call providers other than the model.
- **Validation agent/module:** deterministic checks first; model-based quality review
  only where deterministic checks cannot decide.

Each has its own prompt version, structured output schema, timeout, retry budget, trace
span, state transition tests, and public start/completion/failure events.

### Multi-agent failure isolation

- Child tasks receive immutable access scope and independent call/token/deadline budgets.
- Results use `Success[T] | Partial[T] | Failure` envelopes rather than exceptions in
  shared graph state.
- A failed child never cancels successful siblings unless the overall deadline expires.
- The reducer is deterministic and idempotent; it combines structured findings, not raw
  child transcripts.
- Circuit breakers and global request budgets prevent provider failure amplification.
- Partial answers list missing batches/sources without exposing internal errors.
- Checkpoints prevent completed expensive work from being repeated after approval or a
  recoverable interruption.

## 9. Retrieval and ingestion plan

### Sample corpus

Create deterministic synthetic documents for a fictional commercial bank:

- policies with different access levels;
- architecture documents;
- payment and non-payment incident reports across dates;
- operational runbooks;
- product specifications;
- meeting notes;
- exact error codes and semantic paraphrases;
- one retrieved prompt-injection document;
- deliberately unauthorized documents for leakage tests.

Store source fixtures in version control with stable IDs and expected-answer metadata.
No real personal, company, or customer data is used.

### Ingestion

1. Parse Markdown, text, JSON, and text-native PDF while retaining page/section data.
2. Validate file type, size, page count, extraction warnings, and required metadata.
3. Normalize elements and apply structure-aware chunking.
4. Generate deterministic document/chunk IDs and hashes.
5. Fit BM25 on the actual corpus and persist encoder parameters with corpus checksum.
6. Generate 1,024-dimensional Qwen dense embeddings asynchronously with bounded
   concurrency, then L2-normalize vectors before they cross the adapter seam.
7. Upsert dense and sparse vectors plus attribution/security metadata to one Pinecone
   index per environment and namespace per tenant.
8. Reconcile stale document versions idempotently.
9. Poll index stats for eventual consistency before declaring success.
10. Emit an ingestion report with inserted, updated, deleted, rejected, and failed counts.

### Query path

1. Derive namespace and mandatory metadata filters from `AccessScope`.
2. Create bounded dense/lexical query variants.
3. Encode dense and BM25 sparse query vectors.
4. Apply the same L2 normalization to query embeddings, then apply evaluated alpha
   weighting and query Pinecone asynchronously.
5. Deduplicate and convert matches to authorized evidence records.
6. Rerank a wider candidate set and return the final evidence set.
7. Record query type, filters, alpha, counts, scores, latency, and corpus version without
   logging restricted text.

Tune chunking, alpha, candidate count, top-k, and reranker with the evaluation corpus.
Record the chosen values and measurements; do not claim universal defaults.

## 10. Recursive research plan

The RLM implementation uses a validated plan DSL executed by trusted Python:

```text
ResearchPlan
  objective
  discovery_queries[]
  filters
  grouping_strategy
  batch_size
  max_depth
  max_children
  max_retrieval_calls
  max_model_calls
  token_budget
  deadline
  aggregation_schema
```

Execution stages are discover, filter, partition, child analysis, reduce, explicit gap
check, one optional targeted recursion, compose, and validate. Defaults remain small
enough for a predictable walkthrough. The annual payment-outage example must prove date/topic
filtering, batching, parallel child analysis, partial-failure behavior, recurring-cause
aggregation, and evidence-backed output.

Deep Agents is not the primary runtime. A time-boxed compatibility spike may wrap one
research worker behind the same interface only if it preserves graph visibility, RBAC,
budgets, checkpoints, and deterministic tests. Failure of that spike does not block the
explicit LangGraph implementation or reduce requirement coverage.

## 11. Tools and approval

### Knowledge search

Calls `KnowledgeIndex` with the server-derived scope. The model may choose a query and
requested limit within bounds; it cannot set namespace or authorization filters.

### Python analysis

Expose named operations over validated structured records, initially:

- count/group incidents by normalized root cause;
- calculate recurrence and date-range summaries;
- aggregate severity/service statistics;
- sort and limit tabular results.

No `eval`, `exec`, arbitrary expressions, imports, filesystem, subprocesses, or network
access are accepted.

### MCP server

Expose dummy employee-directory, service-catalog, and incident-record tools through the
official MCP SDK. Use Streamable HTTP, protocol contract tests, strict schemas, small
responses, request deadlines, and no secrets. Analyst and administrator may use
read-only tools; only administrator may request a simulated impactful action.

### Human approval

An administrator's impactful action creates a JSON-serializable proposal and pauses at
a LangGraph interrupt before any side effect. Resume requires the same principal,
thread/run IDs, action hash, unexpired approval token, and explicit confirmation.
Execution is idempotent. Denial, timeout, duplicate resume, principal mismatch, and
restart recovery all have tests and visible events.

## 12. Authentication, authorization, and security

### Authentication

- Skycloak hosts upstream Keycloak for the public pilot.
- Streamlit uses Authorization Code OIDC and forwards only the access token to FastAPI.
- FastAPI validates signature, fixed algorithms, issuer, audience, expiry/not-before,
  and required client roles using cached discovery/JWKS with bounded refresh.
- Local Keycloak uses an exportable equivalent realm through a Compose profile.
- Unit tests use locally signed fixtures and never require the hosted identity provider.

### Authorization

| Capability | Viewer | Analyst | Administrator |
|---|---:|---:|---:|
| Chat and scoped search | yes | yes | yes |
| Python analytics | no | yes | yes |
| Read-only MCP | no | yes | yes |
| Durable memory management | own only | own only | own only |
| Feedback | own runs | own runs | own runs |
| Impactful simulated action | no | no | approval required |

Authorization is checked when tools are listed and again in `ToolGateway`. Retrieval
scope, conversation ownership, memory ownership, feedback ownership, and approval
identity are enforced by deterministic code.

### Threat controls

- Request schema, length, encoding, and supported-content validation.
- Instruction hierarchy and clear untrusted-data delimiters.
- Retrieved prompt-injection detection as a signal, never the sole defense.
- Allow-listed tools and outbound hosts; strict Pydantic parameters and response limits.
- Evidence ledger and claim-to-evidence citation validation.
- Secret/token/document redaction shared by logs, traces, events, and error responses.
- Safe brand policy for the fictional bank: no fabricated commitments, account actions,
  financial advice, or claims unsupported by authorized evidence.
- Per-user token bucket and graph-level call/token/time budgets.
- Dependency locking, container non-root users, health checks, and secret injection only
  through environment/runtime configuration.
- A documented threat model with assets, trust zones, abuse cases, controls, residual
  risk, and verification links.

## 13. Persistence plan

### PostgreSQL ownership

LangGraph owns its checkpoint tables. Application migrations own only:

```text
memory_items
  id, tenant_id, user_id, kind, content, provenance_run_id,
  sensitivity, status, created_at, expires_at, deleted_at

feedback
  id, tenant_id, user_id, run_id, trace_id, rating, note,
  prompt_version, model, corpus_version, route, created_at

audit_events
  id, tenant_id, actor_id, action, resource_type, resource_id,
  outcome, safe_metadata_json, created_at
```

Use Psycopg and typed row mapping at first. Alembic manages application tables. Do not
edit LangGraph-managed checkpoint schemas through application migrations. Neon uses a
direct connection for the async checkpointer; local PostgreSQL provides the same
contract in Compose.

### Long-term memory lifecycle

1. Recall only active, unexpired items for the authenticated tenant/user.
2. Graph may propose a memory candidate but cannot persist it directly.
3. UI shows content, purpose, provenance, and expiry for confirmation.
4. Policy rejects secrets, restricted document text, inferred sensitive attributes,
   and unsupported claims.
5. Confirmed items become available across threads.
6. Users can list and delete their items; deletion is audited.
7. Tests prove tenant/user isolation, expiry, explicit consent, and injection resistance.

### Feedback lifecycle

Feedback is idempotent per user/run. It is attached to exact trace, prompt, model,
corpus, route, and evidence versions. A reviewed export creates evaluation examples;
negative feedback does not automatically become ground truth or modify runtime prompts.

## 14. Reliability and graceful degradation

| Failure | Required behavior | Verification |
|---|---|---|
| Cloudflare model timeout/429/403/5xx | bounded retry only for transient errors; safe failure or configured fallback; never retry a paid-only-plan error | fake adapter and deadline tests |
| Invalid model output | structured parse failure, one repair, then safe response | malformed fixture tests |
| Pinecone unavailable | no fabricated answer; explicit unavailable result | adapter failure injection |
| Dense encoding fails | use sparse-only if independently available; label degradation | retrieval scenario test |
| Sparse encoding fails | use dense-only; label degradation | retrieval scenario test |
| Reranker fails | preserve hybrid order | deterministic fallback test |
| One research child fails | retain sibling results; label incomplete coverage | graph fan-out test |
| MCP timeout/failure | omit tool result; continue if evidence is sufficient | protocol timeout tests |
| Analytics input invalid | reject tool request without executing | schema/property tests |
| Postgres checkpoint failure | avoid claiming memory; safe completion only if state permits | saver failure test |
| Redis unavailable | fail closed outside explicit development mode | readiness/policy test |
| Keycloak/JWKS unavailable | cached valid keys within policy or authentication unavailable | cache-expiry tests |
| Citation validation fails | one repair, then partial/insufficient-evidence answer | hallucinated-ID tests |
| SSE client disconnects | cancel work where safe; preserve checkpoint; no leaked task | cancellation test |
| Approval expires/replays | reject without side effect | resume idempotency tests |

Retries occur only at adapter seams for classified transient and idempotent operations.
Every request has a wall-clock deadline and every child/tool call receives a smaller
derived deadline.

## 15. Observability and evaluation

### LangSmith and logs

- Trace every conversation with nested spans for graph transitions, retrieval,
  reranking, tools, child research, validation, memory, and approval.
- Correlate `request_id`, `run_id`, `thread_id`, trace ID, route, role, prompt version,
  model, corpus version, and retrieval configuration.
- Apply one redaction policy before data reaches LangSmith, structlog, activity events,
  exceptions, or audit metadata.
- Keep raw tokens, credentials, restricted document bodies, system prompts, and hidden
  reasoning out of telemetry.

### Evaluation set

Create versioned cases for:

- exact identifier/BM25 retrieval;
- semantic paraphrase/dense retrieval;
- hybrid query requiring both;
- metadata date/type/department filters;
- unauthorized document leakage attempts;
- grounded direct answer and insufficient-evidence answer;
- multi-document outage research and recurring-cause aggregation;
- child failure and partial aggregation;
- multi-turn conversation recall;
- cross-thread confirmed-memory recall and deletion;
- all three roles and every allowed/denied tool path;
- user and retrieved-document prompt injection;
- exfiltration, role spoofing, namespace spoofing, and tool-parameter abuse;
- hallucinated/missing citations;
- each named provider failure and timeout;
- approval, denial, expiry, replay, and restart resume;
- feedback idempotency and reviewed dataset export.

Measure recall@k, MRR/nDCG where useful, citation validity/precision, groundedness,
policy bypass count, task success, partial-result correctness, latency percentiles,
model/tool calls, tokens, and estimated cost. Establish a baseline before tuning and
record chosen thresholds in the evaluation README.

## 16. Test strategy and CI gates

### Test layers

- **Unit:** pure policy, reducers, routing, budgets, schemas, citation rules, memory
  policy, feedback projection, and analytics.
- **Graph:** complete paths with fake ports, including loops, interruption, resume,
  partial failures, deadlines, and checkpoint restoration.
- **Contract:** Pinecone request mapping, OIDC/JWKS, MCP protocol, SSE schema, Postgres
  repositories, Redis Lua behavior, and provider error classification.
- **Integration:** local PostgreSQL/Redis/MCP plus API; opt-in live Pinecone, model,
  LangSmith, Skycloak, and Neon tests.
- **Security:** RBAC matrix, tenant isolation, injections, citation spoofing, unsafe tool
  parameters, approval replay, leakage/redaction, and rate-limit bypass.
- **Evaluation:** versioned retrieval and answer cases with recorded configuration.
- **Smoke:** Docker Compose health, login configuration, one chat run, one tool call,
  one checkpoint resume, and one feedback entry.

### Pull-request gates

1. `ruff check` and `ruff format --check`.
2. Strict mypy for domain/application/interfaces; narrow documented adapter ignores.
3. Unit, graph, contract, and security tests without paid services.
4. Migration upgrade from empty database and downgrade/re-upgrade check where safe.
5. Dependency vulnerability/license scan and secret scan.
6. Container build and Compose configuration validation.
7. Retrieval evaluation comparison when ingestion/ranking/chunking changes.

## 17. Configuration and operational plan

Use validated settings grouped by application, auth, Cloudflare model/embedding,
retrieval, database, Redis, MCP, tracing, budgets, and feature flags. Include
`CLOUDFLARE_ACCOUNT_ID`, a server-only scoped `CLOUDFLARE_API_TOKEN`, base URL,
generation model ID, embedding model ID, expected dimension, and per-run/day budgets.
`.env.example` contains names and safe example values only. Startup fails with a concise
message for missing required production settings or a Pinecone/embedding dimension
mismatch.

Feature flags are limited to genuine environment differences:

- fake versus live external adapters;
- Cloudflare Qwen default versus the evaluated GLM alternate or a generic
  OpenAI-protocol fallback (optional; Cloudflare remains the default vendor);
- local Keycloak versus Skycloak issuer;
- optional Deep Agents research spike;
- in-memory rate limiting in explicit development mode only;
- trace body policy for synthetic walkthrough data.

Compose containers use pinned images, non-root users where supported, health checks,
read-only mounts where practical, named volumes, restart behavior, and no embedded
credentials. Readiness distinguishes required from optional/degraded dependencies.

## 18. Ordered work packages

Each package ends with passing tests, updated docs, and a focused commit. Later packages
may start only when their dependencies and exit criteria pass.

### WP-00 Repository and decisions

Depends on: none

- Initialize Git, public-safe ignore rules, license, README skeleton, contribution notes,
  environment example, and CI skeleton.
- Record ADRs for modular monolith, explicit LangGraph, Pinecone hybrid search,
  Skycloak-hosted Keycloak, Neon direct Postgres, project-owned UI system, bounded RLM,
  and consent-based memory.
- Add architecture and graph diagrams as source-controlled Mermaid plus exported image.

Exit: clean public repository with no secrets and all major decisions traceable.

### WP-01 Python foundation

Depends on: WP-00

- Configure Python, uv, dependency groups, Ruff, mypy, pytest, and package layout.
- Implement domain values, errors, interfaces, fake adapters, settings, and composition
  root skeleton, including Cloudflare chat/embedding provider contracts.
- Define SSE/event, evidence, plan, tool, validation, memory, and feedback schemas.

Exit: imports, lint, type checks, and contract serialization tests pass.

### WP-02 Corpus and ingestion

Depends on: WP-01

- Create synthetic bank corpus and golden metadata.
- Implement parsing, chunking, attribution, deterministic IDs, BM25 fitting, embedding,
  Qwen vector normalization/dimension assertion, and idempotent Pinecone reconciliation.
- Add extraction, chunking, access metadata, and eventual-consistency tests.

Exit: repeat ingestion makes no unintended changes and every indexed chunk is attributable.

### WP-03 Hybrid retrieval and reranking

Depends on: WP-02

- Implement access-scope derivation, dense/sparse search, alpha weighting, evidence
  conversion, and one evaluated reranking/fallback provider.
- Build retrieval evaluation baseline and tune parameters.

Exit: exact, semantic, hybrid, filter, attribution, and unauthorized-leakage cases meet
documented thresholds.

### WP-04 Direct graph and validation

Depends on: WP-01, WP-03

- Implement supervisor, retrieval, response, and validation paths with structured output.
- Add evidence ledger, citation validation, one repair, and insufficient-evidence answer.
- Add LangSmith spans and redacted structured logging.

Exit: direct questions produce grounded cited answers and malformed/citation failures are safe.

### WP-05 FastAPI, SSE, and Streamlit

Depends on: WP-04

- Implement lifecycle-managed clients, endpoints, error mapping, cancellation, and SSE.
- Implement Streamlit chat, activity timeline, evidence cards, validation status, and
  project-owned tokens/icons/components.

Exit: two-turn streamed chat works and activity events remain ordered and redacted.

### WP-06 Recursive research and multi-agent isolation

Depends on: WP-04

- Implement research plan DSL, discovery, bounded fan-out, worker subgraph, deterministic
  reducer, gap recursion, budgets, and partial failures.
- Optionally run the contained Deep Agents compatibility spike.

Exit: annual outage scenario proves batching, aggregation, citations, and one-child failure.

### WP-07 Authentication and RBAC

Depends on: WP-05

- Configure Skycloak realm/client/roles and export an equivalent local Keycloak realm.
- Implement OIDC verification, token forwarding, principal/access scope, and complete
  role matrix enforcement.

Exit: valid users work; invalid tokens, role spoofing, cross-tenant access, and denied
tools fail before provider execution.

### WP-08 Tools and MCP

Depends on: WP-06, WP-07

- Implement knowledge and constrained analytics tools.
- Implement separate MCP server/client and `ToolGateway` double authorization.
- Add timeouts, output caps, protocol tests, and tool activity events.

Exit: analyst paths work, viewer paths are denied, and failures degrade predictably.

### WP-09 Durable checkpoints and memory

Depends on: WP-04, WP-07

- Configure Postgres checkpointer and prove restart/pause-resume behavior.
- Add rolling summary/context controls.
- Implement long-term memory propose/confirm/recall/expire/delete lifecycle and audits.

Exit: thread memory survives restart; cross-thread memory requires consent and is isolated.

### WP-10 Rate limiting and security controls

Depends on: WP-07, WP-08

- Implement Redis token bucket, input/output rules, injection/exfiltration controls,
  outbound allow-list, shared redaction, and threat model.
- Run adversarial security suite.

Exit: configured per-user limits and all documented abuse cases behave safely.

### WP-11 Human approval

Depends on: WP-08, WP-09

- Implement simulated impactful admin action, interrupt proposal, UI approval/denial,
  secure resume, idempotency, expiry, and audit record.

Exit: restart-safe approval works and denial/replay/mismatched identity cannot execute.

### WP-12 Feedback and evaluation loop

Depends on: WP-05, WP-09

- Implement feedback UI/API/storage and reviewed LangSmith dataset export.
- Complete offline dataset, deterministic check suites, selective LLM judge, and results
  report.

Exit: feedback is trace-linked/idempotent and evaluation is reproducible from a command.

### WP-13 Reliability and performance

Depends on: WP-03 through WP-12

- Add provider failure injection, retry/deadline/cancellation tests, concurrency caps,
  load smoke tests, and cost/latency measurements.
- Verify no cascade under child/provider failure.

Exit: every named failure mode and fallback appears in tests and activity/trace evidence.

### WP-14 Containers and CI

Depends on: WP-05, WP-08, WP-09, WP-10

- Build production-like containers and Compose profiles with health checks.
- Complete CI gates, migration checks, scans, and one-command local setup.

Exit: a fresh machine can run the documented local pilot path with fixture/fake credentials.

### WP-15 Release and walkthrough

Depends on: all previous packages

- Finalize public README, architecture diagram, setup, assumptions, trade-offs, security,
  evaluation results, trace links/screenshots, and troubleshooting.
- Prepare and rehearse a timed guided walkthrough showing v1-scope evidence.
- Audit the public repository for secrets, personal data, dead code, stale flags, and
  unreferenced claims before publication.

Exit: every row in `requirements-traceability.md` has implementation, test, and walkthrough evidence.

## 19. Suggested commit history

Use small, reviewable commits that preserve the product build story:

1. `plan: record architecture and requirement traceability`
2. `build: initialize typed Python project and CI`
3. `product: add domain contracts and fake provider adapters`
4. `product: add synthetic corpus and idempotent ingestion`
5. `product: implement scoped hybrid retrieval and reranking`
6. `product: add direct LangGraph workflow and citation validation`
7. `product: stream graph activity through FastAPI and Streamlit`
8. `product: add bounded recursive research subgraph`
9. `product: enforce Keycloak identity and role policy`
10. `product: add authorized analytics and MCP tools`
11. `product: persist checkpoints and consent-based memories`
12. `product: add Redis rate limits and security guardrails`
13. `product: add restart-safe human approval`
14. `product: capture feedback and export evaluation examples`
15. `test: cover provider failures and multi-agent isolation`
16. `release: add reproducible Compose deployment`
17. `release: finalize evaluation evidence and walkthrough guide`

Never manufacture commit history after implementation. Each commit must build or have a
clearly documented temporary reason when a cross-commit change is unavoidable.

## 20. Guided walkthrough plan (45 min)

Walk a pilot customer through the v1 story in 45 minutes, using live product behavior
and trace evidence:

| Time | Evidence |
|---:|---|
| 0-4 min | Problem, architecture diagram, assumptions, and deliberate trade-offs |
| 4-9 min | Repository modules, deep interfaces, graph state, async/event design |
| 9-15 min | Viewer direct RAG, streaming UI, hybrid evidence, attribution, LangSmith trace |
| 15-23 min | Annual outage RLM: discovery, batching, parallel agents, aggregation, partial failure |
| 23-28 min | Multi-turn checkpoints, process restart, confirmed cross-thread memory, deletion |
| 28-34 min | Viewer denial, analyst tools, MCP call, Python analysis, metadata isolation |
| 34-38 min | Admin action pause, approval/denial, resume and audit evidence |
| 38-41 min | Prompt injection, exfiltration, hallucinated citation, rate limiting, provider failure |
| 41-43 min | Feedback entry and LangSmith evaluation dataset/results |
| 43-45 min | Docker Compose, known limitations, production next steps, recap |

Keep a prerecorded fallback for hosted-provider outages, but demonstrate the live path
when available. The fallback must show real prior traces/results from the same commit.

## 21. Definition of done

- Every row in the traceability matrix is marked verified.
- The public repository builds from documented commands and contains no secrets.
- Unit, graph, contract, integration, security, evaluation, and Compose smoke tests pass.
- Mandatory provider calls are async and lifecycle-managed.
- All three roles and all resource ownership rules have positive and negative tests.
- Hybrid retrieval has measured results and complete attribution.
- The RLM path proves bounded recursion and partial-failure isolation.
- Checkpoints survive restart; durable memory requires consent and supports deletion.
- HITL execution is resumable, authorized, expiring, idempotent, and audited.
- Every answer citation maps to authorized evidence; unsupported claims fail safely.
- LangSmith traces and UI events expose useful execution state without secrets or hidden
  chain-of-thought.
- Feedback is run/trace-linked and exportable through a reviewed evaluation flow.
- Docker Compose starts the documented local stack and health checks pass.
- The architecture diagram, README, assumptions/trade-offs, evaluation report, and
  guided walkthrough are complete and consistent with the implemented commit.

## 22. Risks and decision checkpoints

| Risk | Planned control | Decision checkpoint |
|---|---|---|
| Scope exceeds release timeline | Implement work packages in value/risk order; keep v1 scope bounded | Re-estimate after WP-05 and WP-10 |
| Deep Agents hides behavior or churns | Explicit LangGraph remains authoritative; contain spike behind worker interface | Decide during WP-06 |
| Pinecone sparse/rerank behavior differs by account | Early live compatibility test plus fake adapter and measured fallback | Before WP-03 exit |
| Cloudflare free allocation/model access changes | Provider contract tests, per-run budgets, safe quota failure, and configurable fallback | Before WP-04 exit and walkthrough rehearsal |
| Neon pooler incompatibility | Use direct endpoint for checkpointer; local Postgres for tests | Before WP-09 |
| Skycloak operator-access ambiguity | Describe as hosted upstream Keycloak; include realm export and local profile | Before WP-07 exit |
| Streamlit OIDC/token behavior blocks API flow | Prove token handoff in an early auth spike | Start of WP-07 |
| Telemetry leaks sensitive content | One redaction module and adversarial trace/log tests | WP-04 and WP-10 gates |
| Long-term memory creates privacy risk | Explicit consent, narrow data classes, TTL, provenance, delete, isolation | WP-09 design review |
| Feedback becomes false ground truth | Store raw signal; require review before dataset export | WP-12 design review |
| Hosted services fail during walkthrough | Checkpointed state, graceful errors, fixtures, recorded fallback evidence | Walkthrough rehearsal |

Open tuning choices - model, index dimension, chunk sizes, alpha, candidate count,
reranker, recursion budgets, timeouts, rate thresholds, memory TTL, and evaluation
thresholds - must be settled by compatibility tests and recorded measurements, not by
guesswork.

## Appendix A. Brief coverage note

The work packages above cover the originating solution brief end to end, from
foundation and retrieval through operations, release, and the guided walkthrough.
ID-level mapping between brief items, implementation, tests, and walkthrough evidence
lives in requirements-traceability.md.
