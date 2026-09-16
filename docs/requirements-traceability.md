# Orysys — Product Requirements & Acceptance Criteria

This document is the acceptance checklist for Orysys — Enterprise Knowledge Assistant. A requirement is met only when spec, implementation, automated check, and operator verification agree at the same commit.

Status values used by the release audit:

- **Planned:** design and work package are identified; no implementation claim.
- **Implemented:** code exists and local tests pass.
- **Verified:** code, automated evidence, documentation, and operator evidence agree.

This matrix defines what evidence each requirement needs; it does not itself claim that
the evidence was captured. The current grouped status, exceptions, and evidence links
are maintained in [`release-audit.md`](release-audit.md). A row is **Verified** only
after its automated and operator evidence are both recorded for the same commit.

## 1. Objective and user experience

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| OBJ-01 | Enterprise knowledge assistant, not a thin LLM wrapper | Modular monolith, typed domain, explicit graph, provider adapters, security and evaluation | Architecture/import tests and end-to-end scenarios | Architecture-to-request verification |
| OBJ-02 | Search organizational documents | `KnowledgeIndex` over synthetic bank corpus | Retrieval evaluation and filter tests | Search policy/runbook/incident examples |
| OBJ-03 | Answer questions with supporting evidence | Evidence ledger and claim-to-evidence validator | Citation validity and insufficient-evidence tests | Expand evidence cards for final answer |
| OBJ-04 | Explain what the system is doing | Typed public activity events plus LangSmith spans | Event ordering/redaction contract tests | Live activity panel and matching trace |
| OBJ-05 | Maintain conversation context | Postgres LangGraph checkpoints and bounded rolling summary | Multi-turn and restart tests | Follow-up without repeating context |
| OBJ-06 | Invoke external tools | Authorized knowledge, analytics and MCP tools | Role/tool matrix and protocol tests | Analyst invokes MCP and analytics |
| OBJ-07 | Multiple roles with controlled information/tool access | Keycloak roles plus server-derived `AccessScope` | Positive/negative RBAC and leakage suite | Viewer denial, analyst success, admin approval |
| OBJ-08 | Readable surrounding logic | Deep modules, small interfaces, typed state/events/errors, ADRs | Ruff, mypy, architecture dependency checks | Repository module review |
| OBJ-09 | Maintain meaningful Git history | Focused work-package commits | CI at each commit where practical | Public history review |

## 2. Frontend

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| UI-01 | Use Streamlit | Thin Streamlit process | Compose smoke test | Open running application |
| UI-02 | Multi-turn chat | Server-owned conversation/thread ID, checkpoint reload, owner-scoped `GET /v1/conversations` list plus sidebar history picker | UI/API multi-turn and list integration tests | Two related questions plus previous-thread reload |
| UI-03 | Streaming responses | FastAPI SSE `answer.delta`, rendered with native Streamlit streaming | SSE framing/order/disconnect tests | Visible token stream |
| UI-04 | Current agent state | `agent.*` and `node.*` events | Event schema tests | Activity timeline |
| UI-05 | Active LangGraph node | Node name/status in public events | Graph-to-event mapping tests | Live node transitions |
| UI-06 | Tool calls | Redacted request/result/status cards | Tool event tests | MCP and analytics calls |
| UI-07 | Retrieval status | Query type, filter summary, counts, latency and degradation events | Retrieval event tests | Dense/sparse/hybrid status |
| UI-08 | Memory updates | Recall/propose/save/delete events | Memory event tests | Checkpoint and durable-memory actions |
| UI-09 | Validation results | Citation/auth/safety/brand checks in activity panel | Validator/event tests | Passed and blocked examples |
| UI-10 | Final generation | Generation state, answer deltas, plus per-claim bullet rendering | Stream integration and UI claim tests | Final-response phase with claim bullets |
| UI-11 | Functional transparency over visual complexity | Native Streamlit plus small project-owned design system | Smoke/accessibility checks | Clear chat/activity/evidence layout |

