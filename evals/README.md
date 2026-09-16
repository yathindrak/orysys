# Retrieval evaluation

Run the live retrieval benchmark with:

```bash
uv run python -m orysys.evals.retrieval
```

The checked-in report compares dense-only retrieval, weighted dense-plus-BM25
retrieval, and hybrid retrieval followed by Pinecone hosted reranking. Evaluation
uses an analyst principal in the `commercial-bank` tenant with payments access and
clearance level 2. The restricted prompt-injection fixture has clearance level 8 and
must never appear in results for this principal.

The `bank-demo-v1` baseline produced mean recall@8 of 0.917 for all three
configurations. Reranking improved mean reciprocal rank from 0.833 to 1.0, with zero
restricted-document leaks and no degraded reranker calls.

The annual incident case currently retrieves three of four expected source documents
within the first eight evidence chunks. Its 0.75 document recall is a known baseline
gap. WP-06 should solve collection-wide synthesis through metadata-aware discovery
and bounded document batching rather than increasing direct-answer context without
limits.

## Security controls

Run the credential-free control suite with:

```bash
uv run python -m orysys.evals.controls
```

The checked-in `control-suite-v1.json` report covers control-character rejection,
explicit credential-exfiltration requests, the outbound host allow-list, and token-
bucket exhaustion. It is intentionally deterministic so CI and reviewers can reproduce
the result without provider credentials.
