# Orysys release audit

Audit date: 2026-09-16  
Release candidate base: `8af2617` plus the current WP-15 changes  
Final verified commit: **capture after the WP-15 commit**

Local repository verification on 2026-09-16: Ruff format/lint passed, strict mypy
passed for 97 source files, all 90 tests passed, all three deterministic evaluation
commands passed, Compose configuration validated, and the rendered SVG parsed as XML.
A selective live Cloudflare judge also passed the one synthetic case chosen for review;
its output was kept separate from the deterministic release gate. This is local
evidence, not a substitute for the final public CI run.

This is the status companion to the
[`requirements-traceability.md`](requirements-traceability.md) acceptance matrix.
“Implemented” means the code and deterministic repository evidence exist. “Verified”
is deliberately reserved for requirements whose CI, live-provider, and operator
evidence have all been captured at the final verified commit.

## Status by requirement group

| Requirement group | Status | Repository evidence | Evidence still required |
|---|---|---|---|
| Objective and backend (`OBJ`, `BE`) | Implemented | `src/orysys/`, API contract/unit tests, CI quality gates | Final CI URL and request verification |
| Frontend (`UI`) | Implemented with limitations | Streamlit app, view-model/design tests, UI smoke | Browser verification; no automatic SSE reconnect after network loss |
| LangGraph and research (`LG`, `RLM`) | Implemented | Direct/research graph tests, checkpoint tests, bounded budgets | Live direct and annual-research traces |
| Retrieval (`RAG`) | Implemented | Ingestion/retrieval contracts and checked-in retrieval report | Re-run live benchmark at final corpus/index version |
| Memory (`MEM`) | Implemented | Repository, API, checkpoint, ownership, TTL, and deletion tests | Restart-and-recall verification |
| Tools and MCP (`TOOL`) | Implemented | Gateway, handler, authorization, MCP protocol/timeout tests | Analyst success and viewer-denial verification |
| Models and observability (`LLM`, `OBS`) | Implemented; live proof pending | Provider contracts, redaction tests, telemetry spans; production now requires tracing | Redacted LangSmith trace IDs/URLs for final commit |
| Security/auth/rate limits (`SEC`, `AUTH`, `RATE`) | Implemented with one policy limitation | OIDC, RBAC, approval, rate-limit, citation and adversarial tests; threat model | Browser role verification; brand behavior is prompt policy, not a separate deterministic validator |
| Failure handling (`ERR`) | Implemented | Retry, cancellation, degradation, circuit and reliability tests | One controlled live degradation trace |
| Sample data (`DATA`) | Implemented | Versioned synthetic corpus, manifest, loaders, fixtures | Confirm verified index reports `bank-demo-v1` |
| Extensions (`EXT`) | Implemented | Research isolation, approval, reranking, memory, feedback and Compose tests/config | Fresh-host Compose CI and live verification evidence |
| Release artifacts (`DEL`) | Partial | README, operations, Mermaid plus SVG diagram, CI, Compose, this audit and release checklist | Public repository URL, final CI URL, and curated trace references |

No group is marked **Verified** yet because the final CI run and matching live evidence are
external artifacts and have not been supplied. This avoids turning configured capability
into a false execution claim.

## Automated evidence map

| Claim | Primary evidence |
|---|---|
| Grounded direct response and repair | `tests/graph/test_direct_graph.py`, `tests/unit/test_validation.py` |
| Bounded recursive research and child isolation | `tests/graph/test_research_graph.py` |
| Scoped dense/sparse/hybrid retrieval and reranking | `tests/contract/test_pinecone.py`, `evals/results/retrieval-bank-demo-v1.json` |
| OIDC, immutable scope, role policy | `tests/contract/test_oidc.py`, `tests/contract/test_api_auth.py` |
| Double-authorized tools and MCP boundary | `tests/unit/test_tool_gateway.py`, `tests/contract/test_mcp.py` |
| Durable checkpoints and long-term memory | `tests/graph/test_checkpoints.py`, `tests/unit/test_memory.py` |
| Approval replay/expiry/identity controls | `tests/graph/test_approval_graph.py`, `tests/unit/test_controls.py` |
| Deterministic answer/security/reliability evaluation | `evals/results/grounded-answers-v1.json`, `evals/results/control-suite-v1.json`, `evals/results/local-load-smoke-v1.json` |
| Packaging, migrations and supply-chain gates | `.github/workflows/ci.yml`, `Dockerfile`, `compose.yaml` |

## Known release limitations

- The corpus, identities, MCP data, and impactful action are synthetic. The approval
  mechanism is real; the action handler intentionally simulates a restart.
- Readiness reports process/configuration state, not active health probes for every
  external provider.
- The credential-free load report measures the API control plane, not Cloudflare or
  Pinecone latency/cost. Those measurements must be captured during an authorized run.
- The UI resumes durable conversation state after a reload, but an interrupted SSE
  stream is not automatically resumed from a last-event identifier.
- The live answer judge is intentionally optional and nondeterministic. Deterministic
  citation and expected-behavior checks remain the release gate.

## Release decision

The repository is ready for final CI and operator verification when the automated
commands in [`release-checklist.md`](release-checklist.md) pass. Public release remains
blocked until the exact commit, CI URL, and live trace references
are recorded without exposing credentials or restricted content.