## 3. Backend and async engineering

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| BE-01 | Python | Python 3.13 project managed by uv | CI interpreter and lock checks | Repository configuration |
| BE-02 | FastAPI | Versioned routes and lifecycle composition root | API contract tests | API docs/requests |
| BE-03 | Async APIs | Async route handlers and SSE generator | Concurrency/cancellation tests | Concurrent streaming run |
| BE-04 | Async retrieval | Pinecone async client and bounded embedding concurrency | Adapter concurrency tests | Retrieval timing trace |
| BE-05 | Async tool execution | Awaitable `ToolGateway`, MCP and analytics operations | Timeout/concurrency tests | Parallel research/tool trace |
| BE-06 | Proper exception handling | Typed provider/domain errors mapped at API/graph seams | Failure matrix tests | Controlled failure examples |
| BE-07 | Structured logging | structlog JSON with correlation and redaction | Log capture/redaction tests | Safe correlated log excerpt |

## 4. LangGraph and specialized agents

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| LG-01 | LangGraph orchestration | Explicit compiled `StateGraph` | Graph topology snapshot/test | Graph diagram and live transitions |
| LG-02 | Supervisor agent | Typed intent, plan, budget and route | Structured-output and routing tests | Supervisor selects path |
| LG-03 | Retrieval agent | Query generation, scoped hybrid search, evidence | Retrieval subgraph tests | Retrieval-agent span/events |
| LG-04 | Research agent | Discovery, batching, bounded workers, reduce/gap check | Fan-out/recursion tests | Annual outage investigation |
| LG-05 | Response agent | Claims generated only from evidence/findings | Grounding/citation tests | Cited final synthesis |
| LG-06 | Shared state management | Serializable `AssistantState`, append/dedupe reducers | Reducer/property and checkpoint tests | State summary in trace |
| LG-07 | Agent transition visibility | Named spans and public events | Trace/event correlation tests | UI-to-LangSmith comparison |
| LG-08 | Safe graph loops | One repair and bounded targeted recursion | Loop-limit and termination tests | Visible repair/recursion example |

## 5. Recursive Language Model behavior

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| RLM-01 | Explore document collections | Metadata-aware discovery stage | Discovery coverage tests | Candidate collection counts |
| RLM-02 | Generate Python-based search plans | Model emits validated plan DSL; trusted Python executes it | Plan schema/rejection tests | Rendered plan summary |
| RLM-03 | Decompose large tasks | Stable document grouping/batching strategy | Decomposition determinism tests | Multiple batch tasks |
| RLM-04 | Retrieve targeted sections | Batch workers query page/section evidence | Section attribution tests | Evidence from targeted sections |
| RLM-05 | Call sub-agents recursively | Bounded worker subgraph and one gap-driven level | Depth/child/call budget tests | One targeted recursive follow-up |
| RLM-06 | Aggregate results | Typed deterministic reducer with evidence dedupe | Aggregation/golden tests | Recurring root-cause summary |
| RLM-07 | Avoid loading entire corpus/context | IDs, compact evidence and findings in graph state | State-size/context budget tests | Trace shows bounded inputs |
| RLM-08 | Demonstrate annual outage scenario | Payment incidents filtered by date/topic, analyzed in batches | Golden end-to-end eval | Full scenario verification |

## 6. Retrieval and Pinecone

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| RAG-01 | Dense embeddings | Cloudflare Qwen3 embedding adapter, 1,024 dimensions and L2 normalization | Semantic retrieval cases and dimension assertion | Paraphrased question |
| RAG-02 | Sparse keyword/BM25 | Corpus-fitted `pinecone-text` BM25 encoder | Exact-code retrieval cases | Exact incident/error query |
| RAG-03 | Hybrid ranking | Single-index dense+sparse query with evaluated alpha | Hybrid ablation/evaluation | Scores/config in activity panel |
| RAG-04 | Use Pinecone | Async Pinecone vector adapter | Opt-in live contract test | Pinecone index/query trace |
| RAG-05 | Namespaces | Namespace per tenant/environment | Namespace isolation tests | Safe namespace summary |
| RAG-06 | Metadata filtering | Server-derived department/type/access/date filters | Filter and spoofing tests | Filtered incident query |
| RAG-07 | Document attribution | Stable doc/chunk/page/section/source/hash evidence | Attribution integrity tests | Evidence card/source citation |
| RAG-08 | Idempotent ingestion | Content hashes, deterministic IDs and stale reconciliation | Repeat/update/delete ingestion tests | Ingestion report |
| RAG-09 | Reranking | Wider hybrid candidates plus Pinecone hosted rerank and fallback | Rerank quality/failure tests | Before/after ranking evidence |
| RAG-10 | Retrieval evaluation | Versioned corpus/queries and measured parameters | Repeatable eval command | Results table and rationale |

