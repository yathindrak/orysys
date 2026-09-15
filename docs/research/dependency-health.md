# Orysys — Dependency & Platform Decisions

**Research date:** 2026-09-15  
**Scope:** product and platform choices for the Orysys v1 pilot.  
**Evidence policy:** primary sources only: upstream documentation, upstream repositories/releases, PyPI metadata, and published specifications. Versions below are the latest stable PyPI versions observed on the research date unless explicitly described as a service, server, or alternative.

## Decision summary

Use Python 3.13 and lock the complete environment with `uv.lock`. Python 3.13.15 is in bugfix support through October 2029 and all recommended dependencies support it. Python 3.14 is attractive but Unstructured currently declares `<3.14`; Python 3.10 reaches end of life in October 2026. See the [CPython support table](https://devguide.python.org/versions/) and [Python 3.13.15 release](https://www.python.org/downloads/release/python-31315/).

Build the primary workflow directly with `langgraph.StateGraph`. The graph should expose named, reviewable nodes for authorization, intent/routing, retrieval planning, batch exploration, synthesis, citation validation, and response generation. This is a better fit than making `deepagents` the top-level runtime because Orysys v1 requires explicit architecture, observable node transitions, security controls, and failure handling. `deepagents` is useful for a bounded recursive research branch, but it is pre-1.0 and its opinionated planning/filesystem/subagent harness hides decisions the operator must be able to inspect.

Use a single Pinecone dense index carrying both dense and sparse vectors. Generate
1,024-dimensional dense vectors with Cloudflare Workers AI's Qwen3 embedding adapter,
L2-normalize them, and combine them with a corpus-fitted BM25 encoder through Pinecone's
`dotproduct` hybrid index. Pinecone warns that raw sparse/BM25 weights and dense scores
have different ranges; `alpha` must be evaluated, not guessed. Add one standalone
reranking provider selected by evaluation. Cloudflare model IDs, free-allocation caps,
and paid-only exclusions are pinned in the architecture spec (Section 15); key sources are
Pinecone's
[hybrid search guide](https://docs.pinecone.io/guides/search/hybrid-search) and
[reranking guide](https://docs.pinecone.io/guides/search/rerank-results).

Use PostgreSQL for durable LangGraph checkpoints, conversation state, feedback, document manifests, and the audit trail. Use Redis only for the distributed token bucket and short-lived coordination/cache data. Keeping these responsibilities separate avoids making transient Redis state the source of truth for conversations.

Keep the Streamlit visual layer project-owned. Use `itsdaniyalm/streamlit-facade` and `truevis/aifab-facade` as design references only, not dependencies or codebase foundations. Implement a small `ui/design_system/` package containing tokens and only the components Orysys v1 needs. Vendor a reviewed subset of SVGs from the official `lucide-static` release and record its exact version and license in a manifest.

Use upstream Keycloak as the identity provider, hosted by Skycloak for the deployed demo. Integrate through standard OpenID Connect discovery and JWKS only so the application is not coupled to Skycloak-specific APIs. Streamlit performs Authorization Code login and forwards the exposed access token; FastAPI independently validates its signature, issuer, audience, lifetime, and role claims before constructing trusted runtime context. An optional Compose profile can run upstream Keycloak locally for offline review.

Expose a small application-owned stream event contract over SSE from FastAPI, for example `node.started`, `retrieval.progress`, `tool.requested`, `tool.completed`, `memory.updated`, `validation.result`, `token.delta`, and `run.completed`. Convert LangGraph stream parts to this contract at one adapter boundary. LangGraph's unified v2 stream shape requires `version="v2"`, but v1 remains the default; leaking raw tuples/dicts into Streamlit would make the UI brittle. See the [LangGraph streaming migration table](https://docs.langchain.com/oss/python/langgraph/streaming).

Enable LangSmith because it is mandatory, but redact or hash document text, user identifiers, access metadata, and tool secrets before tracing. LangSmith records inputs, outputs, metadata, and nested runs and retains SaaS traces for a documented period, so observability is also a data-governance boundary. See [observability concepts](https://docs.langchain.com/langsmith/observability-concepts) and [data storage/privacy](https://docs.langchain.com/langsmith/data-storage-and-privacy).

## Recommended dependency boundaries

The codebase should depend on small internal protocols rather than provider objects:

- `ChatModel`, `EmbeddingModel`, `Retriever`, `Reranker`, `CheckpointStore`, `RateLimiter`, `ToolExecutor`, `Tracer`, and `DocumentParser` are ports owned by the application.
- Provider implementations (`CloudflareChatModel`, `CloudflareEmbeddings`,
  `PineconeRetriever`, `LangSmithTracer`, and an optional generic OpenAI-protocol fallback
  that is off by default)
  live under infrastructure adapters.
- LangGraph nodes call use-case services, not SDKs directly. This keeps graph state serializable and makes failures, retries, and tests deterministic.
- RBAC is enforced both before a tool is exposed to the model and inside every tool implementation. Pinecone metadata filters are derived from trusted authenticated context, never from model output.
- Retry policy belongs at provider boundaries and applies only to demonstrably transient, idempotent operations. A retry library must not wrap arbitrary graph nodes or side-effecting tools.
- Parsed content and retrieved content are untrusted data. Preserve source/page/chunk identifiers, never treat retrieved instructions as system instructions, and validate every citation against the final retrieved set.

## Runtime, API, and UI

| Item | Current evidence | License / Python | Role and recommendation | Main risk / control |
|---|---|---|---|---|
| CPython | [3.13.15, 2026-08-05](https://www.python.org/downloads/release/python-31315/); [supported through 2029-10](https://devguide.python.org/versions/) | PSF; runtime | **Adopt 3.13.** It is still receiving binary bugfix releases and the recommended dependency set supports it. | Keep the normal GIL build. Do not use 3.10, which reaches EOL in 2026-10. Python 3.14 would exclude Unstructured today. |
| FastAPI | [0.141.1, 2026-07-29](https://pypi.org/project/fastapi/0.141.1/) | MIT; Python >=3.10 | **Adopt.** Async HTTP API, validation integration, dependency-injected auth context, SSE endpoint. | Still pre-1.0; upstream recommends pinning a tested minor range. Let FastAPI select compatible Starlette rather than pinning Starlette independently ([version policy](https://fastapi.tiangolo.com/deployment/versions/)). |
| Uvicorn | [0.53.0, 2026-09-14](https://pypi.org/project/uvicorn/0.53.0/) | BSD-3-Clause; Python >=3.10 | **Adopt `uvicorn[standard]`.** ASGI server for the FastAPI process. | High release cadence: lock the exact resolved version and test streaming disconnect/cancellation behavior. Do not confuse this with `uv`. |
| Streamlit | [1.63.0, 2026-09-01](https://docs.streamlit.io/develop/quick-reference/release-notes) | Apache-2.0; Python >=3.10 | **Adopt `streamlit[auth]` as a thin UI.** It has chat/status containers, streaming, and OIDC login. Configure `expose_tokens = "access"`, then use the access token only as a server-side Bearer credential to FastAPI ([`st.login` 1.63 docs](https://docs.streamlit.io/develop/api-reference/user/st.login)). | `st.write_stream` converts async generators to sync internally and warns about cached async references ([docs](https://docs.streamlit.io/develop/api-reference/write-magic/st.write_stream)). Exposed tokens are secrets: never render, log, trace, or persist them. Streamlit authentication is not the API authorization boundary. |
| streamlit-facade | [0.1.6, 2026-05-02](https://pypi.org/project/streamlit-facade/0.1.6/); [upstream repository](https://github.com/itsdaniyalm/streamlit-facade) | MIT; Python >=3.8; Streamlit >=1.35 | **Reference only; do not install.** Borrow the ideas of centralized tokens, consistent component wrappers, and a small icon helper. | It is a young 0.1.x project with no tagged GitHub releases. Its current implementation writes `.streamlit/config.toml` at runtime and bundles a generated icon table ([source](https://github.com/itsdaniyalm/streamlit-facade/blob/main/facade/theme.py)); both are broader and more brittle than Orysys v1 needs. |
| `truevis/aifab-facade` | [repository and README](https://github.com/truevis/aifab-facade) | MIT; application, not a package | **Visual/playground reference only.** It is a showcase that depends on upstream `streamlit-facade`, not a competing component library. | Do not vendor or depend on the playground. If any MIT-licensed implementation code is copied rather than merely imitated, retain the required copyright/license notice. |
| Lucide static SVGs | [`lucide-static` 1.46.0, 2026-09-14](https://github.com/lucide-icons/lucide/releases/tag/1.46.0); [license](https://github.com/lucide-icons/lucide/blob/main/LICENSE) | ISC, with MIT terms for inherited Feather icons | **Adopt a vendored, reviewed subset.** Store only icons actually used, plus upstream version, source path, checksum, and license in a manifest. Render from trusted static assets with accessible labels. | Do not add an unofficial Python wrapper or load a CDN at runtime. Do not copy the facade package's entire generated icon table: its source advertises Lucide 1.8.0 while current upstream is 1.46.0 ([facade icon source](https://github.com/itsdaniyalm/streamlit-facade/blob/main/facade/lucide.py)). |
| Pydantic | [2.13.5, 2026-08-28](https://github.com/pydantic/pydantic/releases/tag/v2.13.5) | MIT; Python >=3.9 | **Adopt.** Request/response, graph-state, tool-argument, event, citation, and settings validation. | Avoid arbitrary/pickle-backed deserialization. Treat validation as shape enforcement, not authorization. |
| pydantic-settings | [2.15.0, 2026-08-07](https://pypi.org/project/pydantic-settings/2.15.0/) | MIT; Python >=3.10 | **Adopt.** Typed environment configuration and secret references. | Secret values can leak through repr/logging; mark secret fields and redact at logging/tracing processors. |
| HTTPX2 | [2.13.0, 2026-09-14](https://pypi.org/project/httpx2/2.13.0/); [maintained by Pydantic](https://github.com/pydantic/httpx2) | BSD-3-Clause; Python >=3.10 | **Adopt for new application-owned outbound HTTP.** Reuse one `AsyncClient` with explicit connect/read/write/pool timeouts. The OpenAI SDK 3.x also uses HTTPX2 ([migration guide](https://github.com/openai/openai-python/blob/main/httpx2.md)). | It is a new major-line continuation of HTTPX; transports, mocks, hooks, and exception classes are a distinct compatibility boundary. Pin `<3` and hide it behind a small gateway. |
| HTTPX | [0.28.1, 2024-12-06](https://pypi.org/project/httpx/0.28.1/) | BSD-3-Clause; Python >=3.8 | **Conditional compatibility dependency only.** Keep it if a chosen Streamlit/SSE helper or test integration still requires HTTPX 0.x. | Upstream activity is limited and HTTPX2 is the maintained forward path. Do not mix `httpx` and `httpx2` request/response/exception types in application interfaces. |

## Orchestration and observability

| Item | Current evidence | License / Python | Role and recommendation | Main risk / control |
|---|---|---|---|---|
| LangGraph | [1.2.11, 2026-08-11](https://github.com/langchain-ai/langgraph/releases/tag/1.2.11) | MIT; Python >=3.10 | **Adopt as the orchestration engine.** Explicit `StateGraph`, typed state, subgraphs, interrupts, durable execution, and streaming. | Streaming APIs are still moving. Always request `version="v2"` and translate `StreamPart` to the application's event schema. Keep graph state small and serializable. |
| langchain-core | [1.6.3, 2026-09-11](https://pypi.org/project/langchain-core/1.6.3/) | MIT; Python >=3.10,<4 | **Adopt transitively / directly where its message, runnable, and tool contracts help.** | Avoid the broad `langchain` umbrella and community integrations unless needed. Extra abstraction makes security and failure paths harder to explain. |
| langchain-openai | [1.6.2, 2026-09-09](https://pypi.org/project/langchain-openai/1.6.2/) | MIT; Python >=3.10,<4 | **Do not include in the default stack.** It is useful only if an OpenAI-compatible fallback experiment proves it adds value beyond the project-owned Cloudflare REST adapter. | The default path must not assume exact LangChain/OpenAI feature parity with Cloudflare. Keep model streaming and structured-output normalization inside `CloudflareChatModel`. |
| Deep Agents | [0.7.14, 2026-09-14](https://pypi.org/project/deepagents/0.7.14/) | MIT; Python >=3.11 | **Optional, not the primary graph.** Consider one spike for the recursive research agent because it includes planning, filesystem context offload, subagents, permissions, and HITL on LangGraph ([overview](https://docs.langchain.com/oss/python/deepagents/overview)). | It is explicitly pre-1.0; a recent release renamed a subagent mode, demonstrating minor-version churn ([releases](https://github.com/langchain-ai/deepagents/releases)). Its built-in tools and hidden harness can obscure the Orysys v1 explainability and RBAC story. If used, pin exactly and wrap it as one subgraph/adapter. |
| LangSmith SDK/service | [SDK 0.12.5, 2026-09-15](https://pypi.org/project/langsmith/0.12.5/) | SDK MIT, hosted service terms; Python >=3.10 | **Adopt; mandatory.** Trace the root conversation and explicit spans for routing, retrieval, each tool, validation, and response generation. Add `user_role`, graph version, retrieval config, and correlation ID as non-sensitive metadata. | SaaS trace data may include confidential document content. Use conditional tracing and redaction, and provide a demo project separate from production data. |
| langgraph-supervisor | [0.0.31, 2025-11-19](https://pypi.org/project/langgraph-supervisor/0.0.31/) | MIT; Python >=3.10 | **Avoid for new work.** Write the supervisor/router explicitly in `StateGraph`. | Its own maintainers steer new projects toward direct tool-calling or StateGraph patterns; it reduces routing transparency and has lagged the main LangGraph release train. |

### Deep Agents decision

Deep Agents helps when the task truly needs an agent harness: automatic todo planning, context offload to a virtual filesystem, subagent isolation, sandbox execution, permissions, memory, and HITL. Those are real capabilities, not marketing wrappers; the [official architecture description](https://docs.langchain.com/oss/python/deepagents/overview) states that the package compiles to LangGraph and uses its durable runtime.

For Orysys v1, however, the top-level graph should remain explicit. The operator must be able to inspect each agent state, node, permission decision, retrieval transition, validation result, and failure boundary. A generic harness makes those choices harder to see and harder to test. The best compromise is:

1. Implement the production path with explicit LangGraph nodes and subgraphs.
2. If time remains, run a small `deepagents` spike for only the recursive research branch.
3. Require that branch to use the same read-only retrieval and role-aware tool ports as the main graph; do not grant local filesystem or shell access.
4. Compare it against the explicit branch on trace clarity, failure isolation, token cost, citation correctness, and reproducibility before keeping it.

## Model and retrieval providers

| Item | Current evidence | License / Python | Role and recommendation | Main risk / control |
|---|---|---|---|---|
| Cloudflare Workers AI | [Workers AI OpenAI-compatible endpoint](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/) | Hosted service; no required Python SDK | **Adopt for development/demo.** Use a project-owned async HTTPX2 adapter from FastAPI, not Cloudflare's JavaScript Vercel AI SDK. | Free usage is a capped shared 10,000-Neuron daily allocation, not an SLA; map quota/capacity/model-plan errors to typed provider failures. |
| Generation model | [`@cf/qwen/qwen3-30b-a3b-fp8`](https://developers.cloudflare.com/workers-ai/models/qwen3-30b-a3b-fp8/) | Cloudflare-hosted | **Adopt as configured default.** Evaluate `@cf/zai-org/glm-4.7-flash` as the named alternate, never as an automatic retry. | Catalog, plan access, pricing, and capabilities change. Pin model IDs in settings and pass provider contract/evaluation checks before the demo. |
| Embedding model | [`@cf/qwen/qwen3-embedding-0.6b`](https://developers.cloudflare.com/workers-ai/models/qwen3-embedding-0.6b/) | Cloudflare-hosted | **Adopt for the first index.** Assert the 1,024-dimensional output at startup/ingestion, L2-normalize it, and record model/dimension/normalization in the corpus manifest. | Any change requires a new Pinecone index and complete re-ingestion. |
| Pinecone Python SDK | [10.0.0, 2026-09-03](https://pypi.org/project/pinecone/10.0.0/) | Apache-2.0 SDK, hosted service terms; Python >=3.10 | **Adopt `pinecone[asyncio]`.** Async index/query clients, namespaces, metadata filtering, hybrid vectors, and hosted reranking. | v9 was a total rewrite and v10 followed quickly, so use an adapter and lock exact transitive versions. Pinecone is eventually consistent; ingestion tests must wait/check index stats rather than assuming read-after-write ([search limits/freshness](https://docs.pinecone.io/guides/search/search-overview)). |
| pinecone-text | [0.11.0, 2025-08-11; repository active in 2026](https://github.com/pinecone-io/pinecone-text) | Apache-2.0; Python >=3.9 | **Conditional adopt for BM25 sparse encoding only.** It is the shortest route to the Orysys v1 BM25 requirement and emits Pinecone-compatible sparse vectors. Fit on the actual corpus, persist parameters and a corpus/version checksum, and pin exactly. | The project calls itself public preview; BM25 document frequency is static and does not update as documents are added. Never use `BM25Encoder.default()` for enterprise data. Refit/reindex when the corpus changes materially, and isolate behind `SparseEncoder`. |
| Milvus / Zilliz Cloud | [Milvus 3.0.1, 2026-09-09](https://github.com/milvus-io/milvus/releases/tag/v3.0.1); [`pymilvus` 3.0.1](https://pypi.org/project/pymilvus/3.0.1/) | Milvus and SDK Apache-2.0; SDK Python >=3.9; Zilliz Cloud service terms | **Do not use for Orysys v1; keep as a future alternative.** Milvus is actively maintained and technically compelling because it provides server-side BM25 plus dense/sparse hybrid search ([official hybrid docs](https://milvus.io/docs/multi-vector-search.md)). | Orysys v1 requires Pinecone, so replacing it would fail a named requirement while adding self-hosted operational cost or another managed vendor. Preserve a narrow `Retriever` port; do not add `pymilvus`, `langchain-milvus`, or a second index now. |
| bm25s | [0.3.11, 2026-08-25](https://pypi.org/project/bm25s/0.3.11/) | MIT; Python >=3.8 | **Optional as a local lexical baseline/test oracle.** Useful for retrieval evaluation and a no-network development fallback. | It is a separate local index, not a direct drop-in for Pinecone sparse-vector upserts. Do not introduce a second production source of ranking truth merely to use it. |
| Pinecone hosted rerank | [Current rerank API/models](https://docs.pinecone.io/guides/search/rerank-results) | Hosted service | **Adopt for Orysys v1.** Retrieve a wider candidate set, rerank, then return a smaller evidence set. `bge-reranker-v2-m3` is a sensible first benchmark. | A single dense+sparse vector index cannot use integrated embedding/reranking; call standalone `pc.inference.rerank`. The documented pair limit is 512 tokens, so send concise chunk text and retain original attribution separately. |
| Cohere SDK / Rerank | [SDK 7.1.1, 2026-08-31](https://pypi.org/project/cohere/7.1.1/); [Rerank v4 model choices](https://docs.cohere.com/docs/rerank) | MIT SDK, hosted service terms; Python >=3.10 | **Optional benchmark**, especially `rerank-v4.0-fast` vs `-pro` for latency/quality. | Adds another vendor, key, billing surface, and data processor. Keep behind `Reranker`; do not adopt without relevance-evaluation evidence. |
| sentence-transformers | [6.0.1, 2026-08-31](https://pypi.org/project/sentence-transformers/6.0.1/) | Apache-2.0; Python >=3.10 | **Optional local/privacy reranker.** `CrossEncoder` is designed for second-stage pair scoring ([official guide](https://www.sbert.net/docs/quickstart.html#cross-encoder)). | Heavy Torch/model artifacts, cold starts, CPU latency, model-specific licenses, and operational complexity. Pin the model revision as well as the library. |
| FlashRank | [0.2.10, 2025-01-06](https://pypi.org/project/FlashRank/0.2.10/) | Apache-2.0; Python >=3.6 declared | **Avoid for Orysys v1.** | No PyPI release in over 20 months and an unrealistically old Python floor compared with this stack. Pinecone hosted rerank or Sentence Transformers has stronger current evidence. |

### Hybrid retrieval decision details

The Orysys v1 path should be one Pinecone index configured for dense vectors and `dotproduct`, with both dense and sparse values on each chunk. At ingestion, write stable `_id`, `document_id`, `chunk_id`, `source_uri`, `page_or_section`, `department`, `document_type`, `access_level`, `created_date`, `content_hash`, `embedding_model`, and `corpus_version`. Put environment/tenant boundaries in namespaces and role/document constraints in mandatory metadata filters.

At query time:

1. Derive the namespace and access filter from trusted authentication context.
2. Embed the query and encode it with the same BM25 parameters used for ingestion.
3. Scale dense and sparse query components with an evaluated `alpha`; Pinecone explicitly warns that unnormalized sparse weights otherwise dominate.
4. Retrieve 30-50 candidates, rerank, deduplicate adjacent chunks, and pass only the top evidence set to synthesis.
5. Validate every answer citation against the retrieved chunk IDs and access filter.

Keep an offline retrieval set of representative questions with relevance labels. Measure dense-only, sparse-only, hybrid alpha values, and hybrid-plus-rerank. Without this evaluation, adding hybrid and reranking merely increases complexity without proving quality.

## Authentication and authorization

Choose the Orysys v1 open-source-auth path: upstream Keycloak, with Skycloak operating the hosted instance. The hosting decision must not leak into application code. Both Streamlit and FastAPI should know only the realm issuer, expected audience/client ID, and standard OIDC discovery URL.

| Item | Current evidence | License / Python | Role and recommendation | Main risk / control |
|---|---|---|---|---|
| Keycloak | [26.7.3, 2026-08-31](https://github.com/keycloak/keycloak/releases/tag/26.7.3) | Apache-2.0 server | **Adopt as the identity provider.** Create separate confidential OIDC clients for Streamlit and, if needed, service-to-service use; define the Orysys v1 user roles in the realm/client and map them to a small application role enum. Keycloak publishes discovery and realm JWKS endpoints ([official OIDC endpoints](https://www.keycloak.org/securing-apps/oidc-layers)). | Keycloak has a large operational surface. Keep one reviewed realm export for the demo, disable unused flows, use Authorization Code flow, use exact redirect URIs, and do not use the Resource Owner Password flow. |
| Skycloak | [managed Keycloak documentation](https://skycloak.io/docs/faqs/) | Hosted service terms; no Python dependency | **Adopt as the deployed Keycloak host.** It handles hosting, updates, backups, and monitoring; connect using only standard Keycloak OIDC endpoints. Keep an optional local Keycloak Compose profile for offline assessment. | It adds a vendor/data-processor dependency and the public product evidence is much younger than Keycloak itself. Export realm configuration, document supported Keycloak version, and test the same contract against local upstream Keycloak to preserve exitability. |
| Authlib | [1.8.0, 2026-08-30](https://pypi.org/project/Authlib/1.8.0/) | BSD-3-Clause; Python >=3.10 | **Adopt transitively through `streamlit[auth]`.** Streamlit requires Authlib for `st.login`; application code should use Streamlit's OIDC API rather than constructing a second authorization client. | Do not use the browser identity cookie as an API credential. Configure `expose_tokens = "access"` and forward only the access token to FastAPI over TLS. |
| PyJWT | [2.14.0, 2026-09-11](https://pypi.org/project/PyJWT/2.14.0/) | MIT; Python >=3.9 | **Adopt `PyJWT[crypto]` in FastAPI for independent JWT/JWKS verification.** Cache keys by `kid`, refresh once on an unknown key, and require a fixed asymmetric algorithm plus exact `iss`, `aud`, `exp`, and `nbf` validation before reading roles. | Versions 2.9.0-2.12.1 had an algorithm allow-list bypass and are patched from 2.13.0 ([upstream advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-jq35-7prp-9v3f)). Pin a patched version, never select algorithms from the untrusted token header, and never log tokens. |
| pwdlib | [0.3.1, 2026-08-12](https://pypi.org/project/pwdlib/0.3.1/) | MIT; Python >=3.10 | **Not needed on the selected path.** If a completely offline hardcoded-user fallback is required, use `pwdlib[argon2]` for precomputed password hashes rather than plaintext; FastAPI's own security guide recommends pwdlib and PyJWT ([guide](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)). | Do not ship two active identity systems. Keep the fallback behind an explicit development-only setting and make it impossible to enable in the hosted profile. |
| Auth0 | [hosted identity platform documentation](https://auth0.com/docs/get-started/identity-fundamentals/introduction-to-auth0) | Hosted service terms; open-source SDKs, not an open-source identity server | **Do not select.** It is a capable standards-based IAM service, but it does not satisfy the Orysys v1 explicit open-source-auth option as directly as Keycloak. | Supporting Auth0 as a second provider would increase configuration and test scope without expanding scope. Standard OIDC boundaries preserve future compatibility without adding it now. |

The request path is: `st.login()` redirects to the Skycloak-hosted Keycloak realm; Streamlit exposes the access token through `st.user.tokens.access`; the Streamlit server sends `Authorization: Bearer ...` to FastAPI; FastAPI verifies the token itself against issuer discovery/JWKS and constructs `Principal(user_id, roles, scopes)`. Every request, graph run, retriever metadata filter, and MCP tool receives this principal as trusted runtime context. Never accept role, namespace, or access level from the UI payload or model state.

## Persistence, rate limiting, and MCP

| Item | Current evidence | License / Python | Role and recommendation | Main risk / control |
|---|---|---|---|---|
| PostgreSQL | [18.6 current and supported to 2030](https://www.postgresql.org/support/versioning/) | PostgreSQL License | **Adopt.** For Compose, pin a concrete 18.6 image tag/digest. Store checkpoints, thread/user records, feedback, document manifests, and immutable audit events. | Apply migrations explicitly. Back up durable state. Do not place large retrieved document bodies in graph checkpoints. |
| psycopg | [3.3.5, 2026-08-31](https://pypi.org/project/psycopg/3.3.5/) | LGPL-3.0-only; Python >=3.10 | **Adopt `psycopg[binary,pool]` for Orysys v1.** Psycopg 3 has native async, pooling, typing, and current development ([docs](https://www.psycopg.org/psycopg3/docs/)). | `psycopg_pool` is separately distributed. Open async pools explicitly in FastAPI lifespan; constructor auto-open is deprecated ([pool docs](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)). Production may prefer `psycopg[c,pool]` to link patchable system `libpq`. |
| LangGraph Postgres checkpointer | [3.1.2, 2026-08-07](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/) | MIT; Python >=3.10 | **Adopt `AsyncPostgresSaver`.** Official production-oriented durable checkpoint implementation. | Call `.setup()` once in a migration/startup step. Manual connections require `autocommit=True` and `dict_row`. Set `LANGGRAPH_STRICT_MSGPACK=true` or an explicit allow-list to prevent unsafe deserialization if the DB is compromised ([upstream README](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/README.md)). |
| Neon | [Postgres compatibility](https://neon.com/docs/reference/compatibility); [Psycopg guide](https://neon.com/docs/guides/python) | Managed-service terms; wire-compatible Postgres | **Optional managed deployment target.** It works with Psycopg 3 and can host both LangGraph checkpoints and application tables. Keep local PostgreSQL in Compose for reproducibility. Use a direct Neon connection string for the checkpointer and migrations. | Neon's pooler is PgBouncer in transaction mode ([pooling docs](https://neon.com/docs/connect/connection-pooling)); the current async checkpointer unconditionally uses pipeline mode and has an open incompatibility report ([LangGraph issue](https://github.com/langchain-ai/langgraph/issues/8420)). Do not point `AsyncPostgresSaver` at the `-pooler` hostname until an upstream fix is released and tested. Scale-to-zero adds a few hundred milliseconds of reactivation latency and drops session state ([docs](https://neon.com/docs/introduction/scale-to-zero)); retry connection establishment within a bounded deadline. |
| SQLAlchemy | [2.0.53, 2026-09-14](https://pypi.org/project/SQLAlchemy/2.0.53/) | MIT; Python >=3.7 | **Do not add its ORM/runtime layer initially.** The LangGraph checkpointer already speaks Psycopg, and the few application tables can use typed repository methods with parameterized SQL. | A second pool/session abstraction makes transaction ownership harder to see. Adopt SQLAlchemy later only if relational joins and model lifecycle complexity justify it; its Psycopg dialect supports native sync and async ([official dialect docs](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)). |
| Alembic | [1.20.0, 2026-09-11](https://pypi.org/project/alembic/1.20.0/) | MIT; Python >=3.10 | **Adopt for application-owned schema migrations, without adopting the ORM.** Version document manifests, feedback, audit, and any long-term-memory tables explicitly; run migrations as a separate deployment step through a direct PostgreSQL/Neon connection. | Alembic brings SQLAlchemy transitively and autogeneration is less useful without models. Keep hand-reviewed migration scripts small; do not place LangGraph-owned checkpoint DDL under application migrations unless upstream documents ownership. |
| redis-py | [8.1.0, 2026-07-30](https://pypi.org/project/redis/8.1.0/) | MIT client; Python >=3.10 | **Adopt only if the token bucket must work across processes.** Use one shared `redis.asyncio.Redis` instance created/closed in app lifespan ([async guide](https://redis.io/docs/latest/develop/clients/redis-py/async/)). Implement refill/consume atomically with a Lua script. | Redis server 8 is tri-licensed RSALv2/SSPLv1/AGPLv3 while the client is MIT ([license table](https://redis.io/legal/licenses/)). Get an enterprise license review or choose an approved compatible service. Pin server 8.10.1 or newer: 8.10.1 contains multiple security fixes ([release](https://github.com/redis/redis/releases/tag/8.10.1)). |
| Official MCP Python SDK | [2.2.0, 2026-09-07](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0) | MIT; Python >=3.10 | **Adopt package `mcp`.** Build the dummy enterprise server with the v2 high-level `MCPServer`, and use Streamable HTTP for the separately running demo service. | v2 is a major redesign for the 2026-07-28 protocol. `FastMCP` was renamed to `MCPServer`, imports moved, and the handshake/session model changed ([v2 guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/whats-new.md)). Pin `mcp>=2.2,<3` and write protocol-level contract tests. |
| `fastmcp` package | [4.0.3, 2026-09-05](https://pypi.org/project/fastmcp/4.0.3/) | Apache-2.0; Python >=3.10 | **Avoid for Orysys v1.** It is a separate third-party framework, not the v1 `mcp.server.fastmcp.FastMCP` namespace. | Naming makes reviews and migrations ambiguous. The official SDK is sufficient for one small server and better demonstrates protocol understanding. |
| langchain-mcp-adapters | [0.3.2, 2026-08-06](https://pypi.org/project/langchain-mcp-adapters/0.3.2/) | MIT; Python >=3.10 | **Optional, preferably avoid initially.** A thin internal adapter around the official `mcp` client makes RBAC and timeouts clearer. | LangChain is now moving MCP support into `langchain.mcp`, so this package is another churn point ([upstream tracking issue](https://github.com/langchain-ai/langchain/issues/40072)). |

## Reliability, testing, and developer tooling

| Item | Current evidence | License / Python | Role and recommendation | Main risk / control |
|---|---|---|---|---|
| structlog | [26.1.0, 2026-06-06](https://github.com/hynek/structlog/releases/tag/26.1.0) | MIT or Apache-2.0; Python >=3.10 | **Adopt.** Emit JSON logs with correlation/run/thread IDs, graph node, duration, outcome, and safe provider metadata. | A structured logger makes leaking structured secrets easier. Centralize a redaction processor and never log prompts/documents by default. |
| tenacity | [9.1.4 on PyPI, 2026-02-07](https://pypi.org/project/tenacity/9.1.4/) and [active upstream releases](https://github.com/jd/tenacity/releases) | Apache-2.0; Python >=3.10 | **Adopt narrowly.** Retry transient 429/5xx/network failures with exponential backoff, jitter, attempt/time caps, and retry callbacks into tracing. | Retrying non-idempotent tools can duplicate side effects and amplify outages. Each adapter must define retryable exceptions and idempotency behavior. |
| pytest | [9.1.1, 2026-06-19](https://docs.pytest.org/en/stable/changelog.html#pytest-9-1-1-2026-06-19) | MIT; Python >=3.10 | **Adopt.** Unit, contract, graph-transition, policy, citation, failure-injection, and retrieval-evaluation tests. | Avoid tests that require live paid services by default; mark a small opt-in integration suite. |
| pytest-asyncio | [1.4.0, 2026-05-26](https://pytest-asyncio.readthedocs.io/en/stable/reference/changelog.html#id1) | Apache-2.0; Python >=3.10 | **Adopt with explicit `asyncio_mode = "strict"` and loop scopes.** | 1.x deprecates overriding `event_loop_policy`; configure the new loop-factory hook and avoid legacy fixture patterns. |
| pytest-httpx2 | [1.0.0, 2026-05-20](https://pypi.org/project/pytest-httpx2/1.0.0/) | BSD-3-Clause; Python >=3.10 | **Adopt for application-owned HTTPX2 adapters.** Use it for OIDC discovery/JWKS and any other raw HTTP gateways; fake provider ports for model tests. | It is a young 1.0 plugin. Keep most tests against application protocols and use transport-level mocking only for the small HTTP adapter surface. |
| RESPX | [0.23.1, 2026-04-08](https://pypi.org/project/respx/0.23.1/) | BSD-3-Clause; Python >=3.8 | **Use only if legacy HTTPX remains.** It supplies route matching, side effects, and pytest fixtures for `httpx` 0.x ([docs](https://lundberg.github.io/respx/)). | It does not intercept the OpenAI SDK's default HTTPX2 traffic. Do not retain legacy HTTPX solely to keep RESPX tests. |
| Ruff | [0.16.7, 2026-09-10](https://pypi.org/project/ruff/0.16.7/) | MIT; Python >=3.7 | **Adopt for linting and formatting.** Use one `pyproject.toml`; run `ruff check` and `ruff format --check` in CI. | Ruff formatter does not sort imports by itself; the linter's `I` rules do that. Avoid formatter-conflicting lint rules listed in the [formatter docs](https://docs.astral.sh/ruff/formatter/). |
| mypy | [2.3.1, 2026-08-15](https://pypi.org/project/mypy/2.3.1/) | MIT; Python >=3.10 | **Adopt as the CI type checker.** Python-native packaging keeps the toolchain simple. Start strict on domain, application, and boundary modules; tolerate narrow third-party adapter ignores with codes. | LangGraph/LangChain generics can produce noisy edge cases. Do not weaken the whole project for adapter-local typing gaps. |
| Pyright | [Microsoft CLI 1.1.414, 2026-09-10](https://www.npmjs.com/package/pyright) | MIT; Node runtime | **Optional editor/CI alternative, not alongside mypy initially.** | Microsoft's official distribution is npm. The PyPI package named `pyright` is explicitly community-maintained and installs/manages Node ([official installation docs](https://github.com/microsoft/pyright/blob/main/docs/installation.md)); adding it to Python dependencies obscures provenance. |
| uv | [0.12.14, 2026-09-15](https://pypi.org/project/uv/0.12.14/) | MIT or Apache-2.0; Python package metadata >=3.8 | **Adopt for interpreter/dependency management, locking, running, and builds.** Commit `uv.lock`; use `uv sync --locked` in CI and containers. | `uv sync` is exact by default and removes undeclared packages. This is desirable in CI but should be understood locally. Preview malware checking is not a substitute for a vulnerability scanner ([locking docs](https://docs.astral.sh/uv/concepts/projects/sync/)). |
| Docker Compose | [v5.5.1, 2026-09-03](https://github.com/docker/compose/releases/tag/v5.5.1) | Apache-2.0 implementation | **Adopt for the demo stack:** API, Streamlit, PostgreSQL, Redis, and MCP server, with health checks and named volumes; add local Keycloak only as an optional profile. | Use `docker compose`, not the legacy Python `docker-compose` package/command. Follow the rolling Compose Specification and omit obsolete top-level `version` ([spec docs](https://docs.docker.com/reference/compose-file/version-and-name/)). Pin container tags or digests, never `latest`. |

## Document parsing candidates

Document parsing should be a pluggable ingestion concern, outside the request-serving process. Persist normalized document elements and provenance before chunking so a parser can be replaced without changing retrieval code.

| Item | Current evidence | License / Python | Recommendation | Main risk / control |
|---|---|---|---|---|
| pypdf | [6.18.1, 2026-09-11](https://pypi.org/project/pypdf/6.18.1/) | BSD-3-Clause; Python >=3.9 | **Adopt baseline for text-native PDFs.** Small, permissive, and actively released. | PDF text order/layout can be ambiguous and scanned pages need OCR. Keep page numbers and extraction warnings; do not silently treat empty output as success. |
| Docling | [2.127.0, 2026-09-14](https://pypi.org/project/docling/2.127.0/) | MIT; Python >=3.10 | **Optional preferred upgrade for complex layouts, tables, Office files, images, and OCR.** It has a unified, provenance-aware document model and many formats ([formats](https://docling-project.github.io/docling/usage/supported_formats/)). Prefer the narrowest suitable `docling-slim` extras ([official slim package](https://github.com/docling-project/docling/blob/main/packages/docling-slim/README.md)). | Large ML/native dependency surface and CPU/memory cost. Run in an ingestion worker/container, whitelist formats, cap pages/file size/time, and disable unnecessary remote fetching/models. |
| Unstructured | [0.27.6, 2026-09-14](https://pypi.org/project/unstructured/0.27.6/) | Apache-2.0; Python >=3.11,<3.14 | **Optional alternative, not alongside Docling in Orysys v1.** Rich element types and document-specific partitioning/chunking ([partition docs](https://docs.unstructured.io/open-source/core-functionality/partitioning)). | Heavy optional/system dependencies, narrower Python range, and hosted/local product split. Its staging helpers are being deprecated; do not build new architecture around them ([deprecation notice](https://docs.unstructured.io/open-source/core-functionality/staging)). |
| PyMuPDF | [1.28.2, 2026-08-06](https://pypi.org/project/pymupdf/1.28.2/) | AGPL-3.0 or commercial; Python >=3.10 | **Avoid unless licensing is explicitly approved.** Technically strong and actively maintained. | AGPL network copyleft/commercial licensing is an unnecessary license risk when permissive alternatives meet Orysys v1. |

Recommended sequence: support `.txt`, `.md`, and text-native `.pdf` with standard-library parsing plus pypdf; define golden extraction tests; add Docling only for a small set of layout-heavy samples that fail those tests. Never import both large parsing stacks merely to advertise format coverage.

## Package-name and deprecation traps

- Install `pinecone`, not `pinecone-client`. Pinecone states that upgrading with `pinecone-client` does not work from SDK v6 onward ([SDK guide](https://docs.pinecone.io/reference/sdks/python/overview)). An unrelated older `pinecone-io/pinecone-client` repository is archived.
- Milvus's official Python SDK is `pymilvus`, not a package guessed from the server name. It is deliberately absent because Pinecone is an Orysys v1 requirement.
- Install official `mcp`. In official MCP SDK v2, use `from mcp.server import MCPServer`; old examples using `mcp.server.fastmcp.FastMCP` are v1. The separate `fastmcp` PyPI project is not that namespace.
- Install `psycopg`, not `psycopg3`; upstream explicitly says there is no `psycopg3` package. Prefer Psycopg 3 over feature-frozen Psycopg 2 for new async work ([install guide](https://www.psycopg.org/psycopg3/docs/basic/install.html)).
- Install `redis`; import async support from `redis.asyncio`. Do not install `aioredis`: its last release was in 2021 and it was merged into redis-py ([Redis FAQ](https://redis.io/faq/doc/26366kjrif/what-is-the-difference-between-aioredis-v2-0-and-redis-py-asyncio)).
- Use `pydantic-settings` for environment settings. Old Pydantic v1 examples importing `BaseSettings` from `pydantic` are stale.
- Use focused packages `langgraph` and `langchain-core`; do not add every
  `langchain-community` integration or a provider wrapper the default path does not use.
- `deepagents` is the official LangChain package name, but it is an agent harness on top of LangGraph, not a replacement for understanding or exposing the graph.
- LangGraph v2 streaming is opt-in via `version="v2"`; examples omitting the version may return raw values, tuples, or triples depending on modes/subgraphs.
- `streamlit-facade` is the small upstream library; `truevis/aifab-facade` is only its demonstration application. Neither belongs in the lock. Keep the project-owned design-system surface deliberately small.
- Use the official `lucide-static` SVG source, not an unofficial Python `lucide` wrapper. Record source version and license for every vendored subset.
- `httpx2` is a separate import/package and a maintained successor, not an HTTP/2 feature flag for `httpx`. RESPX targets legacy `httpx`; use `pytest-httpx2` or `httpx2.MockTransport` for HTTPX2.
- Install `PyJWT`, imported as `jwt`; do not install the unrelated `jwt` package. Avoid copying older FastAPI examples that use `python-jose` when current FastAPI documentation uses PyJWT and pwdlib.
- Skycloak is a managed host for upstream Keycloak, not a Python authentication SDK required by the application. Integrate with the realm's standard discovery/JWKS endpoints so local Keycloak and Skycloak-hosted Keycloak have the same contract.
- Use Docker's Compose plugin (`docker compose`) and the Compose Specification. The standalone Python Compose v1 path and versioned 2.x/3.x file formats are legacy.
- If Pyright is chosen, the Microsoft-owned package is on npm. The same-named PyPI package is a community wrapper.
- Avoid old `PyPDF2` examples; the maintained project/package is `pypdf`.

## Initial lock policy

Do not paste all latest versions directly into broad production ranges. For Orysys v1:

- Declare only direct dependencies in `pyproject.toml`.
- Commit an exact `uv.lock` and build the container with `uv sync --locked --no-dev`.
- Put a tested minor upper bound on pre-1.0 or fast-moving surfaces: FastAPI, Deep Agents (if used), `pinecone-text`, and MCP adapters.
- Put a major upper bound on stable SDKs that have recently had major rewrites:
  `pinecone>=10,<11`, `httpx2>=2,<3`, `mcp>=2.2,<3`, `langgraph>=1.2,<2`.
- Depend on one parser stack and one reranker in the default group; keep heavy/local alternatives in optional dependency groups.
- Schedule a dependency review rather than unattended major upgrades. The acceptance gate is unit/contract tests plus the retrieval evaluation set and a Docker Compose smoke test.

An appropriate first-pass direct dependency set is:

```text
fastapi
uvicorn[standard]
streamlit[auth]
langgraph
langchain-core
langsmith
pinecone[asyncio]
pinecone-text
pydantic
pydantic-settings
httpx2
psycopg[binary,pool]
langgraph-checkpoint-postgres
alembic
redis
mcp
PyJWT[crypto]
structlog
tenacity
pypdf
```

Development dependencies:

```text
pytest
pytest-asyncio
pytest-httpx2
ruff
mypy
```

Optional groups should contain `deepagents`, `docling` (or `unstructured`, not both initially), `sentence-transformers`, and `cohere` only when a measured experiment requires them. Keep legacy `httpx` plus RESPX in a compatibility group only if a selected SSE helper demonstrably requires them. A local Keycloak container belongs in an optional Compose profile, not Python dependencies.

## Architecture consequences to keep visible during implementation

1. **Explainability is an event and state design problem, not chain-of-thought disclosure.** Show named transitions, tool inputs after redaction, retrieval counts/filters, retry/fallback decisions, validation outcomes, and evidence IDs. Do not display hidden reasoning tokens.
2. **Authorization must be deterministic.** Authentication context enters the graph as immutable trusted runtime context. The model may request a tool, but it never selects its own role, namespace, metadata filter, or approval status.
3. **RLM recursion needs budgets.** Track depth, child count, wall time, token use, and retrieved-chunk count in typed state. Aggregate structured child findings; do not concatenate whole documents or raw child transcripts.
4. **Failure isolation needs typed provider errors.** Map timeouts, rate limits, unavailable providers, invalid outputs, and authorization failures to explicit graph transitions and user-safe responses. Keep partial evidence and checkpoints so a retriable failure does not repeat successful work.
5. **Conversation memory and long-term memory are different.** LangGraph/Postgres checkpoints retain per-thread state; curated durable user facts belong in a separate store/table with provenance, expiry, and user controls. Do not automatically convert every chat message into long-term memory.
6. **Observability must not bypass security.** Apply the same redaction policy to structlog, LangSmith, Streamlit activity events, exception messages, and tests/fixtures.

## Sources consulted

The package-version links in the tables are primary PyPI project metadata. The most consequential architecture claims were cross-checked against:

- [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence), and [Postgres checkpointer](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/README.md)
- [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview), [streaming](https://docs.langchain.com/oss/python/deepagents/streaming), and [releases](https://github.com/langchain-ai/deepagents/releases)
- [Pinecone Python SDK](https://docs.pinecone.io/reference/sdks/python/overview), [hybrid search](https://docs.pinecone.io/guides/search/hybrid-search), and [reranking](https://docs.pinecone.io/guides/search/rerank-results)
- [Workers AI OpenAI-compatible API](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/), [pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), and [Qwen3 embedding](https://developers.cloudflare.com/workers-ai/models/qwen3-embedding-0.6b/)
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [v2 changes](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/whats-new.md), and [versioning policy](https://github.com/modelcontextprotocol/python-sdk/blob/main/VERSIONING.md)
- [LangSmith observability concepts](https://docs.langchain.com/langsmith/observability-concepts) and [data storage/privacy](https://docs.langchain.com/langsmith/data-storage-and-privacy)
- [Psycopg async behavior](https://www.psycopg.org/psycopg3/docs/advanced/async.html) and [pool lifecycle](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
- [Redis asyncio client](https://redis.io/docs/latest/develop/clients/redis-py/async/), [Redis licensing](https://redis.io/legal/licenses/), and [Redis 8.10.1 security release](https://github.com/redis/redis/releases/tag/8.10.1)
- [Streamlit chat/status/streaming APIs](https://docs.streamlit.io/develop/api-reference/chat), [`st.login` and token exposure](https://docs.streamlit.io/develop/api-reference/user/st.login), [FastAPI async guidance](https://fastapi.tiangolo.com/async/), and [Docker Compose Specification](https://docs.docker.com/reference/compose-file/)
- [Keycloak OIDC endpoints](https://www.keycloak.org/securing-apps/oidc-layers), [Keycloak 26.7.3 release](https://github.com/keycloak/keycloak/releases/tag/26.7.3), [Skycloak managed-service FAQ](https://skycloak.io/docs/faqs/), and [PyJWT security advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-jq35-7prp-9v3f)
- [Neon Postgres compatibility](https://neon.com/docs/reference/compatibility), [Neon pooling](https://neon.com/docs/connect/connection-pooling), and [LangGraph PgBouncer issue](https://github.com/langchain-ai/langgraph/issues/8420)
- [`streamlit-facade` upstream](https://github.com/itsdaniyalm/streamlit-facade), [`aifab-facade` playground](https://github.com/truevis/aifab-facade), and [Lucide upstream/license](https://github.com/lucide-icons/lucide)
- [Milvus hybrid search](https://milvus.io/docs/multi-vector-search.md), [Milvus 3.0.1 release](https://github.com/milvus-io/milvus/releases/tag/v3.0.1), and [`pymilvus` metadata](https://pypi.org/project/pymilvus/3.0.1/)
- [HTTPX2 upstream](https://github.com/pydantic/httpx2), [OpenAI's HTTPX2 migration guide](https://github.com/openai/openai-python/blob/main/httpx2.md), [SQLAlchemy Psycopg dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg), and [Alembic](https://github.com/sqlalchemy/alembic)
- [Docling supported formats](https://docling-project.github.io/docling/usage/supported_formats/), [Unstructured partitioning](https://docs.unstructured.io/open-source/core-functionality/partitioning), and [pypdf](https://pypi.org/project/pypdf/)
- [uv locking](https://docs.astral.sh/uv/concepts/projects/sync/), [Ruff](https://docs.astral.sh/ruff/), [pytest changelog](https://docs.pytest.org/en/stable/changelog.html), and [pytest-asyncio changelog](https://pytest-asyncio.readthedocs.io/en/stable/reference/changelog.html)
