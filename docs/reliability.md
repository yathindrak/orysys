# Reliability and performance evidence

## Runtime policy

Provider retries occur only around Cloudflare chat and embedding HTTP calls. Network
errors, 408, 429, and selected 5xx responses receive at most the configured number of
attempts with bounded exponential backoff. Authentication/authorization failures such
as 403 are returned immediately. Cancellation is never caught by the retry layer.

Chat calls, embedding batches, LangGraph fan-out, and research workers have explicit
concurrency caps. Research work receives both a run deadline and the smaller deadline
from its plan. A child that fails or times out becomes a failed outcome; successful
siblings remain available to the reducer and the final answer is marked incomplete.

Hybrid retrieval degrades to sparse-only when dense encoding fails and to dense-only
when sparse encoding fails. A Pinecone failure produces an explicit safe answer with a
`retrieval.degraded` event. Reranker failure preserves the pre-rerank hybrid order.

## Failure evidence

| Failure | Safe behavior | Automated evidence |
|---|---|---|
| Cloudflare timeout/429/5xx | bounded transient retry | `test_retry.py`, `test_cloudflare_chat.py`, `test_cloudflare_embeddings.py` |
| Cloudflare 403 | no retry; provider unavailable | `test_cloudflare_chat.py` |
| Invalid model/citations | one repair, then safe answer | `test_direct_graph.py` |
| Pinecone unavailable | no model call; degraded event and safe answer | `test_direct_graph.py` |
| Dense or sparse encoder unavailable | independently use the remaining retrieval signal | `test_pinecone_retrieval.py` |
| Reranker unavailable | preserve hybrid ordering and mark degraded | `test_pinecone_retrieval.py` |
| Research child failure/deadline | retain siblings, retry within budget, label incomplete | `test_research_graph.py` |
| Tool/MCP timeout | safe provider error and `tool.failed` event | `test_tool_gateway.py`, `test_mcp.py` |
| Redis unavailable | fail closed outside development | `test_api_controls.py` |
| OIDC/JWKS unavailable | authentication unavailable, never anonymous fallback | `test_oidc.py` |
| SSE disconnect/provider failure | close work stream or emit redacted `run.failed` | `test_api_cancellation.py` |
| Approval expiry/replay/mismatch | no action side effect | `test_controls.py`, `test_api_controls.py` |

## Performance baseline

Run the credential-free smoke test with:

```bash
uv run python -m orysys.evals.reliability
```

The checked-in `evals/results/local-load-smoke-v1.json` report records 25 requests at
concurrency five. It is a local control-plane baseline, not a claim about production
model or Pinecone latency. The deterministic fake profile performs no paid provider
calls, so its estimated provider cost is zero. Capture live latency, tokens, and cost
only during an explicitly authorized provider run.