## 7. Memory

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| MEM-01 | Preserve user context | Trusted principal plus scoped checkpoint state | Identity/context tests | Role/context maintained |
| MEM-02 | Preserve previous questions | Postgres checkpointer keyed by thread ID plus Postgres/InMemory owner-scoped conversation list with preview/count pagination | Multi-turn persistence and list tests | Follow-up turn plus history picker |
| MEM-03 | Relevant historical interactions | Recent-window plus validated rolling summary | Context selection tests | Long conversation summary |
| MEM-04 | Survive multiple session turns | Durable checkpoint and process restart | Restart integration test | Restart then follow-up |
| MEM-05 | Explain memory design | Architecture/implementation/ADR documentation | Documentation link audit | Operator memory explanation |
| MEM-06 | Long-term memory | Explicit propose/confirm/recall/expire/delete lifecycle | Consent/isolation/TTL/deletion tests | Cross-thread preference and deletion |
| MEM-07 | Keep memory types separate | LangGraph tables versus app-owned memory table | Repository/schema tests | Diagram and data-flow explanation |

## 8. Tools and MCP

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| TOOL-01 | Knowledge search tool | Scoped `KnowledgeIndex` tool | Tool/authorization tests | Agent-triggered document search |
| TOOL-02 | Simple MCP server | Separate official-SDK server with dummy data | MCP handshake/schema/timeout tests | Service catalog or incident lookup |
| TOOL-03 | Agent invokes MCP when needed | Deterministic `enrich_with_mcp` allow-list lookup plus `ToolGateway` selection | Enrichment, routing, and fake-model tests | Natural-language MCP request with `mcp:*` evidence |
| TOOL-04 | Python analysis tool | Named safe aggregations over validated records | Unit/property/invalid-input tests | Root-cause frequency analysis |
| TOOL-05 | Prevent unsafe execution | No eval/exec/shell/import/filesystem/network | Adversarial parameter tests | Rejected arbitrary-code attempt |
| TOOL-06 | Tool timeouts and output limits | Gateway deadlines, caps and typed failures | Timeout/oversize tests | Controlled MCP timeout |

## 9. Model and observability

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| LLM-01 | Use a modern LLM | Cloudflare Qwen3 generation model behind typed adapter (default vendor); GLM alternate and generic OpenAI-protocol fallback remain configurable, off by default | Provider contract and structured-output tests | Configured model shown safely |
| LLM-02 | Document selection rationale | ADR/research report with quality/cost roles | Documentation link audit | Trade-off explanation |
| OBS-01 | LangSmith mandatory | Tracing enabled around complete runtime | Trace-presence integration test | Open conversation trace |
| OBS-02 | Trace every conversation | Root run for every accepted request | Run/trace correlation test | UI run ID matches trace |
| OBS-03 | Trace tool calls | Nested tool spans with redacted inputs/outcomes | Test-adapter tests | MCP/analytics spans |
| OBS-04 | Trace agent transitions | Named agent/node spans | Transition-span tests | Supervisor/research/response tree |
| OBS-05 | Trace retrieval | Dense/sparse/hybrid/filter/rerank metadata spans | Retrieval-span tests | Retrieval trace details |
| OBS-06 | Protect traced data | Shared redaction and metadata-only policy | Canary secret/document leakage tests | Safe trace inspection |

## 10. Security, validation, and brand

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| SEC-01 | Instruction override protection | Fixed hierarchy, delimited evidence, deterministic controls | User/retrieved injection suite | Retrieved injection ignored |
| SEC-02 | Data exfiltration protection | Scope enforcement, egress allow-list, redaction, excerpt limits | Cross-tenant/secret leakage tests | Unauthorized source request denied |
| SEC-03 | Tool abuse protection | Allow-list, double auth, strict schemas, budgets, approval | Role/parameter/replay tests | Viewer/admin abuse attempts |
| SEC-04 | Validate user requests | Pydantic schema, size/encoding/content rules | Invalid/boundary/property tests | Graceful invalid request |
| SEC-05 | Validate tool parameters | Per-tool strict schemas and semantic checks | Malformed/out-of-range tests | Rejected unsafe argument |
| SEC-06 | Validate retrieved content | Treat as untrusted data, provenance and injection signal | Malicious-document tests | Injection document remains evidence only |
| SEC-07 | Unauthorized access guardrail | Principal-derived filters and resource ownership | Full RBAC/tenant suite | Viewer and cross-tenant denial |
| SEC-08 | Hallucinated citation guardrail | Evidence-ID validation and one repair | Unknown/mismatched citation tests | Safe insufficient-evidence answer |
| SEC-09 | Invalid response guardrail | Structured response checks and repair/failure path | Invalid-output tests | Visible validation failure |
| SEC-10 | Brand-value consideration | Fictional commercial-bank response policy | Unsupported commitment/advice tests | Brand-safe refusal/caveat |
| SEC-11 | Threat model | Assets, trust zones, threats, controls, residual risks | Documentation/control link audit | Security overview |

## 11. Authentication, RBAC, and rate limiting

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| AUTH-01 | Implement an allowed auth option | Upstream Keycloak hosted by Skycloak; local equivalent profile | OIDC/JWKS and local realm smoke tests | Login and issuer explanation |
| AUTH-02 | Viewer role | Chat/search only | Positive/negative capability tests | Viewer search and tool denial |
| AUTH-03 | Analyst role | Search, analytics and MCP | Positive/negative capability tests | Analyst analytics/MCP |
| AUTH-04 | Administrator role | All tools, impactful actions require approval | Capability/approval tests | Admin HITL flow |
| AUTH-05 | Agent cannot bypass authorization | Immutable scope and gateway recheck | Prompt/role/namespace spoof tests | Spoof attempt denied |
| RATE-01 | Token bucket | Atomic Redis Lua refill/consume | Time/refill/concurrency tests | Burst then graceful limit |
| RATE-02 | Per-user limits | Keyed by tenant and authenticated subject | User-isolation tests | Different users have separate budgets |
| RATE-03 | Configurable thresholds | Validated settings by environment/role if chosen | Settings boundary tests | Show safe configuration |
| RATE-04 | Graceful errors | Stable 429/retry-after and activity result | API contract tests | Limit response without crash |

## 12. Required failure handling

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| ERR-01 | LLM failures | Classified timeout/rate/provider/parse failures and bounded retry | Failure-injection tests | Controlled model failure |
| ERR-02 | Vector DB failures | Typed unavailable/degraded paths; never fabricate | Pinecone adapter failures | Controlled retrieval outage |
| ERR-03 | MCP failures | Timeout/error isolation and evidence-only continuation | MCP failure tests | Controlled MCP outage |
| ERR-04 | Tool timeouts | Derived deadline and cancellation | Slow-tool tests | Visible timeout event |
| ERR-05 | Invalid requests | Stable validation errors | API schema tests | Invalid request example |
| ERR-06 | Graceful degradation | Explicit partial/degraded/safe-failure responses | End-to-end failure matrix | Rerank/child failure examples |

## 13. Sample data

| ID | Requirement | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| DATA-01 | Incident reports | Synthetic payment/non-payment incidents across dates/severity | Fixture/schema tests | Annual outage query |
| DATA-02 | Architecture documents | Synthetic service architecture docs | Fixture/schema tests | Architecture question |
| DATA-03 | Operational runbooks | Synthetic remediation/runbook docs | Fixture/schema tests | Runbook answer |
| DATA-04 | Product specifications | Synthetic product docs | Fixture/schema tests | Product question |
| DATA-05 | Policies and meeting notes | Additional scenario corpus | Fixture/schema tests | Policy/follow-up question |
| DATA-06 | Security/evaluation fixtures | Restricted docs, injection text, exact codes and paraphrases | Expected-case tests | Security and hybrid checks |

## 14. v1.1 extensions (staged)

| ID | v1.1 extension | Implementation | Automated evidence | Required operator evidence |
|---|---|---|---|---|
| EXT-01 | Multi-agent collaboration and failure cascade handling | Typed shared state, isolated workers, bounded budgets, deterministic reducer, partial failures | Worker failure/deadline/circuit tests | One batch fails while siblings complete |
| EXT-02 | Human-in-the-loop approval | LangGraph interrupt and secure restart-safe resume | approve/deny/expire/replay/restart tests | Admin action pause and resume |
| EXT-03 | Reranking | Pinecone hosted rerank behind deep module | Quality and fallback tests | Rerank result/failure |
| EXT-04 | Long-term memory | Consent-based cross-thread memory lifecycle | Scope/consent/TTL/delete tests | Remember, new thread recall, forget |
| EXT-05 | Feedback loop | Run/trace-linked feedback and reviewed LangSmith export | Idempotency/export tests | Submit feedback and show dataset row |
| EXT-06 | Docker Compose | API, UI, MCP, Postgres, Redis; optional Keycloak | Fresh-start health/smoke tests | One-command local stack |

## 15. Evaluation categories

| Area | Weight | Primary evidence |
|---|---:|---|
| Agent Architecture | 20% | Explicit specialized subgraphs, typed state, interfaces, failure isolation |
| RAG Design | 15% | Measured dense+sparse hybrid retrieval, filters, attribution, reranking |
| LangGraph Usage | 15% | StateGraph routing, reducers, checkpoints, streaming, interrupt/resume |
| RLM Implementation | 10% | Validated Python plan DSL, discovery, batching, workers, reduce, recursion |
| Security and Guardrails | 10% | Threat model, deterministic scope/tool policy, adversarial tests, citations |
| Observability | 10% | Complete LangSmith traces, correlated safe events/logs, evaluation |
| Async Engineering | 5% | Async API/provider/tool paths, concurrency limits, cancellation/deadlines |
| RBAC | 5% | Keycloak roles, resource scopes, double tool authorization |
| Code Quality | 5% | Deep modules, typed contracts, tests, lint/type gates, focused history |
| Documentation | 5% | README, diagrams, ADRs, setup, security, evals, assumptions/trade-offs |

## 16. Release artifacts

| ID | Artifact | Artifact definition | Completion check |
|---|---|---|---|
| DEL-01 | Public source repository | GitHub repository at final reviewed commit | Anonymous clone/setup succeeds; secret scan clean |
| DEL-02 | Architecture diagram | Mermaid source plus rendered PNG/SVG in `docs/diagrams/` | Matches implemented modules and deployment |
| DEL-03 | Curated verification traces | Trace IDs from final commit/config, redacted and correlated to verification runs | Accessible, redacted and correlated to verification runs |
| DEL-04 | Assumptions and trade-offs | README/ADR section plus verification notes | Explicit choices, rejected options and limitations |
| DEL-05 | Reproducible deployment | Docker Compose and setup/troubleshooting docs | Fresh-machine smoke test passes |

## 17. Release audit rule

Before release:

1. Change a requirement's release-audit status only when implementation exists.
2. Link every row to its code location and exact test name.
3. Attach a trace ID, screenshot, result file, or verification timestamp where claimed.
4. Remove or label features that did not meet their acceptance criteria.
5. Reconcile the architecture diagram and README against the final code.
6. Run public-repository secret, personal-data, license, dependency, and dead-link checks.
7. Tag the exact verified commit and record dependency/model/corpus/prompt versions.

The release should prefer an honest, measured limitation over an unverified feature claim.

## Appendix A: Originating-brief mapping

This table links the originating brief areas to the requirement groups in this document.

| Originating brief area | Requirement ID groups |
|---|---|
| Agents | LG-01–LG-08, TOOL-01–TOOL-06, EXT-01, EXT-02 |
| RAG | RAG-01–RAG-10, OBJ-02, OBJ-03, DATA-01–DATA-06 |
| LangGraph | LG-01–LG-08, MEM-01–MEM-05, MEM-07, EXT-02 |
| RLM | RLM-01–RLM-08 |
| Security | SEC-01–SEC-11, AUTH-01–AUTH-05 |
| Observability | OBS-01–OBS-06, LLM-01–LLM-02, OBJ-04, EXT-05 |
| Async | BE-01–BE-07, ERR-01–ERR-06 |
| RBAC | AUTH-01–AUTH-05, OBJ-07, SEC-07 |
| Quality | OBJ-01, OBJ-08, OBJ-09, BE-06–BE-07, ERR-01–ERR-06, UI-01–UI-11 |
| Docs | MEM-05, LLM-02, SEC-11, DEL-02, DEL-04, DEL-05 |
